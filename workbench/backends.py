"""Local-only inference adapters. No remote model requests, implicit downloads, or file logs."""
from __future__ import annotations
import http.client
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from .domain import canonical
from .inventory import command, executable
from .workflows import Cancelled, Unsupported

class BackendError(RuntimeError):
    pass

class Transport:
    def __init__(self, base_url: str, token: str = '', timeout: float = 900):
        url=urlsplit(base_url)
        if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost','::1') or url.username or url.password:
            raise ValueError('Inference must use an HTTP loopback endpoint on the GPU machine')
        self.host,self.port=url.hostname,url.port or 80
        self.token,self.timeout=token,timeout
        self.connection=None
    def cancel(self):
        conn=self.connection
        if conn:
            try:
                if conn.sock:conn.sock.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            conn.close()
    def request(self,path,body=None,stream=False,cancel=None):
        conn=http.client.HTTPConnection(self.host,self.port,timeout=self.timeout)
        self.connection=conn
        headers={'Content-Type':'application/json'}
        if self.token:headers['Authorization']='Bearer '+self.token
        started=time.perf_counter()
        try:
            if cancel and cancel.is_set():raise Cancelled('Cancelled')
            conn.request('POST' if body is not None else 'GET',path,canonical(body).encode() if body is not None else None,headers)
            response=conn.getresponse()
            if response.status>=400:
                detail=response.read(65536).decode('utf-8',errors='replace')
                raise BackendError(f'HTTP {response.status}: {detail}')
            if not stream:return json.loads(response.read())
            chunks=[];text=[];reasoning=[];finish=None;usage={};timings={};first=None;visible=None
            while True:
                if cancel and cancel.is_set():raise Cancelled('Cancelled')
                line=response.readline()
                if not line:
                    if cancel and cancel.is_set():raise Cancelled('Cancelled')
                    break
                if not line.startswith(b'data:'):continue
                data=line[5:].strip()
                if data==b'[DONE]':break
                chunk=json.loads(data);chunks.append(chunk)
                if 'error' in chunk:raise BackendError(str(chunk['error']))
                if chunk.get('usage'):usage=chunk['usage']
                if chunk.get('timings'):timings=chunk['timings']
                for choice in chunk.get('choices',[]):
                    delta=choice.get('delta',{})
                    piece=delta.get('content') or ''
                    thought=delta.get('reasoning_content') or delta.get('reasoning') or ''
                    if piece or thought:
                        if first is None:first=time.perf_counter()-started
                    if piece:
                        if visible is None:visible=time.perf_counter()-started
                        text.append(piece)
                    if thought:reasoning.append(thought)
                    if choice.get('finish_reason') is not None:finish=choice['finish_reason']
            if finish is None:raise BackendError('Stream ended without a finish reason')
            cached=usage.get('prompt_tokens_details',{}).get('cached_tokens',timings.get('cache_n'))
            return {'text':''.join(text),'reasoning_text':''.join(reasoning),'finish_reason':finish,
                    'request_seconds':time.perf_counter()-started,'first_token_seconds':first,
                    'first_visible_text_seconds':visible,'usage':usage,'timings':timings,
                    'cached_tokens':cached,'raw_chunks':chunks}
        except (OSError,http.client.HTTPException,json.JSONDecodeError) as exc:
            if cancel and cancel.is_set():raise Cancelled('Cancelled') from exc
            raise BackendError(str(exc)) from exc
        finally:
            conn.close();self.connection=None

