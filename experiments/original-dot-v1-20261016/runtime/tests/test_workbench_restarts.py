import contextlib
import json
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from workbench.controller import Controller
from workbench.domain import write_json,read_json
from workbench.restarts import UpdateCoordinator,consume_request
from workbench.unity import make_script
from test_unity_script import BASH
ROOT=Path(__file__).resolve().parents[1]

class RestartTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.app=Controller(self.root,True)
        self.path=self.app.data/'resume-after-update.json'
    def test_default_never_starts_run(self):self.assertFalse(consume_request(self.app))
    def test_valid_request_consumed_once(self):
        write_json(self.path,{'operation':'run','created_at':100,'restart_count':1})
        self.assertTrue(consume_request(self.app,lambda:101));self.assertEqual(self.app.automatic_restart_count,1)
        self.assertFalse(consume_request(self.app));self.assertFalse(self.path.exists())
    def test_stale_or_invalid_request_does_not_execute(self):
        for value in [{},{'operation':'shell','created_at':100,'restart_count':1},
                      {'operation':'run','created_at':100,'restart_count':4},
                      {'operation':'run','created_at':0,'restart_count':1}]:
            write_json(self.path,value);self.assertFalse(consume_request(self.app,lambda:1000))
    def test_coordinator_only_closes_after_operation(self):
        closed=threading.Event()
        class Server:
            app=self.app;exit_requested=False
            def close_all(s):closed.set()
        server=Server();coordinator=UpdateCoordinator(server,.01)
        self.app.operation.acquire();self.app.restart_required=True;coordinator.start()
        self.assertFalse(closed.wait(.05));self.app.operation.release()
        self.assertTrue(closed.wait(2));coordinator.thread.join(2)
        self.assertTrue(server.exit_requested);self.assertEqual(read_json(self.path)['operation'],'run')
    def test_user_stop_cancels_auto_resume(self):
        class Server:
            app=self.app;exit_requested=False
            def close_all(s):raise AssertionError('Must not restart after Stop')
        self.app.restart_required=True;self.app.cancel_event.set()
        c=UpdateCoordinator(Server(),.01).start();c.thread.join(1)
        self.assertFalse(c.thread.is_alive());self.assertFalse(self.path.exists())
    def test_restart_loop_is_bounded(self):
        class Server:
            app=self.app;exit_requested=False
            def close_all(s):raise AssertionError('No fourth restart')
        self.app.automatic_restart_count=3;self.app.restart_required=True
        c=UpdateCoordinator(Server(),.01).start();c.thread.join(1)
        self.assertEqual(self.app.state,'error');self.assertFalse(self.path.exists())
    def test_restart_starts_saved_run_once(self):
        class Server:
            app=self.app;exit_requested=False
        write_json(self.path,{'operation':'run','created_at':time.time(),'restart_count':1})
        with patch.object(self.app,'start') as start:
            c=UpdateCoordinator(Server(),.01).start();start.assert_called_once_with('run');c.stop.set();c.thread.join(1)
    def test_unity_constraint_and_signal_template(self):
        self.assertIn('--constraint=titanx',make_script('12'))
        self.assertIn('--constraint=v100&vram32',make_script('32'))
        self.assertIn('--signal=B:USR1@60',make_script('16'))
        self.assertIn('.venv-workbench/bin/python',make_script('16'))
        self.assertIn('kill -USR1',make_script('16'))
    @unittest.skipUnless(BASH,'No working Bash; shell checks also run on Linux')
    def test_generated_slurm_shell_syntax(self):
        import subprocess
        for tier in ['8','11','12','16','24','32','40','48','80']:
            result=subprocess.run([BASH,'-n'],input=make_script(tier),text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
