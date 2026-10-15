"""Five operation purposes, useful boundaries and independent transfer expectations."""
import copy
import json
import unittest
from collections import Counter
from test_builder.builder import ROOT, TASKS, at, compile_test, oracle
from workbench.domain import read_json
from workbench.scoring import apply
from workbench.workflows import evaluate
from evaluation.core import assess


class OperationCoverageTests(unittest.TestCase):
    def setUp(self):
        self.fixtures=read_json(ROOT/'fixtures.json')['fixtures']
        self.by_id={f['id']:f for f in self.fixtures}

    def test_only_the_five_operations_and_a_no_change_control_are_benchmarked(self):
        counts=Counter(TASKS[f['task']][0] for f in self.fixtures)
        self.assertEqual(counts,{'update':4,'append':4,'remove':4,'move':4,'copy':4,'no_change':1})
        for f in self.fixtures:
            self.assertNotIn(f['task'],('index','insert','reorder','test'))

    def test_append_move_copy_cover_both_element_types_and_empty_destinations(self):
        for operation in ('append','move','copy'):
            covered=set()
            for f in self.fixtures:
                if TASKS[f['task']][0]!=operation:continue
                params=f['parameters']
                destination=at(f['state'],params.get('destination_array',params['array_path']))
                covered.add(('record' if f['task'].endswith('record') else 'value',bool(destination)))
            self.assertEqual(covered,{('record',False),('record',True),('value',False),('value',True)},operation)

    def test_remove_covers_remaining_elements_and_becoming_empty_for_both_types(self):
        covered=set()
        for f in self.fixtures:
            if TASKS[f['task']][0]!='remove':continue
            _,after=oracle(f)
            covered.add((f['task'],bool(at(after,f['parameters']['array_path']))))
        self.assertEqual(covered,{('remove_record',False),('remove_record',True),('remove_value',False),('remove_value',True)})

    def test_all_transfer_oracles_match_complete_element_and_both_collections_independently(self):
        for f in self.fixtures:
            operation=TASKS[f['task']][0]
            if operation not in ('move','copy'):continue
            with self.subTest(fixture=f['id']):
                p=f['parameters'];state=f['state']
                before=copy.deepcopy(state)
                source=at(state,p['array_path']);destination=at(state,p['destination_array'])
                field=p.get('id_field');wanted=p.get('id_value',p.get('value'))
                element=next(e for e in source if (e[field] if field else e)==wanted)
                expected=copy.deepcopy(state)
                if operation=='move':
                    at(expected,p['array_path'])[:]=[e for e in source if (e[field] if field else e)!=wanted]
                at(expected,p['destination_array']).append(copy.deepcopy(element))
                patch_value,after=oracle(f)
                self.assertEqual(after,expected)
                self.assertEqual(patch_value[0]['op'],operation)
                self.assertEqual(at(after,p['destination_array']),destination+[element])
                self.assertEqual(state,before)
                if operation=='copy':self.assertEqual(at(after,p['array_path']),source)

    def test_copy_evaluators_pass_correct_answers_and_explain_move_or_malformed_answers(self):
        for f in self.fixtures:
            if TASKS[f['task']][0]!='copy':continue
            test=compile_test(f);v=test['variants'][0]
            good=oracle(f)[0]
            for kind in ('correct','move','missing_source','invalid_source','missing_element','wrong_destination'):
                response=copy.deepcopy(good)
                if kind=='move':response[0]['op']='move'
                elif kind=='missing_source':response[0].pop('from')
                elif kind=='invalid_source':response[0]['from']='/"unterminated'
                elif kind=='missing_element':response[0]['from']=f['parameters']['array_path']+'/"absent"'
                elif kind=='wrong_destination':response[0]['path']=f['parameters']['array_path']
                values={'patch':json.dumps(response)}
                with self.subTest(fixture=f['id'],kind=kind):
                    report=assess(test,v,values)
                    self.assertEqual(report['objective_outcome'],'PASS' if kind=='correct' else 'FAIL')
                    self.assertEqual(evaluate(test,v,values)['exact_match'],kind=='correct')
                    if kind!='correct':
                        failures=[c for c in report['checks'] if c['status']=='failed']
                        self.assertTrue(failures)
                        self.assertTrue(all(c['explanation'] for c in failures))

    def test_nested_copy_creates_independent_nested_objects(self):
        from tests.test_value_paths import obj
        element=obj({'id':{'type':'string'},'details':obj({'count':{'type':'number'}})})
        collection={'type':'array','x-id-field':'id','items':element}
        schema=obj({'source':collection,'destination':collection})
        state={'source':[{'id':'a/b','details':{'count':2}}],'destination':[]}
        after=apply(state,[{'op':'copy','from':'/source/"a/b"','path':'/destination'},
                           {'op':'replace','path':'/destination/"a/b"/details/count','value':9}],'value_patch',schema)
        self.assertEqual(after['source'],state['source'])
        self.assertEqual(after['destination'],[{'id':'a/b','details':{'count':9}}])

    def test_copy_fixture_rejects_same_collection_and_duplicate_destination_before_export(self):
        from test_builder.builder import build_prompt
        f=copy.deepcopy(self.by_id['db_v3_copy_record'])
        f['parameters']['destination_array']=f['parameters']['array_path']
        with self.assertRaisesRegex(ValueError,'different destination'):
            build_prompt(f,'normal_json')
        f=copy.deepcopy(self.by_id['db_v3_copy_record'])
        f['state']['storage'][0]['item_id']=f['parameters']['id_value']
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            build_prompt(f,'normal_json')

    def test_frozen_four_operation_contracts_still_reject_copy(self):
        f=self.by_id['db_v3_copy_record'];test=compile_test(f);v=test['variants'][0]
        values={'patch':json.dumps(oracle(f)[0])}
        self.assertTrue(evaluate(test,v,values)['exact_match'])
        # A saved four-operation definition keeps its own response contract.
        old=copy.deepcopy(v)
        old['result']['response_schema']['items']['oneOf']=[choice for choice in old['result']['response_schema']['items']['oneOf']
                                                         if choice['properties']['op']['const']!='copy']
        self.assertFalse(evaluate(test,old,values)['exact_match'])
        report=assess(test,old,values)
        self.assertEqual(report['objective_outcome'],'FAIL')
        self.assertTrue(any(c['status']=='failed' and c['code']=='patch.method_contract' for c in report['checks']))
