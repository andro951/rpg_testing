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
        (self.root/'.gitignore').write_text((Path(__file__).resolve().parents[1]/'.gitignore').read_text())
        (self.root/'models.json').write_text('[]\n')
        git(self.root,'add','.');git(self.root,'commit','-m','init');git(self.root,'push','-u','origin','HEAD')
    def test_clean_pull(self):self.assertFalse(pull(self.root))
    def test_machine_local_models_do_not_dirty_pull(self):
        (self.root/'models.json').write_text('[1]')
        self.assertFalse(pull(self.root));self.assertEqual((self.root/'models.json').read_text(),'[1]')
        self.assertEqual(git(self.root,'ls-files','--','models.json'),'')
    def test_dirty_nonconflicting_pull_preserves_local_edit(self):
        tracked=self.root/'tracked.txt';tracked.write_text('base')
        git(self.root,'add','tracked.txt');git(self.root,'commit','-m','add tracked');git(self.root,'push')
        peer=self.root.parent/'peer';git(self.root.parent,'clone',str(self.remote),str(peer))
        git(peer,'config','user.email','peer@example.invalid');git(peer,'config','user.name','Peer')
        tracked.write_text('local edit')
        (peer/'remote.txt').write_text('remote change')
        git(peer,'add','remote.txt');git(peer,'commit','-m','remote nonconflict');git(peer,'push')
        self.assertTrue(pull(self.root))
        self.assertEqual(tracked.read_text(),'local edit')
        self.assertEqual((self.root/'remote.txt').read_text(),'remote change')
        self.assertIn('tracked.txt',git(self.root,'status','--porcelain'))

    def test_dirty_conflicting_pull_aborts_and_preserves_local_edit(self):
        tracked=self.root/'conflict.txt';tracked.write_text('base')
        git(self.root,'add','conflict.txt');git(self.root,'commit','-m','add conflict');git(self.root,'push')
        peer=self.root.parent/'peer-conflict';git(self.root.parent,'clone',str(self.remote),str(peer))
        git(peer,'config','user.email','peer@example.invalid');git(peer,'config','user.name','Peer')
        tracked.write_text('local edit')
        (peer/'conflict.txt').write_text('remote edit')
        git(peer,'add','conflict.txt');git(peer,'commit','-m','remote conflict');git(peer,'push')
        before=git(self.root,'rev-parse','HEAD')
        with self.assertRaises(RuntimeError) as cm:pull(self.root)
        self.assertIn('local changes',str(cm.exception).lower())
        self.assertEqual(git(self.root,'rev-parse','HEAD'),before)
        self.assertEqual(tracked.read_text(),'local edit')

    def test_save_only_test_config(self):
        (self.root/'models.json').write_text('[1]');(self.root/'private.txt').write_text('private')
        (self.root/'test_specs').mkdir();(self.root/'test_specs/local.json').write_text('{"ok":true}')
        save_configuration(self.root)
        self.assertEqual(git(self.root,'show','HEAD:test_specs/local.json'),'{"ok":true}')
        self.assertEqual(git(self.root,'ls-files','--','models.json'),'');self.assertEqual((self.root/'models.json').read_text(),'[1]')
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
