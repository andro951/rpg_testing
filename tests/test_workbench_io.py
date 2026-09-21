import hashlib
import io
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from workbench.downloads import download_model, HTTPSOnly
from workbench.workflows import Cancelled
from workbench.gitops import git, pull, save_configuration, Publisher

class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.data=b'GGUF'+struct.pack('<IQQ',3,0,0);self.cancel=threading.Event()
        self.model={'id':'m','repo_id':'publisher/model','files':['test.gguf'],'sha256':{'test.gguf':hashlib.sha256(self.data).hexdigest()}}
    def opener(self,req,timeout):
        self.assertTrue(req.full_url.startswith('https://huggingface.co/publisher/model/resolve/main/'))
        obj=io.BytesIO(self.data);obj.headers={'Content-Length':str(len(self.data))};return obj
    def test_download_verified(self):
        download_model(self.model,self.root,self.cancel,opener=self.opener)
        self.assertEqual((self.root/'publisher/model/test.gguf').read_bytes(),self.data)
    def test_no_overwrite_verified_existing(self):
        download_model(self.model,self.root,self.cancel,opener=self.opener)
        download_model(self.model,self.root,self.cancel,opener=lambda *a,**k:self.fail('Must not redownload'))
    def test_mismatch_not_installed(self):
        self.model['sha256']['test.gguf']='b'*64
        with self.assertRaises(ValueError):download_model(self.model,self.root,self.cancel,opener=self.opener)
        self.assertEqual(list(self.root.rglob('*.gguf')),[]);self.assertEqual(list(self.root.rglob('*.partial')),[])
    def test_cancel_no_install(self):
        self.cancel.set()
        with self.assertRaises(Cancelled):download_model(self.model,self.root,self.cancel,opener=self.opener)
    def test_bad_file_never_installed(self):
        self.data=b'not a model';self.model.pop('sha256')
        with self.assertRaises(ValueError):download_model(self.model,self.root,self.cancel,opener=self.opener)
    def test_path_traversal_rejected(self):
        self.model['files']=['../bad.gguf']
        with self.assertRaises(ValueError):download_model(self.model,self.root,self.cancel)
    def test_insecure_redirect_rejected(self):
        with self.assertRaises(ValueError):HTTPSOnly().redirect_request(None,None,302,'',{},'http://insecure/test')

class GitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name)
        self.remote=base/'remote.git';self.remote.mkdir();git(self.remote,'init','--bare')
        self.root=base/'repo';git(base,'clone',str(self.remote),str(self.root))
        git(self.root,'config','user.email','test@example.invalid');git(self.root,'config','user.name','Test')
        (self.root/'.gitignore').write_text('.local/\n')
        (self.root/'models.json').write_text('[]\n')
        git(self.root,'add','.');git(self.root,'commit','-m','init');git(self.root,'push','-u','origin','HEAD')
    def test_clean_pull(self):self.assertFalse(pull(self.root))
    def test_dirty_pull_refused(self):
        (self.root/'models.json').write_text('[1]')
        with self.assertRaises(RuntimeError):pull(self.root)
        self.assertEqual((self.root/'models.json').read_text(),'[1]')
    def test_save_only_config(self):
        (self.root/'models.json').write_text('[1]');(self.root/'private.txt').write_text('private')
        save_configuration(self.root)
        self.assertEqual(git(self.root,'show','HEAD:models.json'),'[1]')
        self.assertIn('private.txt',git(self.root,'status','--porcelain'))
    def test_refuse_unrelated_staged(self):
        (self.root/'secret').write_text('secret');git(self.root,'add','secret')
        with self.assertRaises(RuntimeError):save_configuration(self.root)
    def test_publish_results_not_credentials(self):
        data=self.root/'.local/workbench';(data/'results/m').mkdir(parents=True);(data/'logs').mkdir()
        (data/'results/m/c.json').write_text('{"status":"completed"}')
        (data/'settings.json').write_text('SECRET')
        p=Publisher(self.root,data,'unit-worker');p.flush()
        files=git(p.checkout,'ls-tree','-r','--name-only','HEAD')
        self.assertIn('workbench_results/unit-worker/results/m/c.json',files)
        self.assertNotIn('settings.json',files)
        (data/'results/m/c.json').unlink();p.flush()
        self.assertNotIn('results/m/c.json',git(p.checkout,'ls-tree','-r','--name-only','HEAD'))
if __name__=='__main__':unittest.main()
