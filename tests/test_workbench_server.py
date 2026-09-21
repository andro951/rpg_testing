import io
import json
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from workbench.controller import Controller
from workbench.server import WorkbenchServer
from workbench.domain import read_json

ROOT=Path(__file__).resolve().parents[1]

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);shutil.copytree(ROOT/'test_specs',self.root/'test_specs')
        shutil.copytree(ROOT/'examples',self.root/'examples')
        self.app=Controller(self.root,True);self.app.selftest=lambda:None
        self.server=WorkbenchServer(('127.0.0.1',0),self.app,'testing-key')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close);self.url=f'http://127.0.0.1:{self.server.server_port}'
    def close(self):
        self.app.control('stop')
        if self.app.thread:self.app.thread.join(5)
        self.server.shutdown();self.server.server_close();self.thread.join(5)
    def req(self,path,body=None,headers=None,auth=True):
        hs={'Authorization':'Bearer testing-key'} if auth else {}
        hs.update(headers or {})
        if body is not None:
            hs.setdefault('Content-Type','application/json');body=json.dumps(body).encode()
        request=urllib.request.Request(self.url+path,data=body,headers=hs)
        try:
            with urllib.request.urlopen(request,timeout=10) as r:return r.status,r.read(),dict(r.headers)
        except urllib.error.HTTPError as r:return r.code,r.read(),dict(r.headers)
    def wait(self):
        if self.app.thread:self.app.thread.join(10)
        self.assertFalse(self.app.operation.locked())
    def test_no_auth_no_state(self):self.assertEqual(self.req('/api/state',auth=False)[0],403)
    def test_bad_key(self):self.assertEqual(self.req('/api/state',headers={'Authorization':'Bearer wrong'})[0],403)
    def test_bad_origin(self):self.assertEqual(self.req('/api/run',{},headers={'Origin':'http://evil.example'})[0],403)
    def test_bad_host(self):self.assertEqual(self.req('/api/state',headers={'Host':'evil.example'})[0],403)
    def test_static_assets_no_token_leak(self):
        for path in ['/','/app.js','/style.css']:
            status,data,hs=self.req(path,auth=False);self.assertEqual(status,200);self.assertNotIn(b'testing-key',data)
            self.assertIn('Content-Security-Policy',hs)
    def test_no_public_binding(self):
        for host in ['0.0.0.0','192.168.1.1','8.8.8.8']:
            with self.assertRaises(ValueError):WorkbenchServer((host,0),self.app,'x')
    def test_json_content_type_required(self):self.assertEqual(self.req('/api/run',{},headers={'Content-Type':'text/plain'})[0],400)
    def test_preflight_does_not_run_model(self):
        self.assertEqual(self.req('/api/preflight',{})[0],202);self.wait()
        self.assertEqual(self.app.store.all(),[]);self.assertTrue(self.app.report['ready'])
    def test_run_resume_and_read_results(self):
        self.assertEqual(self.req('/api/run',{})[0],202);self.wait()
        rs=json.loads(self.req('/api/results')[1]);self.assertEqual(len(rs),8)
        self.req('/api/run',{});self.wait();self.assertEqual(self.app.completed_now,0)
    def test_export_and_summary(self):
        self.app.run();status,body,headers=self.req('/api/export')
        self.assertEqual(status,200);z=zipfile.ZipFile(io.BytesIO(body))
        self.assertIn('summary.csv',z.namelist());self.assertIn('summary.json',z.namelist())
        self.assertEqual(json.loads(self.req('/api/analysis')[1])['records'],8)
    def test_unknown_api(self):self.assertEqual(self.req('/api/exec',{'cmd':'whatever'})[0],404)
    def test_unsafe_test_id(self):
        test=read_json(self.root/'test_specs/time_only.json');test['id']='../oops'
        self.assertEqual(self.req('/api/test/save',{'test':test})[0],400)
    def test_edit_preserves_original_when_invalid(self):
        old=(self.root/'test_specs/time_only.json').read_bytes();test=json.loads(old);test['context_tokens']=2
        self.assertEqual(self.req('/api/test/save',{'test':test})[0],400)
        self.assertEqual((self.root/'test_specs/time_only.json').read_bytes(),old)
    def test_import_example_and_prevent_overwrite(self):
        self.assertEqual(self.req('/api/test/import-example',{'id':'cached_questions'})[0],200)
        self.assertEqual(self.req('/api/test/import-example',{'id':'cached_questions'})[0],400)
    def test_browse_is_host_side(self):
        from urllib.parse import quote
        status,body,_=self.req('/api/browse?path='+quote(str(self.root)))
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['path'],str(self.root))
    def test_pairing_requires_existing_auth(self):
        self.assertEqual(self.req('/api/pairing-key',auth=False)[0],403)
        self.assertEqual(json.loads(self.req('/api/pairing-key')[1])['key'],'testing-key')
    def test_busy_disk_read_blocked(self):
        self.app.operation.acquire()
        try:self.assertEqual(self.req('/api/results')[0],409)
        finally:self.app.operation.release()
    def test_unity_script_download(self):
        status,body,_=self.req('/api/unity-script?tier=16')
        self.assertEqual(status,200);self.assertIn(b'SLURM_JOB_ID',body)
        self.assertEqual(self.req('/api/unity-script?tier=evil')[0],400)
    def test_remote_enable_fails_cleanly_without_install(self):
        from unittest.mock import patch
        with patch('workbench.server.executable',return_value=None):self.assertEqual(self.req('/api/remote/enable',{})[0],400)
if __name__=='__main__':unittest.main()
