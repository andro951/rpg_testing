import copy
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from rpgbench.backends import BackendError, HTTPClient, ManagedBackend, MockBackend, artifact_info, select_gpu
from rpgbench.core import PIPELINES, ResultStore, canonical, read_json
from rpgbench.runner import code_digest, execute_case, make_case_id, run_suite
ROOT=Path(__file__).resolve().parents[1]


class StubHandler(BaseHTTPRequestHandler):
    last_body=None
    def log_message(self,*args):pass
    def do_GET(self):
        data=json.dumps({'data':[{'id':'stub'}]}).encode()
        self.send_response(200);self.end_headers();self.wfile.write(data)
    def do_POST(self):
        type(self).last_body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        data=json.dumps({'choices':[{'message':{'content':'[]'},'finish_reason':'stop'}],
                         'usage':{'prompt_tokens':5,'completion_tokens':2}}).encode()
        self.send_response(200);self.end_headers();self.wfile.write(data)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.models=read_json(ROOT/'models.json')
        self.exp=read_json(ROOT/'experiment.json')
        self.fixtures=[read_json(p) for p in sorted((ROOT/'fixtures').glob('*.json'))]
        self.worker={'backend':'mock','backend_version':'mock-v1'}
        self.gpu={'name':'SIMULATED GPU','total_gib':8,'driver':'none','uuid':'mock'}

    def test_four_pipelines(self):
        b=MockBackend()
        for fixture in self.fixtures:
            for pipeline in PIPELINES:
                with self.subTest(fixture=fixture['id'],pipeline=pipeline):
                    r=execute_case(b,fixture,pipeline,self.exp,42)
                    self.assertTrue(r['score']['exact_match'])
                    self.assertEqual(len(r['calls']),2 if pipeline.startswith('analyze') else 1)

    def test_scheduler_load_once_and_resume(self):
        with tempfile.TemporaryDirectory() as d:
            b=MockBackend()
            s=run_suite(ROOT,self.models,self.exp,self.fixtures,self.worker,Path(d),self.gpu,b)
            self.assertEqual(s['completed_now'],24)
            self.assertEqual(s['models_loaded'],3)
            before=b.calls
            again=run_suite(ROOT,self.models,self.exp,self.fixtures,self.worker,Path(d),self.gpu,b)
            self.assertEqual(again['already_complete'],24)
            self.assertEqual(again['models_loaded'],0)
            self.assertEqual(b.calls,before)

    def test_completed_wrong_answers_are_not_retried(self):
        class Wrong(MockBackend):
            def generate(self,*args):
                self.calls+=1
                return {'text':'[]','finish_reason':'stop','raw':{},'wall_seconds':0}
        with tempfile.TemporaryDirectory() as d:
            b=Wrong()
            s=run_suite(ROOT,self.models[:1],self.exp,self.fixtures,self.worker,Path(d),self.gpu,b)
            self.assertEqual(s['completed_now'],8)
            before=b.calls
            s=run_suite(ROOT,self.models[:1],self.exp,self.fixtures,self.worker,Path(d),self.gpu,b)
            self.assertEqual(b.calls,before)

    def test_transport_retries_are_bounded(self):
        class Broken(MockBackend):
            def generate(self,*args):raise BackendError('synthetic timeout')
        e=dict(self.exp,warmup=False,pipelines=['direct_json_patch'])
        with tempfile.TemporaryDirectory() as d:
            b=Broken()
            s=run_suite(ROOT,self.models[:1],e,self.fixtures,self.worker,Path(d),self.gpu,b)
            self.assertEqual(s['errors'],4)
            s=run_suite(ROOT,self.models[:1],e,self.fixtures,self.worker,Path(d),self.gpu,b)
            self.assertEqual(s['exhausted'],2);self.assertEqual(s['models_loaded'],0)

    def test_truncated_model_response_is_failure(self):
        class Truncated(MockBackend):
            def generate(self,*args):return {'text':'[]','finish_reason':'length','raw':{},'wall_seconds':0}
        r=execute_case(Truncated(),self.fixtures[0],'direct_json_patch',self.exp,42)
        self.assertFalse(r['score']['valid']);self.assertFalse(r['score']['exact_match'])

    def test_identity_changes_only_for_relevant_settings(self):
        args=[self.models[0],{'sha':'one'},self.fixtures[0],'direct_json_patch',self.exp,42,0,{'backend':'x'},'code1']
        first=make_case_id(*args)
        for i,value in [(1,{'sha':'two'}),(3,'analyze_json_patch'),(5,43),(6,1),(7,{'backend':'y'}),(8,'code2')]:
            a=copy.deepcopy(args);a[i]=value;self.assertNotEqual(make_case_id(*a),first)
        a=copy.deepcopy(args);a[4]['max_attempts']=99
        self.assertEqual(make_case_id(*a),first)
        a=copy.deepcopy(args);a[4]['temperature']=0.7
        self.assertNotEqual(make_case_id(*a),first)

    def test_code_digest_ignores_results_docs(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'rpgbench').mkdir()
            (root/'rpgbench/a.py').write_text('x=1\n')
            before=code_digest(root)
            (root/'results').mkdir();(root/'results/x.json').write_text('{}')
            (root/'README.md').write_text('docs')
            self.assertEqual(code_digest(root),before)
            (root/'rpgbench/a.py').write_text('x=2\n')
            self.assertNotEqual(code_digest(root),before)

    def test_gpu_respects_allocated_device(self):
        csv='0, GPU-a, GTX 1080, 8192, 7000, 580\n1, GPU-b, A100, 81920, 80000, 580\n'
        self.assertEqual(select_gpu(csv,visible='1')['uuid'],'GPU-b')
        self.assertEqual(select_gpu(csv,selector='GPU-a')['total_gib'],8)
        for kw in [{},{'selector':'0','visible':'1'},{'visible':''},{'visible':'MIG-x'}]:
            with self.subTest(kw=kw),self.assertRaises(BackendError):select_gpu(csv,**kw)

    def test_artifacts_require_all_exact_shards(self):
        m={'id':'x','files':['one.gguf','two.gguf']}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'one.gguf').write_bytes(b'GGUFone');(p/'two.gguf').write_bytes(b'GGUFtwo')
            w={'model_bindings':{'x':{'files':[str(p/'one.gguf')]}}}
            with self.assertRaises(BackendError):artifact_info(m,w)
            w['model_bindings']['x']['files'].append(str(p/'two.gguf'))
            info,_=artifact_info(m,w)
            self.assertEqual(len(info['files']),2)
            self.assertEqual(len(info['files'][0]['sha256']),64)

    def test_lmstudio_and_llama_load_commands(self):
        m=self.models[0];binding={'files':['Qwen3.5-2B-Q8_0.gguf'],'model_key':'exact-key'}
        with tempfile.TemporaryDirectory() as d:
            for kind in ['lmstudio','llama_cpp']:
                w={'backend':kind,'base_url':'http://127.0.0.1:1234/v1'}
                b=ManagedBackend(w,Path(d),self.gpu)
                cmd=b.command_for(m,binding,self.exp)
                self.assertIn('4096',cmd)
                self.assertIn('rpgbench-'+m['id'],cmd)
                if kind=='lmstudio':self.assertIn('max',cmd)
                else:self.assertIn('--no-context-shift',cmd)

    def test_http_client_smoke(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),StubHandler)
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            client=HTTPClient(f'http://127.0.0.1:{server.server_port}/v1')
            self.assertEqual(client.models()['data'][0]['id'],'stub')
            r=client.generate('stub',[{'role':'user','content':'Hello'}],self.exp,42)
            self.assertEqual(r['text'],'[]');self.assertGreaterEqual(r['wall_seconds'],0)
            self.assertIsNone(r['ttft_seconds']);self.assertIsNone(r['decode_tokens_per_second'])
            self.assertEqual(StubHandler.last_body['seed'],42)
            self.assertNotIn('Authorization',canonical(r))
        finally:server.shutdown();server.server_close();t.join()

    def test_remote_and_parameter_guards(self):
        with self.assertRaises(BackendError):HTTPClient('http://100.1.2.3:1234/v1')
        with self.assertRaises(BackendError):HTTPClient('http://user:secret@localhost:1234/v1')
        client=HTTPClient('http://127.0.0.1:1234/v1')
        with self.assertRaises(BackendError):client.generate('x',[],self.exp,42,{'seed':1})
        with self.assertRaises(BackendError):client.generate('x',[{'content':'x'*5000}],self.exp,42)

