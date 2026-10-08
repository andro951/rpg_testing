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

def configured_case_count(folder):
    tests=[read_json(p) for p in folder.glob('*.json')]
    return sum(t.get('repetitions',1)*sum(v.get('enabled',True) for v in t['variants']) for t in tests if t.get('enabled',True))

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);shutil.copytree(ROOT/'test_specs',self.root/'test_specs')
        shutil.copytree(ROOT/'examples',self.root/'examples')
        self.app=Controller(self.root,True);self.app.selftest=lambda:None
        self.server=WorkbenchServer(('127.0.0.1',0),self.app)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close);self.url=f'http://127.0.0.1:{self.server.server_port}'
    def close(self):
        self.app.control('stop')
        if self.app.thread:self.app.thread.join(5)
        self.server.shutdown();self.server.server_close();self.thread.join(5)
    def req(self,path,body=None,headers=None,auth=False):
        hs={'Authorization':'Bearer testing-key'} if auth else {}
        hs.update(headers or {})
        if body is not None:
            hs.setdefault('Content-Type','application/json');body=json.dumps(body).encode()
        request=urllib.request.Request(self.url+path,data=body,headers=hs)
        try:
            with urllib.request.urlopen(request,timeout=10) as r:return r.status,r.read(),dict(r.headers)
        except urllib.error.HTTPError as r:return r.code,r.read(),dict(r.headers)
    def wait(self):
        if self.app.thread:
            # The full 387-case demo writes evidence on Windows as well as Linux.
            self.app.thread.join(120)
            self.assertFalse(self.app.thread.is_alive(),'Workbench operation did not finish')
        self.assertFalse(self.app.operation.locked())
    def test_state_opens_without_a_key(self):
        status,body,_=self.req('/api/state')
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['control_access'],'private_network')
    def test_obsolete_authorization_header_is_not_required(self):
        self.assertEqual(self.req('/api/state',headers={'Authorization':'Bearer wrong'})[0],200)
    def test_bad_origin(self):self.assertEqual(self.req('/api/run',{},headers={'Origin':'http://evil.example'})[0],403)
    def test_bad_host(self):self.assertEqual(self.req('/api/state',headers={'Host':'evil.example'})[0],403)
    def test_running_server_freezes_static_assets_to_loaded_code(self):
        original=self.server.static_assets['/app.js']
        self.server.static_assets['/app.js']=b'FROZEN-COMPATIBLE-UI'
        try:
            status,data,_=self.req('/app.js',auth=False)
            self.assertEqual(status,200);self.assertEqual(data,b'FROZEN-COMPATIBLE-UI')
        finally:self.server.static_assets['/app.js']=original
    def test_state_exposes_loaded_source_commit(self):
        state=json.loads(self.req('/api/state')[1])
        self.assertIn('process_source_commit',state)
    def test_static_assets_no_token_leak(self):
        for path in ['/','/app.js','/style.css']:
            status,data,hs=self.req(path,auth=False);self.assertEqual(status,200);self.assertNotIn(b'testing-key',data)
            self.assertIn('Content-Security-Policy',hs)
    def test_no_public_binding(self):
        for host in ['0.0.0.0','192.168.1.1','8.8.8.8']:
            with self.assertRaises(ValueError):WorkbenchServer((host,0),self.app)
    def test_json_content_type_required(self):self.assertEqual(self.req('/api/run',{},headers={'Content-Type':'text/plain'})[0],400)
    def test_preflight_does_not_run_model(self):
        self.assertEqual(self.req('/api/preflight',{})[0],202);self.wait()
        self.assertEqual(self.app.store.all(),[]);self.assertTrue(self.app.report['ready'])
    def test_targeted_run_options_and_authorization(self):
        self.assertEqual(self.req('/api/run-options',auth=False)[0],200)
        status,data,_=self.req('/api/run-options');self.assertEqual(status,200)
        options=json.loads(data);self.assertEqual(options['models'][0]['id'],'demo-2b')
        self.assertNotIn('expected_state',str(options))
    def test_targeted_api_runs_and_resumes_only_one_case(self):
        scope={'model_id':'demo-2b','test_id':'time_only','variant_id':'direct_json_patch'}
        self.assertEqual(self.req('/api/preflight',{'selection':scope})[0],202);self.wait()
        self.assertEqual(self.app.report['plan']['pending'],1);self.assertEqual(self.app.store.all(),[])
        self.assertEqual(self.req('/api/run',{'selection':scope})[0],202);self.wait()
        self.assertEqual(len(self.app.store.all()),1);self.assertEqual(self.app.report['selection'],scope)
        self.req('/api/run',{'selection':scope});self.wait();self.assertEqual(self.app.completed_now,0)
    def test_targeted_api_rejects_bad_scope_without_running(self):
        for body in [{'selection':{}},{'model_id':'demo-2b'},{'selection':{'model_id':'unknown'}},
                     {'selection':{'model_id':'demo-2b','test_id':'missing'}}]:
            self.assertEqual(self.req('/api/run',body)[0],400)
        self.assertEqual(self.app.store.all(),[]);self.assertFalse(self.app.operation.locked())
    def test_targeted_options_refuse_disk_reads_while_busy(self):
        self.app.operation.acquire()
        try:self.assertEqual(self.req('/api/run-options')[0],409)
        finally:self.app.operation.release()
    def test_run_resume_and_read_results(self):
        self.assertEqual(self.req('/api/run',{})[0],202);self.wait()
        rs=json.loads(self.req('/api/results')[1]);self.assertEqual(len(rs),configured_case_count(self.root/'test_specs'))
        self.req('/api/run',{});self.wait();self.assertEqual(self.app.completed_now,0)
    def test_export_and_summary(self):
        self.app.run();status,body,headers=self.req('/api/export')
        self.assertEqual(status,200);z=zipfile.ZipFile(io.BytesIO(body))
        self.assertIn('summary.csv',z.namelist());self.assertIn('summary.json',z.namelist())
        self.assertEqual(json.loads(self.req('/api/analysis')[1])['records'],configured_case_count(self.root/'test_specs'))
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
    def test_native_model_folder_picker_returns_host_path(self):
        from unittest.mock import patch
        with patch('workbench.server.select_directory',return_value=str(self.root)):
            status,body,_=self.req('/api/picker/models',{'initial':''})
        self.assertEqual(status,200);self.assertEqual(Path(json.loads(body)['path']).resolve(),self.root.resolve())
    def test_native_picker_is_not_opened_during_active_operation(self):
        from unittest.mock import patch
        self.app.operation.acquire()
        try:
            with patch('workbench.server.select_directory') as picker:
                self.assertEqual(self.req('/api/picker/models',{'initial':''})[0],409)
                picker.assert_not_called()
        finally:self.app.operation.release()
    def test_native_picker_cancel_is_not_an_error(self):
        from unittest.mock import patch
        with patch('workbench.server.select_directory',return_value=None):
            status,body,_=self.req('/api/picker/models',{'initial':''})
        self.assertEqual(status,200);self.assertTrue(json.loads(body)['cancelled'])
    def test_pairing_endpoint_and_controls_are_removed(self):
        self.assertEqual(self.req('/api/pairing-key')[0],404)
        html=self.req('/')[1]
        for marker in (b'id="pairing"',b'id="login"',b'Pairing key'):
            self.assertNotIn(marker,html)
        self.assertFalse((self.app.data/'control.key').exists())
    def test_same_origin_post_needs_no_key(self):
        status,_,_=self.req('/api/settings',{'publish_results':False},headers={'Origin':self.url})
        self.assertEqual(status,200)
    def test_null_and_foreign_origins_are_rejected_without_a_key(self):
        for origin in ('null','http://evil.example','https://'+self.url.split('://')[1]):
            self.assertEqual(self.req('/api/control',{'action':'stop'},headers={'Origin':origin})[0],403)
    def test_tailnet_client_access_and_other_network_clients(self):
        from types import SimpleNamespace
        from workbench.server import Handler,Forbidden
        handler=Handler.__new__(Handler)
        handler.server=SimpleNamespace(server_address=('100.101.102.103',),server_port=8765)
        handler.headers={'Host':'100.101.102.103:8765','Origin':'http://100.101.102.103:8765'}
        for peer in ('100.64.0.1','100.127.255.254','127.0.0.1'):
            handler.client_address=(peer,12345);handler.authorize()
        for peer in ('192.168.1.10','8.8.8.8','100.63.255.255','100.128.0.0'):
            handler.client_address=(peer,12345)
            with self.assertRaises(Forbidden):handler.authorize()
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
    def test_remote_enable_uses_only_the_detected_tailscale_address(self):
        from unittest.mock import patch,Mock
        remote=Mock()
        with patch('workbench.server.executable',return_value='tailscale'),patch('workbench.server.command',return_value='100.101.102.103\n'),patch('workbench.server.WorkbenchServer',return_value=remote) as factory:
            status,body,_=self.req('/api/remote/enable',{})
        self.server.remote_server=None
        self.assertEqual(status,200)
        factory.assert_called_once_with(('100.101.102.103',self.server.server_port),self.app)
        info=json.loads(body);self.assertEqual(info['url'],f'http://100.101.102.103:{self.server.server_port}/')
        self.assertNotIn('pairing',info['note']);self.assertTrue(self.app.settings['remote_enabled'])
    def test_remote_enable_rejects_an_unexpected_interface(self):
        from unittest.mock import patch
        with patch('workbench.server.executable',return_value='tailscale'),patch('workbench.server.command',return_value='192.168.1.10\n'),patch('workbench.server.WorkbenchServer') as factory:
            self.assertEqual(self.req('/api/remote/enable',{})[0],400)
            factory.assert_not_called()
if __name__=='__main__':unittest.main()
