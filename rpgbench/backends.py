"""Backend lifecycle and HTTP transport; no hosted-model credentials in result files."""
from __future__ import annotations
import hashlib
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from .core import canonical, parse_json


class BackendError(RuntimeError):
    pass


def command(args: list[str], timeout: float = 60, env=None) -> str:
    try:
        p = subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout, env=env)
        return p.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise BackendError(f"Command failed ({args[0]}): {exc}") from exc


def select_gpu(csv_text: str, selector: str | None = None, visible: str | None = None) -> dict:
    import csv
    rows = []
    for row in csv.reader(csv_text.splitlines(), skipinitialspace=True):
        if len(row) != 6:
            raise BackendError("Unexpected nvidia-smi output")
        idx, uuid, name, total, free, driver = [x.strip() for x in row]
        rows.append({'index': idx, 'uuid': uuid, 'name': name,
                     'total_gib': float(total)/1024, 'free_gib': float(free)/1024, 'driver': driver})
    allowed = rows
    if visible is not None:
        choices = [s.strip() for s in visible.split(',') if s.strip()]
        if any(s.startswith('MIG-') for s in choices):
            raise BackendError("MIG requires an explicit MIG-aware adapter; refusing to measure the parent GPU")
        allowed = [r for r in rows if any(s == r['index'] or r['uuid'].startswith(s) for s in choices)]
    if selector is not None:
        allowed = [r for r in allowed if selector == r['index'] or r['uuid'].startswith(selector)]
    if len(allowed) != 1:
        raise BackendError("Need exactly one eligible GPU. Set gpu_selector to its physical index/UUID; do not override the Slurm allocation")
    return allowed[0]


def detect_gpu(worker: dict) -> dict:
    csv = command(['nvidia-smi', '--query-gpu=index,uuid,name,memory.total,memory.free,driver_version', '--format=csv,noheader,nounits'])
    if worker.get('backend') == 'lmstudio' and len([line for line in csv.splitlines() if line.strip()]) != 1:
        raise BackendError("The LM Studio adapter currently supports single-NVIDIA-GPU hosts only; its existing daemon does not inherit this worker's CUDA device selection")
    gpu = select_gpu(csv, worker.get('gpu_selector'), os.environ.get('CUDA_VISIBLE_DEVICES'))
    expected = worker.get('expected_gpu_name')
    if expected and expected.casefold() not in gpu['name'].casefold():
        raise BackendError(f"Expected {expected}, detected {gpu['name']}")
    return gpu


def artifact_info(model: dict, worker: dict) -> tuple[dict, dict]:
    binding = worker.get('model_bindings', {}).get(model['id'])
    if not binding:
        raise BackendError("No local binding. Add the exact LM Studio key and GGUF paths to worker.local.json")
    paths = [Path(p).expanduser().resolve() for p in binding.get('files', [])]
    if [p.name for p in paths] != [Path(f).name for f in model['files']]:
        raise BackendError("Local filenames/shards do not match this model catalog entry")
    files = []
    for path in paths:
        h = hashlib.sha256()
        try:
            with path.open('rb') as f:
                while chunk := f.read(8*1024*1024):
                    h.update(chunk)
        except OSError as exc:
            raise BackendError(f"Cannot read model artifact: {path}") from exc
        files.append({'filename': path.name, 'bytes': path.stat().st_size, 'sha256': h.hexdigest()})
    if not files:
        raise BackendError("Missing model files")
    return {'files': files, 'source_revision': binding.get('source_revision')}, binding


