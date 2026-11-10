"""Historical five-operation fixtures retain independent runtime regression coverage."""
import copy
import json
import unittest
from collections import Counter
from tests.helpers.frozen_prompts import INPUTS as ROOT, definition, reference
from workbench.scoring import at as resolve_pointer, pointer
from workbench.domain import read_json
from workbench.scoring import apply
from workbench.workflows import evaluate
from evaluation.core import assess


class OperationCoverageTests(unittest.TestCase):
    def setUp(self):
        self.fixtures=read_json(ROOT/'fixtures.json')['fixtures']
        self.by_id={f['id']:f for f in self.fixtures}

    def test_only_the_five_operations_and_a_no_change_control_are_benchmarked(self):
        counts=Counter(definition(f['id'])['prompt_builder']['operation'] for f in self.fixtures)
        self.assertEqual(counts,{'update':4,'append':4,'remove':4,'move':4,'copy':4,'no_change':1})
        for f in self.fixtures:
            self.assertNotIn(f['task'],('index','insert','reorder','test'))

    def test_append_move_copy_cover_both_element_types_and_empty_destinations(self):
        for operation in ('append','move','copy'):
            covered=set()
            for f in self.fixtures:
                if definition(f['id'])['prompt_builder']['operation']!=operation:continue
                params=f['parameters']
                destination=resolve_pointer(f['state'],pointer(params.get('destination_array',params['array_path'])))
                covered.add(('record' if f['task'].endswith('record') else 'value',bool(destination)))
            self.assertEqual(covered,{('record',False),('record',True),('value',False),('value',True)},operation)

    def test_remove_covers_remaining_elements_and_becoming_empty_for_both_types(self):
        covered=set()
        for f in self.fixtures:
            if definition(f['id'])['prompt_builder']['operation']!='remove':continue
            _,after=reference(f['id'])
            covered.add((f['task'],bool(resolve_pointer(after,pointer(f['parameters']['array_path'])))))
        self.assertEqual(covered,{('remove_record',False),('remove_record',True),('remove_value',False),('remove_value',True)})

    def test_all_transfer_oracles_match_complete_element_and_both_collections_independently(self):
        for f in self.fixtures:
            operation=definition(f['id'])['prompt_builder']['operation']
            if operation not in ('move','copy'):continue
            with self.subTest(fixture=f['id']):
                p=f['parameters'];state=f['state']
                before=copy.deepcopy(state)
                source=resolve_pointer(state,pointer(p['array_path']));destination=resolve_pointer(state,pointer(p['destination_array']))
                field=p.get('id_field');wanted=p.get('id_value',p.get('value'))
                element=next(e for e in source if (e[field] if field else e)==wanted)
                expected=copy.deepcopy(state)
                if operation=='move':
                    resolve_pointer(expected,pointer(p['array_path']))[:]=[e for e in source if (e[field] if field else e)!=wanted]
                resolve_pointer(expected,pointer(p['destination_array'])).append(copy.deepcopy(element))
                patch_value,after=reference(f['id'])
                self.assertEqual(after,expected)
                self.assertEqual(patch_value[0]['op'],operation)
                self.assertEqual(resolve_pointer(after,pointer(p['destination_array'])),destination+[element])
                self.assertEqual(state,before)
                if operation=='copy':self.assertEqual(resolve_pointer(after,pointer(p['array_path'])),source)

    def test_copy_evaluators_pass_correct_answers_and_explain_move_or_malformed_answers(self):
        for f in self.fixtures:
            if definition(f['id'])['prompt_builder']['operation']!='copy':continue
            test=definition(f['id']);v=test['variants'][0]
            good=reference(f['id'])[0]
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

    def test_copy_runtime_rejects_same_collection_and_duplicate_destination(self):
        fixture=self.by_id['db_v3_copy_record']
        test=definition(fixture['id']);variant=test['variants'][0]
        response=reference(fixture['id'])[0]
        response[0]['path']=fixture['parameters']['array_path']
        self.assertFalse(evaluate(test,variant,{'patch':json.dumps(response)})['exact_match'])
        test=definition(fixture['id'])
        test['source']['initial_state']['storage'][0]['item_id']=fixture['parameters']['id_value']
        response=reference(fixture['id'])[0]
        self.assertFalse(evaluate(test,test['variants'][0],{'patch':json.dumps(response)})['exact_match'])

    def test_frozen_four_operation_contracts_still_reject_copy(self):
        f=self.by_id['db_v3_copy_record'];test=definition(f['id']);v=test['variants'][0]
        values={'patch':json.dumps(reference(f['id'])[0])}
        self.assertTrue(evaluate(test,v,values)['exact_match'])
        # A saved four-operation definition keeps its own response contract.
        old=copy.deepcopy(v)
        old['result']['response_schema']['items']['oneOf']=[choice for choice in old['result']['response_schema']['items']['oneOf']
                                                         if choice['properties']['op']['const']!='copy']
        self.assertFalse(evaluate(test,old,values)['exact_match'])
        report=assess(test,old,values)
        self.assertEqual(report['objective_outcome'],'FAIL')
        self.assertTrue(any(c['status']=='failed' and c['code']=='patch.method_contract' for c in report['checks']))