if __name__=='__main__':unittest.main()

class AdditionalTests(unittest.TestCase):
    def test_partial_analysis_is_preserved_on_transport_error(self):
        from rpgbench.runner import PipelineError
        class FailsSecond(MockBackend):
            def generate(self,*args):
                if self.calls:raise BackendError('patch request failed')
                return super().generate(*args)
        fixture=read_json(ROOT/'fixtures/time_only.json')
        with self.assertRaises(PipelineError) as cm:
            execute_case(FailsSecond(),fixture,'analyze_json_patch',read_json(ROOT/'experiment.json'),42)
        self.assertEqual(len(cm.exception.partial_calls),1)
        self.assertEqual(cm.exception.partial_calls[0]['stage'],'analysis')

    def test_bootstrap_lock_and_offline_plan(self):
        import subprocess, shutil
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)
            for item in ['rpgbench','fixtures','models.json','experiment.json','requirements.txt','run_worker.py']:
                src=ROOT/item
                if src.is_dir():shutil.copytree(src,target/item,ignore=shutil.ignore_patterns('__pycache__'))
                else:shutil.copy(src,target/item)
            p=subprocess.run([os.sys.executable,str(target/'run_worker.py'),'--no-sync','--skip-self-tests','--plan'],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertFalse((target/'.local/worker.lock').exists())
            (target/'.local/worker.lock').write_text('{"pid":123}')
            p=subprocess.run([os.sys.executable,str(target/'run_worker.py'),'--no-sync','--skip-self-tests','--plan'],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertTrue((target/'.local/worker.lock').exists())