class HTTPClient:
    def __init__(self, base_url: str, timeout: float = 300, allow_remote: bool = False):
        self.base_url = base_url.rstrip('/')
        p = urllib.parse.urlsplit(self.base_url)
        if p.scheme not in {'http', 'https'} or p.username or p.password or p.query or p.fragment:
            raise BackendError("Use an HTTP(S) endpoint without credentials/query in the URL")
        self.local = p.hostname in {'127.0.0.1','localhost','::1'}
        if not self.local and not allow_remote:
            raise BackendError("Remote endpoints need allow_remote_endpoint=true and are not local GPU timing")
        self.timeout = timeout

    def request(self, method: str, url: str, body=None):
        headers = {'Content-Type':'application/json'}
        token = os.environ.get('RPG_MODEL_API_KEY')
        if token:
            headers['Authorization'] = 'Bearer '+token
        req = urllib.request.Request(url, data=None if body is None else canonical(body).encode(), headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read(32*1024*1024+1)
                if len(raw) > 32*1024*1024:
                    raise BackendError("Response exceeds 32 MiB safety limit")
                return parse_json(raw.decode('utf-8'))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            # Do not echo request headers/tokens or full error response bodies.
            raise BackendError(f"HTTP request failed: {type(exc).__name__}: {getattr(exc, 'code', '')}") from exc

    def models(self):
        return self.request('GET', self.base_url+'/models')

    def generate(self, model_id: str, messages: list, settings: dict, seed: int, extra: dict | None = None) -> dict:
        extra = extra or {}
        protected = {'model','messages','temperature','top_p','seed','max_tokens','stream'}
        if protected & extra.keys():
            raise BackendError("extra_body cannot override recorded experiment settings")
        # Conservative BYTE bound, not a measured token count. Intended for the small initial fixtures.
        upper = sum(len(m['content'].encode('utf-8'))+96 for m in messages)+256+settings['max_output_tokens']
        if upper > settings['context_tokens']:
            raise BackendError("Conservative context guard exceeded; do not silently truncate")
        body = dict(extra, model=model_id, messages=messages, temperature=settings['temperature'],
                    top_p=settings['top_p'], seed=seed, max_tokens=settings['max_output_tokens'], stream=False)
        start = time.perf_counter()
        response = self.request('POST', self.base_url+'/chat/completions', body)
        seconds = time.perf_counter()-start
        try:
            choice = response['choices'][0]
            content = choice['message'].get('content') or ''
            if not isinstance(content, str):
                raise ValueError("Non-text completion")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise BackendError("Malformed chat-completion envelope") from exc
        return {'text':content, 'finish_reason':choice.get('finish_reason'), 'raw':response,
                'wall_seconds':seconds, 'usage':response.get('usage'), 'ttft_seconds':None,
                'prompt_processing_seconds':None, 'decode_tokens_per_second':None}


class MockBackend:
    """Deterministic transport fixture, NOT a language model or quality measurement."""
    def __init__(self):
        self.calls = 0
        self.loads = []
        self.model_id = ''
        self.load_metadata = {}

    def load(self, model, binding, experiment):
        self.model_id = model['id']
        self.loads.append(self.model_id)
        self.load_metadata = {'simulated':True, 'load_seconds':0, 'full_gpu_residency_verified':False}

    def unload(self):
        self.model_id = ''

    def generate(self, messages, settings, seed):
        self.calls += 1
        if len(messages) == 1:
            return {'text':'OK','finish_reason':'stop','raw':{'mock':True},'wall_seconds':0.0,'usage':None}
        source = parse_json(messages[1]['content'])
        info = source['new_information']
        is_time = 'five minutes' in info
        if 'Do not generate a patch yet' in messages[-1]['content']:
            text = 'Only time changes to 14:20.' if is_time else 'Append green jacket to Tom clothing. Nobody moves.'
        else:
            semantic = 'semantic operations' in messages[-1]['content']
            if is_time:
                p=[{'op':'set' if semantic else 'replace','path':'/time','value':'14:20'}]
            else:
                p=[{'op':'list_add' if semantic else 'add','path':'/characters/Tom/clothing'+('' if semantic else '/-'),'value':'green jacket'}]
            text=canonical(p)
        return {'text':text,'finish_reason':'stop','raw':{'mock':True},'wall_seconds':0.0,'usage':None,
                'ttft_seconds':None,'prompt_processing_seconds':None,'decode_tokens_per_second':None}


class ManagedBackend:
    """LM Studio CLI on desktop, or an owned llama-server process inside a GPU allocation."""
    def __init__(self, worker: dict, log_dir: Path, gpu: dict):
        self.worker, self.log_dir, self.gpu = worker, log_dir, gpu
        self.client = HTTPClient(worker['base_url'],worker.get('request_timeout_seconds',300),worker.get('allow_remote_endpoint',False))
        if not self.client.local:
            raise BackendError("Managed lifecycle must run beside the server; remote HTTP requires a separate externally managed adapter")
        self.model_id = ''
        self.process = None
        self.log_file = None
        self.load_metadata = {}

    def command_for(self, model: dict, binding: dict, experiment: dict) -> list[str]:
        alias = 'rpgbench-'+model['id']
        if self.worker['backend']=='lmstudio':
            if not binding.get('model_key') or 'COPY ' in binding['model_key']:
                raise BackendError("Set the exact model_key from lms ls --json")
            return [self.worker.get('lms_executable','lms'),'load',binding['model_key'],'--identifier',alias,
                    '--gpu',self.worker.get('gpu_offload','max'),'--context-length',str(experiment['context_tokens'])]
        return [self.worker.get('llama_server_executable','llama-server'),'--model',str(Path(binding['files'][0]).expanduser().resolve()),
                '--alias',alias,'--host','127.0.0.1','--port',str(urllib.parse.urlsplit(self.client.base_url).port or 8080),
                '--ctx-size',str(experiment['context_tokens']),'--parallel','1','--n-gpu-layers','999','--no-context-shift']

    def load(self, model: dict, binding: dict, experiment: dict):
        if self.model_id:
            raise BackendError("A worker-owned model is already loaded")
        kind = self.worker['backend']
        start = time.perf_counter()
        command_line = self.command_for(model,binding,experiment)
        alias = 'rpgbench-'+model['id']
        self.log_dir.mkdir(parents=True,exist_ok=True)
        self.model_id=alias
        try:
            if kind=='lmstudio':
                root = self.client.base_url.removesuffix('/v1')
                try:
                    inventory = self.client.request('GET',root+'/api/v1/models')
                except BackendError:
                    command([self.worker.get('lms_executable','lms'),'server','start','--port',str(urllib.parse.urlsplit(root).port or 1234)])
                    inventory = self.client.request('GET',root+'/api/v1/models')
                if any(m.get('loaded_instances') for m in inventory.get('models',[])):
                    self.model_id=''
                    raise BackendError("LM Studio already has loaded models. Unload them yourself before this dedicated worker run")
                output=command(command_line,self.worker.get('load_timeout_seconds',900))
                (self.log_dir/(model['id']+'.load.txt')).write_text(output,encoding='utf-8')
            elif kind=='llama_cpp':
                host=urllib.parse.urlsplit(self.client.base_url)
                with socket.socket() as sock:
                    if sock.connect_ex((host.hostname,host.port or 8080))==0:
                        raise BackendError("Server port is already in use; refusing to control an unrelated process")
                self.log_file=(self.log_dir/(model['id']+'.load.txt')).open('w',encoding='utf-8')
                env=dict(os.environ,CUDA_VISIBLE_DEVICES=self.gpu['uuid'])
                self.process=subprocess.Popen(command_line,stdout=self.log_file,stderr=subprocess.STDOUT,env=env)
            else:
                raise BackendError("Unsupported backend")
            deadline=time.monotonic()+self.worker.get('load_timeout_seconds',900)
            while True:
                if self.process and self.process.poll() is not None:
                    raise BackendError("llama-server exited during load; inspect the local load log")
                try:
                    ids={m['id'] for m in self.client.models().get('data',[])}
                    if alias in ids:
                        break
                except BackendError:
                    pass
                if time.monotonic()>deadline:
                    raise BackendError("Model did not become ready under the requested alias")
                time.sleep(0.5)
            self.load_metadata={'load_seconds':time.perf_counter()-start,'command':command_line,
                                'requested_gpu_offload':self.worker.get('gpu_offload','max'),
                                'full_gpu_residency_verified':False,'cache_policy':'backend_default_uncontrolled'}
        except BaseException:
            try:
                self.unload()
            except Exception:
                pass  # Preserve the original load error; never report cleanup as the root cause.
            raise

    def generate(self,messages,settings,seed):
        return self.client.generate(self.model_id,messages,settings,seed,self.worker.get('extra_body',{}))

    def unload(self):
        try:
            if self.process:
                self.process.terminate()
                try:self.process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.process.kill();self.process.wait(timeout=15)
            elif self.model_id and self.worker['backend']=='lmstudio':
                command([self.worker.get('lms_executable','lms'),'unload',self.model_id])
        finally:
            self.model_id=''
            self.process=None
            if self.log_file:
                self.log_file.close();self.log_file=None
