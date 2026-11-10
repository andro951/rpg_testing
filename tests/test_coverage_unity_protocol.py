"""Execute the real remote submission protocol against simulated Slurm responses."""
import base64
import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from optimization.coverage_unity import SUBMIT, evidence_root


class SubmissionProtocolTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(dir=evidence_root(Path(tempfile.gettempdir())));self.addCleanup(temp.cleanup);self.root=Path(temp.name)/'remote'
        raw=io.BytesIO()
        with tarfile.open(fileobj=raw,mode='w:gz') as archive:
            data=b'#!/bin/bash\n';info=tarfile.TarInfo('coverage.sbatch');info.size=len(data);archive.addfile(info,io.BytesIO(data))
        self.packet={'root':str(self.root),'token':'rpg-exact-token','manifest':{'suite_digest':'suite','model_id':'model'},
                     'archive':base64.b64encode(raw.getvalue()).decode()}

    def execute(self,run):
        out=io.StringIO()
        with patch('sys.stdin',io.StringIO(json.dumps(self.packet))),patch('sys.stdout',out),patch.dict(os.environ,{'USER':'test-user'}),patch('subprocess.run',side_effect=run):
            try:exec(compile(SUBMIT,'remote-submission','exec'),{})
            except SystemExit:pass
        return json.loads(out.getvalue())

    def test_first_submit_and_repeated_resume_return_one_same_job(self):
        calls=[]
        def run(args,**kw):calls.append(args);return SimpleNamespace(returncode=0,stdout='123\n',stderr='')
        first=self.execute(run);again=self.execute(run)
        self.assertEqual(first,again);self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][0],'sbatch');self.assertEqual(first['job_id'],'123')

    def test_lost_acknowledgement_adopts_exact_comment_without_resubmission(self):
        self.execute(lambda *a,**k:SimpleNamespace(returncode=0,stdout='123\n',stderr=''))
        (self.root/'job.json').unlink()
        calls=[]
        def run(args,**kw):
            calls.append(args);return SimpleNamespace(returncode=0,stdout='123|rpg-exact-token\n',stderr='')
        self.assertEqual(self.execute(run)['job_id'],'123')
        self.assertNotIn('sbatch',[c[0] for c in calls])

    def test_ambiguous_or_absent_acknowledgement_blocks_without_resubmitting(self):
        self.execute(lambda *a,**k:SimpleNamespace(returncode=0,stdout='123\n',stderr=''))
        (self.root/'job.json').unlink()
        for response in ('','123|rpg-exact-token\n124|rpg-exact-token\n'):
            with self.subTest(response=response):
                with self.assertRaisesRegex(RuntimeError,'No resubmission'):
                    self.execute(lambda *a,**k:SimpleNamespace(returncode=0,stdout=response,stderr=''))

    def test_failed_submission_retains_exclusive_intent(self):
        with self.assertRaisesRegex(RuntimeError,'intent retained'):
            self.execute(lambda *a,**k:SimpleNamespace(returncode=1,stdout='',stderr='quota'))
        self.assertTrue((self.root/'submission-intent.json').exists())
        self.assertFalse((self.root/'job.json').exists())

    def test_conflicting_frozen_manifest_is_rejected(self):
        self.execute(lambda *a,**k:SimpleNamespace(returncode=0,stdout='123\n',stderr=''))
        self.packet['manifest']['suite_digest']='other'
        with self.assertRaisesRegex(RuntimeError,'manifest conflict'):self.execute(lambda *a,**k:None)

    def test_complete_archive_is_checked_and_collected_before_completion(self):
        from optimization import coverage_unity as unity
        from workbench.domain import ResultStore
        import hashlib
        state_id='b'*64;mid='qwen35-27b-iq2_m-bartowski'
        app=SimpleNamespace(root=self.root/'app');(app.root/'coverage_results'/state_id).mkdir(parents=True)
        store=ResultStore(self.root/'remote-results');cid='a'*64
        p=store.save({'case_id':cid,'model_id':mid,'status':'completed','simulated':True})
        raw=io.BytesIO()
        with tarfile.open(fileobj=raw,mode='w:gz') as archive:archive.add(p,arcname='results/'+mid+'/'+cid+'.json')
        data=raw.getvalue();checksum=hashlib.sha256(p.read_bytes()).hexdigest()
        worker={'id':'unity-'+mid,'model_id':mid,'kind':'unity',
            'receipt':{'job_id':'123','root':'/remote','suite_digest':'suite','model_id':mid,'source_digest':'source'}}
        result={'status':'completed','model_id':mid,'suite_digest':'suite','source_digest':'source',
            'rows':[{'model_id':mid,'status':'completed','complete':1,'required':1,
                     'evidence':[{'path':'/remote/repo/results/'+mid+'/'+cid+'.json','sha256':checksum}]}]}
        def transport(worker,code,payload=None,binary=False):
            return data if binary else {'queue':'','repo/coverage-worker-status.json':result}
        with patch.object(unity,'ssh',side_effect=transport),patch.object(unity,'bundle') as bundle:
            unity.advance(app,{'id':state_id,'suite_digest':'suite'},worker)
        bundle.assert_not_called();self.assertEqual(worker['status'],'completed')
        self.assertEqual(worker['rows'][0]['complete'],1)
        collected=Path(worker['rows'][0]['evidence'][0]['path'])
        self.assertEqual(hashlib.sha256(collected.read_bytes()).hexdigest(),checksum)

    def test_bundle_has_one_model_one_gpu_distinct_port_and_frozen_source_proof(self):
        from optimization.coverage_unity import bundle
        from optimization.coverage import scope
        from workbench.domain import digest
        repo=Path(__file__).resolve().parents[1]
        app=SimpleNamespace(root=repo,settings={'backend':'llamacpp','publish_results':True})
        worker={'model_id':'model','model':{'id':'model','files':['model.gguf'],'required_vram_gb':12},
            'model_path':'/models/model.gguf','runtime_path':'/runtime/llama-server','python':'/runtime/python',
            'ssh':['ssh','authorized-host'],'constraint':'titanx&haswell','qos':'normal','remote_base':'/runs',
            'inference_port':24321,'kind':'unity'}
        frozen=scope(repo);state={'id':'batch','scope':frozen,'suite_digest':digest(frozen),'workers':[worker]}
        packet=bundle(app,state,worker)
        self.assertEqual(packet['manifest']['source_digest'],digest(packet['manifest']['source_files']))
        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(packet['archive'])),mode='r:gz') as archive:
            settings=json.load(archive.extractfile('.local/workbench/settings.json'))
            models=json.load(archive.extractfile('models.json'))
            script=archive.extractfile('coverage.sbatch').read().decode()
        self.assertEqual(len(models),1);self.assertEqual(settings['inference_port'],24321)
        self.assertFalse(settings['publish_results']);self.assertFalse(settings['sync_source'])
        self.assertEqual(script.count('#SBATCH --gpus=1'),1)
        worker2={**worker,'model_id':'other'}
        state['workers'].append(worker2)
        with self.assertRaisesRegex(ValueError,'unique inference ports'):bundle(app,state,worker)
