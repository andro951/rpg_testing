"""Owned llama.cpp process; explicit device placement and bounded unattended operations."""
from __future__ import annotations
import contextlib
import os
import re
import secrets
import socket
import subprocess
import threading
import time
from pathlib import Path
from .execution_policy import (CPUOffload, ContextCapacity, DoesNotFit, RunFailure, RuntimeStall,
    UnverifiedPlacement, LOAD_TIMEOUT_SECONDS, classify_load_failure, placement)
from .inventory import executable
from .workflows import Cancelled, Unsupported


def diagnostic_command(args, timeout=30):
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,**flags)
    output='\n'.join(x for x in (p.stdout,p.stderr) if x)
    if p.returncode:raise RunFailure(output or 'Native runtime command failed')
    return output.strip()


def capabilities(exe, preparation=False):
    help_text=diagnostic_command([exe,'--help'])
    required=['--ctx-size','--n-predict','--gpu-layers','--parallel','--no-context-shift','--slots','--fit','--api-key','--list-devices','--reasoning']
    missing=[flag for flag in required if not re.search(re.escape(flag)+r'(?=[\s,=]|$)',help_text)]
    if missing:raise RunFailure('Runtime lacks required controls: '+', '.join(missing))
    result={'help':help_text,'version':diagnostic_command([exe,'--version'])}
    if not preparation:
        devices=diagnostic_command([exe,'--list-devices'])
        if not re.search(r'^\s*(?:CUDA|Vulkan)\d+\s*:',devices,re.M|re.I):
            raise RunFailure('Runtime reports no CUDA/Vulkan GPU. A CPU-only build is not eligible.')
        result['devices']=devices
    return result


