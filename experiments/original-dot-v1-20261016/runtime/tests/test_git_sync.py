import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from rpgbench.git_sync import ResultPublisher, git, sync_source


class GitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name);self.remote=root/'remote.git';self.source=root/'source'
        subprocess.run(['git','init','--bare',str(self.remote)],check=True,capture_output=True)
        subprocess.run(['git','clone',str(self.remote),str(self.source)],check=True,capture_output=True)
        git(self.source,'config','user.name','Synthetic Test')
        git(self.source,'config','user.email','test@example.invalid')
        git(self.source,'checkout','-b','main')
        (self.source/'.gitignore').write_text('.worker_results/\nresults/\n')
        (self.source/'README.md').write_text('test repo\n')
        git(self.source,'add','.');git(self.source,'commit','-m','initial')
        git(self.source,'push','-u','origin','main')

    def tearDown(self):self.temp.cleanup()

    def test_clean_sync_and_dirty_refusal(self):
        before=git(self.source,'rev-parse','HEAD').stdout.strip()
        self.assertEqual(sync_source(self.source),before)
        (self.source/'README.md').write_text('uncommitted')
        with self.assertRaises(RuntimeError):sync_source(self.source)
        self.assertEqual((self.source/'README.md').read_text(),'uncommitted')

    def test_results_publish_and_reopen(self):
        main=git(self.source,'rev-parse','HEAD').stdout.strip()
        p=ResultPublisher(self.source,'desktop-test',0)
        (p.output/'result.json').write_text('{"synthetic":true}')
        self.assertTrue(p.flush(force=True))
        self.assertEqual(git(self.source,'rev-parse','HEAD').stdout.strip(),main)
        self.assertEqual(git(self.source,'show','origin/results/desktop-test:results/desktop-test/result.json').stdout,'{"synthetic":true}')
        p2=ResultPublisher(self.source,'desktop-test',0)
        self.assertTrue((p2.output/'result.json').exists())

    def test_unrelated_staging_blocks_publish(self):
        p=ResultPublisher(self.source,'worker',0)
        (p.path/'README.md').write_text('unrelated edit')
        git(p.path,'add','README.md')
        self.assertFalse(p.flush(force=True));self.assertTrue(p.errors)

    def test_invalid_worker_names(self):
        for name in ['../../main','worker/a','bad space','']:
            with self.subTest(name=name),self.assertRaises(ValueError):ResultPublisher(self.source,name)

if __name__=='__main__':unittest.main()
