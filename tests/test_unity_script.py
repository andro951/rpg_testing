import os
import shutil
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('bash'), 'Bash is not installed on this host')
class UnityScriptTests(unittest.TestCase):
    def test_shell_syntax(self):
        p=subprocess.run(['bash','-n',str(ROOT/'scripts/unity_job.sh')],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_refuses_login_node(self):
        env=dict(os.environ);env.pop('SLURM_JOB_ID',None)
        p=subprocess.run(['bash',str(ROOT/'scripts/unity_job.sh')],env=env,capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('inside a Slurm allocation',p.stderr)

if __name__=='__main__':unittest.main()