class LocalBackend:
    supports_schema=True
    def __init__(self,settings,gpu,log=lambda *args:None):
        self.settings,self.gpu,self.log=settings,gpu,log
        self.kind=settings.get('backend','lmstudio')
        self.supports_cache=self.kind=='llamacpp'
        port=1234 if self.kind=='lmstudio' else 1235
        self.transport=Transport(f'http://127.0.0.1:{port}',settings.get('model_api_token',''))
        self.process=None;self.reader=None;self.owned_id=None;self.load_metadata={};self.context=None;self.version_info={}
    def cancel(self):self.transport.cancel()
    def inventory(self):
        return self.transport.request('/api/v1/models').get('models',[])
    def load(self,model,context,cancel=None):
        self.context=context['allocated_tokens']
        started=time.perf_counter();self.owned_id='rpg-workbench-'+model['id']
        if self.kind=='lmstudio':
            lms=executable('lms',self.settings.get('lms_path',''))
            if not lms:raise BackendError('LM Studio CLI not found')
            inventory=self.inventory()
            if any(m.get('loaded_instances') for m in inventory):
                self.owned_id=None
                raise BackendError('Unload existing LM Studio models using the preflight action first')
            try:self.version_info={'lms':command([lms,'--version']),'runtimes':command([lms,'runtime','ls'])}
            except Exception:self.version_info={'note':'Runtime version query unavailable; inspect load metadata'}
            command([lms,'load',model['model_key'],'--identifier',self.owned_id,
                     '--context-length',str(self.context),'--gpu','max'],timeout=900)
            instances=[i for m in self.inventory() for i in m.get('loaded_instances',[]) if i['id']==self.owned_id]
            if len(instances)!=1:raise BackendError('LM Studio did not expose the requested instance')
            actual=instances[0].get('config',{}).get('context_length')
            if actual is not None and actual!=self.context:raise BackendError('Loaded context differs from requested context')
            self.load_metadata={'backend':'lmstudio','instance':instances[0],'context':context,
                                'full_gpu_residency_verified':False}
        elif self.kind=='llamacpp':
            exe=executable('llama-server',self.settings.get('llama_path',''))
            if not exe:raise BackendError('llama-server executable not found')
            help_text=command([exe,'--help'])
            try:self.version_info={'llama_server':command([exe,'--version'])}
            except Exception:self.version_info={'note':'Version query unavailable'}
            args=[exe,'--model',model['paths'][0],'--alias',self.owned_id,'--host','127.0.0.1',
                  '--port','1235','--ctx-size',str(self.context),'--n-predict','-1','--gpu-layers','999',
                  '--parallel','1','--no-context-shift','--slots']
            if '--fit ' in help_text:args+=['--fit','off']
            if '--jinja' in help_text:args+=['--jinja']
            if '--no-webui' in help_text:args+=['--no-webui']
            env=dict(os.environ)
            if 'CUDA_VISIBLE_DEVICES' not in env:env['CUDA_VISIBLE_DEVICES']=self.gpu['uuid']
            flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
            self.process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                text=True,encoding='utf-8',errors='replace',env=env,**flags)
            def drain():
                for line in self.process.stdout:self.log('backend',line.rstrip())
            self.reader=threading.Thread(target=drain,daemon=True);self.reader.start()
            deadline=time.monotonic()+900
            while True:
                if cancel and cancel.is_set():raise Cancelled('Cancelled while loading')
                if self.process.poll() is not None:raise BackendError('llama-server exited; inspect backend log')
                try:
                    health=self.transport.request('/health')
                    if health.get('status')=='ok':break
                except BackendError:pass
                if time.monotonic()>deadline:raise BackendError('Model did not load before readiness timeout')
                time.sleep(.3)
            info=self.transport.request('/v1/models')
            if not any(m.get('id')==self.owned_id for m in info.get('data',[])):
                raise BackendError('Model identity mismatch')
            props=self.transport.request('/props')
            actual=props.get('default_generation_settings',{}).get('n_ctx') or props.get('default_generation_settings',{}).get('params',{}).get('n_ctx')
            if actual and actual!=self.context:raise BackendError('Backend changed the requested context allocation')
            self.load_metadata={'backend':'llamacpp','arguments':args,'context':context,'properties':props,
                                'full_gpu_residency_verified':False}
        else:raise BackendError('Unknown inference backend')
        self.load_metadata['load_seconds']=time.perf_counter()-started
        check=self.generate([{'role':'user','content':'Reply with the single word READY.'}],
                            {'temperature':0,'seed':42,'top_p':1},None,'default',cancel)
        if check['finish_reason']!='stop' or not check['text'].strip():raise BackendError('Model did not complete the readiness probe')
        self.load_metadata['health_check']=check
        self.load_metadata['health_exact_ready']=check['text'].strip()=='READY'
        if self.supports_cache:self.clear_cache()
        return self.load_metadata
    def clear_cache(self):
        if not self.supports_cache:raise Unsupported('LM Studio does not expose a verified cache reset in this adapter')
        result=self.transport.request('/slots/0?action=erase',{})
        if 'n_erased' not in result:raise Unsupported('Backend did not confirm slot erasure')
        return result
    def generate(self,messages,settings,schema,cache='default',cancel=None):
        if cache!='default' and not self.supports_cache:raise Unsupported('Use native llama.cpp for controlled caching')
        token_count=None
        if self.kind=='llamacpp':
            formatted=self.transport.request('/apply-template',{'messages':messages})['prompt']
            token_count=len(self.transport.request('/tokenize',{'content':formatted,'add_special':True})['tokens'])
            if token_count>=self.context:raise BackendError('Input exceeds the automatically allocated context; no input was truncated')
            if cache=='off':self.clear_cache()
        body={'model':self.owned_id,'messages':messages,**settings,'stream':True,
              'stream_options':{'include_usage':True}}
        if self.kind=='llamacpp':
            body.update(max_tokens=-1,id_slot=0)
            if cache!='default':body['cache_prompt']=cache=='on'
        if schema is not None:body['response_format']={'type':'json_schema','json_schema':{'name':'step_output','strict':True,'schema':schema}}
        result=self.transport.request('/v1/chat/completions',body,stream=True,cancel=cancel)
        result['input_tokens_verified']=token_count
        result['output_limit_policy']='no harness cap; finite backend context'
        result['request_parameters']={k:v for k,v in body.items() if k!='messages'}
        return result
    def unload(self):
        try:
            if self.process:
                self.process.terminate()
                try:self.process.wait(timeout=15)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
                if self.reader:self.reader.join(timeout=2)
            elif self.kind=='lmstudio' and self.owned_id:
                self.transport.request('/api/v1/models/unload',{'instance_id':self.owned_id})
        finally:self.process=None;self.owned_id=None

