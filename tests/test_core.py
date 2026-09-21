import copy
import json
import tempfile
import unittest
from pathlib import Path
from rpgbench.core import (InvalidPatch, ResultStore, PIPELINES, apply_patch, atomic_write,
    canonical, digest, equal, field_changes, parse_json, pipeline_messages, read_json, score, validate_inputs)
ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.models = read_json(ROOT / 'tests/data/legacy_models.json')
        self.exp = read_json(ROOT / 'experiment.json')
        self.fixtures = [read_json(p) for p in sorted((ROOT/'fixtures').glob('*.json'))]

    def test_catalog_and_two_oracles(self):
        self.assertEqual(len(self.fixtures), 2)
        validate_inputs(self.models, self.exp, self.fixtures)
        self.assertIsInstance(self.models, list)
        for f in self.fixtures:
            for kind, p in f['example_patches'].items():
                self.assertTrue(score(f, canonical(p), kind)['exact_match'])

    def test_local_model_record_does_not_require_repo_id(self):
        local=dict(self.models[0])
        local.pop('repo_id',None)
        local.update(id='local-discovered-model',base_model='Local discovered GGUF',files=['local.gguf'])
        validate_inputs([local],self.exp,self.fixtures)

    def test_strict_booleans(self):
        self.assertFalse(equal(True, 1))
        self.assertFalse(equal({'x': [False]}, {'x': [0]}))
        self.assertTrue(equal(1, 1.0))
        self.assertNotEqual(digest(True), digest(1))

    def test_json_rejects_duplicate_nan_and_prose(self):
        for text in ['{"x":1,"x":2}', '[NaN]', '```json\n[]\n```', '[] trailing']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_json(text)

    def test_canonical_order(self):
        self.assertEqual(digest({'b':2,'a':1}), digest({'a':1,'b':2}))

    def test_atomic_application(self):
        state = {'a': 1}
        with self.assertRaises(InvalidPatch):
            apply_patch(state, [{'op':'replace','path':'/a','value':2}, {'op':'remove','path':'/absent'}], 'json_patch')
        self.assertEqual(state, {'a':1})

    def test_all_rfc_operations(self):
        state = {'a':[1,2], 'b':{}}
        patch = [{'op':'test','path':'/a/0','value':1}, {'op':'add','path':'/a/-','value':3},
                 {'op':'copy','from':'/a/0','path':'/b/x'}, {'op':'move','from':'/a/1','path':'/b/y'},
                 {'op':'replace','path':'/a/0','value':4}, {'op':'remove','path':'/a/1'}]
        self.assertEqual(apply_patch(state,patch,'json_patch'), {'a':[4],'b':{'x':1,'y':2}})

    def test_rfc_pointer_escapes(self):
        result=apply_patch({'a/b':{'~':1}},[{'op':'replace','path':'/a~1b/~0','value':2}],'json_patch')
        self.assertEqual(result,{'a/b':{'~':2}})
        with self.assertRaises(InvalidPatch):
            apply_patch({},[{'op':'add','path':'/~2','value':2}],'json_patch')

    def test_rfc_root_and_extra_properties(self):
        self.assertEqual(apply_patch({},[{'op':'replace','path':'','value':[1], 'note':'ignored'}],'json_patch'),[1])

    def test_bad_indices(self):
        for i in ['-1','01','4','-']:
            with self.subTest(i=i), self.assertRaises(InvalidPatch):
                apply_patch({'a':[1]},[{'op':'remove','path':'/a/'+i}],'json_patch')

    def test_move_descendant_and_wrong_test(self):
        with self.assertRaises(InvalidPatch):
            apply_patch({'a':{}},[{'op':'move','from':'/a','path':'/a/x'}],'json_patch')
        with self.assertRaises(InvalidPatch):
            apply_patch({'a':True},[{'op':'test','path':'/a','value':1}],'json_patch')

    def test_semantic_list_remove_ambiguity(self):
        for values in [[],['x','x']]:
            with self.subTest(values=values), self.assertRaises(InvalidPatch):
                apply_patch({'a':values},[{'op':'list_remove','path':'/a','value':'x'}],'semantic')
        self.assertEqual(apply_patch({'a':['x','y']},[{'op':'list_remove','path':'/a','value':'x'}],'semantic'), {'a':['y']})

    def test_semantic_requires_existing_paths(self):
        with self.assertRaises(InvalidPatch):
            apply_patch({},[{'op':'set','path':'/new','value':1}],'semantic')

    def test_invalid_patch_forms(self):
        for patch in [{},[1],[{'op':'nonsense','path':'/a'}],[{'op':'replace','path':'/a'}]]:
            with self.subTest(patch=patch), self.assertRaises(InvalidPatch):
                apply_patch({'a':1},patch,'json_patch')

    def test_equivalent_array_patch_scores_correct(self):
        f=next(f for f in self.fixtures if f['id']=='clothing_append')
        p=[{'op':'replace','path':'/characters/Tom/clothing','value':['blue shirt','jeans','green jacket']}]
        self.assertTrue(score(f,canonical(p),'json_patch')['exact_match'])

    def test_missed_wrong_and_unsupported(self):
        f=next(f for f in self.fixtures if f['id']=='time_only')
        self.assertEqual(score(f,'[]','json_patch')['missed_changes'],1)
        p=[{'op':'replace','path':'/time','value':'14:21'}, {'op':'replace','path':'/location','value':'Garden'}]
        s=score(f,canonical(p),'json_patch')
        self.assertEqual((s['wrong_values'],s['unsupported_changes'],s['correct_changes']),(1,1,0))

    def test_invalid_schema_types(self):
        f=self.fixtures[0]
        p=[{'op':'replace','path':'/door_locked','value':1}]
        self.assertFalse(score(f,canonical(p),'json_patch')['valid'])

    def test_no_change_does_not_inflate_accuracy(self):
        f=copy.deepcopy(self.fixtures[0]);f['expected_state']=copy.deepcopy(f['initial_state'])
        s=score(f,'[]','json_patch')
        self.assertTrue(s['exact_match']);self.assertIsNone(s['recall'])
        self.assertIsNone(s['precision'])

    def test_oracle_never_in_prompt(self):
        f=copy.deepcopy(self.fixtures[0]); f['expected_state']={'SECRET':'DO_NOT_LEAK'}
        f['example_patches']={'SECRET':'DO_NOT_LEAK'}
        for p in PIPELINES:
            for analysis in [None,'Untrusted earlier analysis']:
                self.assertNotIn('DO_NOT_LEAK',canonical(pipeline_messages(f,p,analysis)))

    def test_invalid_catalog_and_settings(self):
        for value in [True, 0, -1, float('inf')]:
            m=copy.deepcopy(self.models);m[0]['required_vram_gb']=value
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate_inputs(m,self.exp,self.fixtures)
        e=copy.deepcopy(self.exp);e['context_tokens']=8192
        with self.assertRaises(ValueError):validate_inputs(self.models,e,self.fixtures)
        m=copy.deepcopy(self.models);m.append(m[0])
        with self.assertRaises(ValueError):validate_inputs(m,self.exp,self.fixtures)

    def test_array_change_is_single_field(self):
        self.assertEqual(len(field_changes({'a':[1,2]},{'a':[3,1,2]})),1)

    def test_results_resume_and_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            store=ResultStore(Path(d));cid='a'*64
            store.save({'case_id':cid,'status':'error','error':'timeout'})
            self.assertFalse(store.done(cid))
            p=store.save({'case_id':cid,'status':'completed','score':{'exact_match':False}})
            self.assertTrue(store.done(cid));self.assertEqual(len(store.records(cid)),2)
            p.write_text('{}')
            with self.assertRaises(ValueError):store.done(cid)

    def test_atomic_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'folder'/'x.json';atomic_write(p,{'ok':True})
            self.assertEqual(read_json(p),{'ok':True})
            self.assertFalse(list(p.parent.glob('.pending-*')))

if __name__=='__main__':unittest.main()
