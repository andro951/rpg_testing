import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import launch_workbench

class FakeTransport:
    states=[]
    posts=[]
    def __init__(self,*a,**k):pass
    def request(self,path,body=None):
        if path=='/api/restart':
            type(self).posts.append((path,body));return {'ok':True}
        if not type(self).states:raise RuntimeError('no state')
        value=type(self).states.pop(0)
        if isinstance(value,Exception):raise value
        return value

class LauncherRestartTests(unittest.TestCase):
    def args(self):return SimpleNamespace(demo=False,no_browser=True)
    def setup_data(self,temp):
        data=Path(temp)/'.local/workbench';data.mkdir(parents=True);(data/'control.key').write_text('k');return data
    def test_matching_worker_reopens_without_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data=self.setup_data(temp)
            FakeTransport.states=[{'process_source_commit':'abc'}];FakeTransport.posts=[]
            with patch('workbench.backends.Transport',FakeTransport),patch('launch_workbench.current_head',return_value='abc'):
                self.assertEqual(launch_workbench.reopen_existing_worker(root,self.args(),data),0)
            self.assertEqual(FakeTransport.posts,[])
    def test_stale_worker_requests_restart_and_waits_for_exact_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data=self.setup_data(temp)
            FakeTransport.states=[{},RuntimeError('down'),{'process_source_commit':'new'}];FakeTransport.posts=[]
            with patch('workbench.backends.Transport',FakeTransport),patch('launch_workbench.current_head',return_value='new'),patch('time.sleep'):
                self.assertEqual(launch_workbench.reopen_existing_worker(root,self.args(),data),0)
            self.assertEqual(FakeTransport.posts,[('/api/restart',{})])
    def test_legacy_worker_restarts_even_when_git_head_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data=self.setup_data(temp)
            FakeTransport.states=[{}, {'process_source_commit':None}];FakeTransport.posts=[]
            with patch('workbench.backends.Transport',FakeTransport),patch('launch_workbench.current_head',return_value=None),patch('time.sleep'):
                self.assertEqual(launch_workbench.reopen_existing_worker(root,self.args(),data),0)
            self.assertEqual(FakeTransport.posts,[('/api/restart',{})])

if __name__=='__main__':unittest.main()
