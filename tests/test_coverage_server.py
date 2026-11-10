"""Coverage APIs and shipped browser panel, without inference or remote jobs."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen,Request
from urllib.error import HTTPError
from workbench.controller import Controller
from workbench.server import WorkbenchServer
from optimization.coverage import save


class CoverageServerTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        self.app=Controller(self.root,demo=True)
        self.server=WorkbenchServer(('127.0.0.1',0),self.app)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.close)
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.state={'id':'coverage-fixture','status':'partial','message':'One submitted model remains queued.',
                    'workers':[{'id':'unity-a','kind':'unity','status':'queued','receipt':{'job_id':'123'}}]}
        save(self.root,self.state)

    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(5)

    def request(self,path,data=None):
        req=Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,
                    headers={'Content-Type':'application/json'} if data is not None else {})
        try:
            with urlopen(req,timeout=5) as response:return response.status,response.read()
        except HTTPError as response:return response.code,response.read()

    def test_status_api_returns_honest_partial_and_resume_uses_existing_id(self):
        code,raw=self.request('/api/coverage/list');self.assertEqual(code,200)
        self.assertEqual(json.loads(raw)['batches'][0]['status'],'partial')
        self.assertEqual(json.loads(self.request('/api/coverage?id=coverage-fixture')[1])['workers'][0]['receipt']['job_id'],'123')
        with patch.object(self.app,'start') as start:
            self.assertEqual(self.request('/api/coverage/resume',{'id':'coverage-fixture'})[0],202)
            start.assert_called_once_with('coverage',{'id':'coverage-fixture'})
        self.assertEqual(self.request('/api/coverage/resume',{'id':'coverage-fixture','replace_job':True})[0],400)

    def test_overview_loads_coverage_panel_from_frozen_static_assets(self):
        self.assertIn(b'/coverage.js',self.request('/')[1])
        code,raw=self.request('/coverage.js');self.assertEqual(code,200)
        self.assertIn(b'/api/coverage/list',raw)
        self.assertIn(b'Resume coverage',raw)

    def test_model_port_survives_saved_worker_configuration(self):
        self.app.settings['inference_port']=24321;self.app.save_settings()
        reloaded=Controller(self.root,demo=True)
        self.assertEqual(reloaded.settings['inference_port'],24321)
