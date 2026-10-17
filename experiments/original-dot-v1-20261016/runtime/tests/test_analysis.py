import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rpgbench.analyze import collect, summarize, write_exports, main
from rpgbench.backends import BackendError, ManagedBackend, detect_gpu
from rpgbench.core import ResultStore, canonical, parse_json, read_json, validate_inputs
ROOT=Path(__file__).resolve().parents[1]


def example(simulated=False):
    return {'case_id':'a'*64,'status':'completed','simulated':simulated,'model_id':'test-model',
            'pipeline':'direct_json_patch','fixture_id':'time_only','seed':42,'repetition':0,
            'environment':{'gpu_name':'test GPU','backend':'mock' if simulated else 'test'},
            'calls':[{'text':'[]'}],'pipeline_seconds':0.25,
            'score':{'valid':True,'exact_match':False,'correct_changes':0,'required_changes':1}}


class AnalysisTests(unittest.TestCase):
    def test_export_deduplicates_and_excludes_simulations(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);store=ResultStore(root/'real')
            store.save(example())
            fake=example(True);fake['case_id']='b'*64
            ResultStore(root/'fake').save(fake)
            rows=collect([root,root])
            self.assertEqual(len(rows),1)
            report=summarize(rows)
            self.assertEqual(report['groups'][0]['exact_match_rate'],0)
            write_exports(report,root/'out')
            self.assertIn('pipeline_seconds',(root/'out/cases.csv').read_text())
            self.assertEqual(len(collect([root],True)),2)
            self.assertEqual(main([str(root),'--output',str(root/'out2')]),0)

    def test_infrastructure_errors_do_not_become_incorrect_answers(self):
        r=example();err=dict(r,status='error',error='timeout')
        err.pop('score')
        report=summarize([err,r])
        self.assertEqual(report['completed_cases'],1)
        self.assertEqual(report['infrastructure_error_attempts'],1)
        self.assertEqual(report['unresolved_cases'],0)
        self.assertEqual(summarize([err])['unresolved_cases'],1)
        with self.assertRaises(ValueError):summarize([r,dict(r,pipeline_seconds=0.3)])

    def test_corrupt_envelope_stops_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            p=ResultStore(Path(d)).save(example());p.write_text('{"sha256":"wrong","record":{}}')
            with self.assertRaises(ValueError):collect([Path(d)])

    def test_empty_export_and_missing_root(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_exports(summarize([]),root)
            self.assertEqual((root/'cases.csv').read_text(),'case_id\n')
            with self.assertRaises(SystemExit):main([str(root/'missing')])

    def test_lmstudio_single_gpu_guard(self):
        csv='0, GPU-a, GTX 1080, 8192, 7000, 580\n1, GPU-b, A100, 81920, 80000, 580\n'
        with patch('rpgbench.backends.command',return_value=csv),self.assertRaises(BackendError):
            detect_gpu({'backend':'lmstudio','gpu_selector':'0'})

    def test_validation_edge_cases(self):
        for text in ['[1e999]','[-1e999]']:
            with self.assertRaises(ValueError):parse_json(text)
        models=read_json(ROOT/'tests/data/legacy_models.json');exp=read_json(ROOT/'experiment.json')
        fixtures=[read_json(p) for p in (ROOT/'fixtures').glob('*.json')]
        for field,value in [('top_p',0),('top_p',2),('pipelines',['direct_json_patch','direct_json_patch']),('seeds',[42,42])]:
            e=dict(exp);e[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate_inputs(models,e,fixtures)

    def test_mocked_lmstudio_lifecycle_and_foreign_model_refusal(self):
        worker={'backend':'lmstudio','base_url':'http://127.0.0.1:1234/v1'}
        model=read_json(ROOT/'tests/data/legacy_models.json')[0];exp=read_json(ROOT/'experiment.json')
        binding={'model_key':'exact-key','files':model['files']}
        with tempfile.TemporaryDirectory() as d:
            backend=ManagedBackend(worker,Path(d),{'uuid':'GPU-test'})
            alias='rpgbench-'+model['id']
            with patch.object(backend.client,'request',return_value={'models':[]}), \
                 patch.object(backend.client,'models',return_value={'data':[{'id':alias}]}), \
                 patch('rpgbench.backends.command',return_value='loaded') as cmd:
                backend.load(model,binding,exp)
                self.assertEqual(backend.model_id,alias)
                backend.unload()
                self.assertEqual(cmd.call_args.args[0],['lms','unload',alias])
            with patch.object(backend.client,'request',return_value={'models':[{'loaded_instances':[{'id':'unrelated'}]}]}), \
                 patch('rpgbench.backends.command') as cmd:
                with self.assertRaises(BackendError):backend.load(model,binding,exp)
                cmd.assert_not_called()

    def test_llama_child_preserves_scheduler_cuda_visibility(self):
        worker={'backend':'llama_cpp','base_url':'http://127.0.0.1:8080/v1'}
        model=read_json(ROOT/'tests/data/legacy_models.json')[0];exp=read_json(ROOT/'experiment.json')
        with tempfile.TemporaryDirectory() as d:
            backend=ManagedBackend(worker,Path(d),{'uuid':'GPU-test'})
            alias='rpgbench-'+model['id']
            with patch.dict('os.environ',{'CUDA_VISIBLE_DEVICES':'scheduler-device'}), \
                 patch('rpgbench.backends.socket.socket') as sock, \
                 patch('rpgbench.backends.subprocess.Popen') as process, \
                 patch.object(backend.client,'models',return_value={'data':[{'id':alias}]}):
                sock.return_value.__enter__.return_value.connect_ex.return_value=1
                process.return_value.poll.return_value=None
                backend.load(model,{'files':model['files']},exp)
                self.assertEqual(process.call_args.kwargs['env']['CUDA_VISIBLE_DEVICES'],'scheduler-device')
                backend.unload()

if __name__=='__main__':unittest.main()