class NativeBackend:
    supports_cache=True
    supports_schema=True
    def __init__(self,settings,gpu,log=lambda *args:None):
        from .backends import Transport
        self.settings,self.gpu,self.log=settings,gpu,log
        if settings.get('backend','llamacpp')!='llamacpp':raise ValueError('Only native llama.cpp is supported')
        self.token=secrets.token_urlsafe(32)
        self.transport=Transport('http://127.0.0.1:1235',self.token,timeout=60)
        self.process=None;self.reader=None;self.owned_id=None;self.context=None
        self.load_metadata={};self.version_info={};self.lines=[];self.timed_out=False
        self.requested_layers='all';self.execution_class='full_gpu';self.progress=lambda task,pct,detail='':None

    def cancel(self):
        self.transport.cancel()
        if self.process and self.process.poll() is None:
            self.process.terminate()

    @contextlib.contextmanager
    def budget(self,seconds):
        self.timed_out=False
        def expire():
            self.timed_out=True;self.cancel()
        timer=threading.Timer(seconds,expire);timer.daemon=True;timer.start()
        try:
            yield
            if self.timed_out:raise RuntimeStall('Operational watchdog expired',{'timeout_seconds':seconds})
        except Exception as exc:
            if self.timed_out:
                error=RuntimeStall('Operational watchdog expired',{'timeout_seconds':seconds})
                error.partial=getattr(exc,'partial',{})
                raise error from exc
            raise
        finally:timer.cancel()

    def launch_arguments(self,exe,model,context,help_text,layers='all'):
        args=[exe,'--model',model['paths'][0],'--alias',self.owned_id,'--host','127.0.0.1','--port','1235',
              '--ctx-size',str(context['allocated_tokens']),'--n-predict','-1','--gpu-layers',str(layers),
              '--fit','off','--parallel','1','--split-mode','none','--no-context-shift','--slots',
              '--reasoning','off','--api-key',self.token]
        # Structured-state benchmarks use direct output only. Never let
        # llama.cpp/model chat templates silently enable reasoning via "auto".
        # capabilities() requires --reasoning so this cannot degrade silently.
        # llama.cpp routes core INFO messages (including the authoritative
        # "offloaded X/Y layers to GPU" placement summary) at verbosity 4.
        # The server default is 3, which hides that evidence on current builds.
        if '--log-verbosity' in help_text or '--verbosity' in help_text or '-lv' in help_text:
            args += ['--log-verbosity','4']
        # Current llama.cpp gates POST /slots/{id}?action=erase behind
        # --slot-save-path even though erase itself writes no slot file.
        # Keep that directory private to the Workbench runtime cache.
        if '--slot-save-path' in help_text:
            slot_path=Path(self.settings.get('runtime_cache',Path.cwd()/'.local/runtime-cache'))/'slots'
            slot_path.mkdir(parents=True,exist_ok=True)
            args += ['--slot-save-path',str(slot_path.resolve())]
        for flag in ('--jinja','--no-webui','--no-mmproj','--op-offload','--kv-offload'):
            if flag in help_text:args.append(flag)
        for flag in ('--n-cpu-moe','--n-cpu-ffn'):
            if flag in help_text:args += [flag,'0']
        return args

    def load(self,model,context,cancel=None,layers='all',execution_class='full_gpu'):
        self.progress('Loading model',0,'Checking runtime and GPU controls.')
        self.lines=[];self.load_metadata={};self.context=context['allocated_tokens']
        self.requested_layers=layers;self.execution_class=execution_class
        self.owned_id='rpg-workbench-'+model['id']
        exe=executable('llama-server',self.settings.get('llama_path',''))
        if not exe:raise RunFailure('Select or install llama-server in Worker setup')
        info=capabilities(exe,preparation=False);self.version_info={'llama_server':info['version']}
        with socket.socket() as sock:
            sock.settimeout(.25)
            if sock.connect_ex(('127.0.0.1',1235))==0:
                raise RunFailure('Port 1235 belongs to another process; it was not stopped')
        args=self.launch_arguments(exe,model,context,info['help'],layers)
        self.progress('Loading model',15,'Runtime verified; launching llama-server.')
        devices=re.findall(r'^\s*((?:CUDA|Vulkan)\d+)\s*:\s*(.*)$',info.get('devices',''),re.M)
        if devices:
            cuda=[d for d in devices if d[0].startswith('CUDA')]
            if cuda:
                if len(cuda)!=1:raise RunFailure('Native runtime exposes multiple CUDA devices; use one allocated/visible GPU')
                chosen=cuda[0][0]
            else:
                if os.environ.get('SLURM_JOB_ID'):raise RunFailure('Use CUDA in Slurm; Vulkan does not honor the CUDA allocation mask')
                name=re.sub(r'^(?:NVIDIA\s+)?(?:GeForce\s+)?','',self.gpu.get('name',''),flags=re.I)
                matches=[d for d in devices if name and name.lower() in d[1].lower()]
                if len(matches)!=1:raise RunFailure('Could not map the Vulkan device to the detected NVIDIA GPU')
                chosen=matches[0][0]
            args+=['--device',chosen]
            self.version_info['selected_device']=chosen
        elif info.get('devices') is not None:raise RunFailure('Native runtime did not identify a GPU device')
        env={k:v for k,v in os.environ.items() if not k.startswith(('LLAMA_ARG_','HF_','GGML_'))}
        if 'CUDA_VISIBLE_DEVICES' not in env and self.gpu.get('uuid'):env['CUDA_VISIBLE_DEVICES']=self.gpu['uuid']
        cache=Path(self.settings.get('runtime_cache',Path.cwd()/'.local/runtime-cache'));cache.mkdir(parents=True,exist_ok=True)
        env.update(CUDA_CACHE_PATH=str(cache),XDG_CACHE_HOME=str(cache),HF_HOME=str(cache/'huggingface'))
        flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
        started=time.perf_counter()
        try:
            self.progress('Loading model',25,'Starting model process and waiting for readiness.')
            self.process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                                          encoding='utf-8',errors='replace',env=env,**flags)
            process=self.process
            def drain():
                for line in process.stdout:
                    line=line.rstrip().replace(self.token,'[REDACTED]')
                    self.lines.append(line);self.log('backend',line)
            self.reader=threading.Thread(target=drain,daemon=True);self.reader.start()
            with self.budget(LOAD_TIMEOUT_SECONDS):
                while True:
                    if cancel and cancel.is_set():raise Cancelled('Stopped during loading')
                    if process.poll() is not None:
                        if self.reader:self.reader.join(timeout=1)
                        raise classify_load_failure('\n'.join(self.lines[-60:]) or 'Runtime exited while loading')
                    evidence=placement(self.lines)
                    if execution_class=='full_gpu' and evidence['status']=='cpu_offloaded':
                        raise CPUOffload('CPU model placement detected before benchmark',evidence)
                    try:
                        if self.transport.request('/health').get('status')=='ok':
                            self.progress('Loading model',75,'llama-server is healthy; verifying placement and context.')
                            break
                    except Exception:
                        if self.timed_out:raise RuntimeStall('Model load timed out')
                    time.sleep(.15)
                evidence=placement(self.lines)
                if evidence['status']=='unverified':raise UnverifiedPlacement('No verifiable layer-placement report',evidence)
                if execution_class=='full_gpu' and evidence['status']!='full_gpu':raise CPUOffload('Partial GPU placement',evidence)
                if execution_class=='cpu_offloaded' and evidence['status']=='full_gpu':
                    raise RunFailure('Hybrid load unexpectedly reports all layers on GPU',evidence)
                if evidence.get('gpu_layers',0)==0:raise DoesNotFit('No model layers were placed on the GPU',evidence)
                models=self.transport.request('/v1/models')
                if not any(m.get('id')==self.owned_id for m in models.get('data',[])):raise RunFailure('Loaded model identity mismatch')
                props=self.transport.request('/props')
                settings=props.get('default_generation_settings',{})
                actual=settings.get('n_ctx') or settings.get('params',{}).get('n_ctx')
                if actual and actual!=self.context:raise RunFailure('Runtime changed the context allocation')
                self.load_metadata={'placement':evidence,'execution_class':execution_class,'requested_gpu_layers':layers,
                    'context':context,'load_seconds':time.perf_counter()-started,
                    'arguments':['[REDACTED]' if a==self.token else a for a in args],
                    'runtime':self.version_info,'properties':props,
                    'full_gpu_layers_verified':evidence['status']=='full_gpu',
                    'independent_os_residency_verified':False}
                self.progress('Loading model',90,'Placement verified; running readiness probe.')
                probe=self.generate([{'role':'user','content':'Reply with the single word READY.'}],
                                    {'temperature':0,'seed':42,'top_p':1},None,'default',cancel)
                if probe['finish_reason']!='stop' or not probe['text'].strip():raise RunFailure('Readiness probe did not finish normally')
                self.load_metadata['health_check']=probe;self.load_metadata['health_exact_ready']=probe['text'].strip()=='READY'
                self.clear_cache();self.progress('Loading model',100,'Model loaded and ready.')
            return self.load_metadata
        except Exception as exc:
            from .backends import BackendError
            if isinstance(exc,BackendError):
                converted=classify_load_failure(str(exc));converted.partial_response=getattr(exc,'partial_response',{})
                exc=converted
            self.load_metadata.update(context=context,execution_class=execution_class,
                placement=placement(self.lines),load_seconds=time.perf_counter()-started)
            if isinstance(exc,RunFailure):exc.evidence={**self.load_metadata,**exc.evidence}
            self.unload();raise exc

    def seed_reproducibility_check(self,cancel=None):
        from .seedcheck import run_seed_check
        return run_seed_check(self,cancel,self.progress)

    def clear_cache(self):
        result=self.transport.request('/slots/0?action=erase',{})
        if type(result.get('n_erased')) is not int:raise Unsupported('Runtime did not confirm prompt-cache erasure')
        return result

    def generate(self,messages,settings,schema,cache='default',cancel=None):
        if cancel and cancel.is_set():raise Cancelled('Stopped')
        text=self.transport.request('/apply-template',{'messages':messages})['prompt']
        count=len(self.transport.request('/tokenize',{'content':text,'add_special':True})['tokens'])
        if count+256>=self.context:raise ContextCapacity('Input leaves insufficient continuation space',count+4096)
        if cache=='off':self.clear_cache()
        body={'model':self.owned_id,'messages':messages,**settings,'stream':True,'stream_options':{'include_usage':True},
              'max_tokens':-1,'id_slot':0,'cache_prompt':cache!='off'}
        if schema is not None:body['response_format']={'type':'json_schema','json_schema':{'name':'step_output','strict':True,'schema':schema}}
        from .backends import BackendError
        try:result=self.transport.request('/v1/chat/completions',body,stream=True,cancel=cancel)
        except BackendError as exc:
            if cancel and cancel.is_set():
                stopped=Cancelled('Stopped');stopped.partial_response=getattr(exc,'partial_response',{});raise stopped from exc
            classified=classify_load_failure(str(exc))
            classified.partial_response=getattr(exc,'partial_response',{})
            raise classified from exc
        result['input_tokens_verified']=count;result['output_limit_policy']='EOS or native context; no token cap'
        if result['finish_reason']=='length':
            error=ContextCapacity('Continuation reached context capacity',self.context+1)
            error.partial_response=result;raise error
        return result

    def unload(self):
        process=self.process
        try:
            if process:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
                if self.reader:self.reader.join(timeout=2)
                if process.stdout:process.stdout.close()
        finally:self.process=None;self.reader=None;self.owned_id=None