class DemoBackend:
    """Plumbing only, prominently labelled simulated; never research evidence."""
    supports_cache=True
    supports_schema=True
    def __init__(self,log=lambda *args:None):self.log=log;self.counter=0;self.load_metadata={};self.context=65536
    def load(self,model,context,cancel=None):
        self.counter=0;self.load_metadata={'simulated':True,'context':context,'load_seconds':0.0,'health_exact_ready':True}
        return self.load_metadata
    def unload(self):pass
    def cancel(self):pass
    def clear_cache(self):self.counter=0
    def generate(self,messages,settings,schema,cache='default',cancel=None):
        from .scoring import parse
        if cancel and cancel.is_set():raise Cancelled('Cancelled')
        time.sleep(.02)
        self.counter+=1
        source=parse(messages[1]['content'].split('\nSOURCE\n',1)[1])
        instruction=messages[-1]['content'];event=source.get('new_information','')
        is_time='minutes' in event
        if schema and schema.get('type')=='boolean':
            text='true' if ('time' in instruction.lower() and is_time) or 'correct' in instruction.lower() else 'false'
        elif schema and schema.get('type')=='string':text='"14:20"'
        elif 'Describe' in instruction:text='The time changes to 14:20.' if is_time else 'Tom adds a green jacket and does not move.'
        elif 'narrat' in instruction.lower():text='Tom waits in the kitchen. Exactly five minutes pass. The clock now reads 14:20.'
        else:
            semantic='list_add' in instruction or 'semantic' in instruction
            patch=[{'op':'set' if semantic else 'replace','path':'/time','value':'14:20'}] if is_time else [{'op':'list_add' if semantic else 'add','path':'/characters/Tom/clothing'+('' if semantic else '/-'),'value':'green jacket'}]
            text=canonical(patch)
        return {'text':text,'finish_reason':'stop','request_seconds':.02,'first_token_seconds':.01,
                'usage':{},'timings':{},'cached_tokens':1024 if cache=='on' and self.counter>1 else 0,
                'simulated':True,'raw_chunks':[]}
