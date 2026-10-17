"""Unity shell guards need a working Bash, not Windows' unconfigured WSL shim."""
import os
import shutil
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def working_bash():
    candidates=[]
    if os.name=='nt':
        candidates.append(str(Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Git/bin/bash.exe'))
    candidates.append(shutil.which('bash'))
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():continue
        try:
            p=subprocess.run([candidate,'-c','printf bash-ready'],capture_output=True,text=True,timeout=10)
            if p.returncode==0 and p.stdout=='bash-ready':return candidate
        except (OSError,subprocess.SubprocessError):continue
    return None

BASH=working_bash()
@unittest.skipUnless(BASH, 'No working Bash on this host; Unity guards are also tested on Linux')
class UnityScriptTests(unittest.TestCase):
    def test_shell_syntax(self):
        p=subprocess.run([BASH,'-n',(ROOT/'scripts/unity_job.sh').as_posix()],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr or p.stdout)
    def test_refuses_login_node(self):
        env=dict(os.environ);env.pop('SLURM_JOB_ID',None)
        p=subprocess.run([BASH,(ROOT/'scripts/unity_job.sh').as_posix()],env=env,capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('inside a Slurm allocation',p.stderr)
    def test_new_generated_job_syntax_and_allocation_guard(self):
        from workbench.unity import make_script,PROFILES
        env=dict(os.environ);env.pop('SLURM_JOB_ID',None)
        for tier in PROFILES:
            script=make_script(tier)
            p=subprocess.run([BASH,'-n'],input=script,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run([BASH],input=script,env=env,capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn('Submit through Slurm',p.stderr)
if __name__=='__main__':unittest.main()
