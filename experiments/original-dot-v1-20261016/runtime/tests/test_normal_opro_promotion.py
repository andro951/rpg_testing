"""Normal promotion preserves roles, operation boundaries and opaque LPIL data."""
import copy
import json
import unittest
from unittest.mock import patch
from test_builder.builder import ROOT, compile_test, prompt_parts, build_messages, oracle
from test_builder import normal_prompt
from workbench.domain import read_json
from workbench.workflows import messages, evaluate
from optimization.templates import bindings


class NormalOproPromotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = read_json(ROOT/'fixtures.json')['fixtures']
        cls.by_id = {f['id']: f for f in cls.fixtures}

    def test_all_operations_have_system_role_and_exactly_one_shared_operation_block(self):
        method=(ROOT/'methods/value_patch.txt').read_text().strip()
        for f in self.fixtures:
            test=compile_test(f)
            self.assertTrue(test['instructions'])
            operation=test['prompt_builder']['operation']
            override=normal_prompt.configuration().get('operation_templates',{}).get(operation)
            self.assertEqual(test['prompt_builder']['normal_template']['exact_winner_reuse'],bool(override))
            for v in test['variants']:
                request=messages(test,v['steps'][0],{},v)
                self.assertEqual([m['role'] for m in request],['system','user'])
                if override:
                    self.assertEqual(request[0]['content'],override['candidate']['system'])
                else:
                    self.assertIn('At EVERY collection boundary',request[0]['content'])
                self.assertEqual(request[1]['content'].count(method),1)
                self.assertEqual(request[1]['content'].count('Only these five operations are allowed:'),1)
                if not override:
                    self.assertIn('No explanation, Markdown fences or rewritten database.',request[1]['content'])
                self.assertIn('Return only a JSON array of operations.',request[1]['content'])
                self.assertTrue(evaluate(test,v,{'patch':json.dumps(oracle(f)[0])})['exact_match'])

    def test_collection_update_guidance_never_forces_other_operations_or_no_change(self):
        for f in self.fixtures:
            p=prompt_parts(f,'normal_json')
            applicable=f['task'] in ('update_record','update_record_nested')
            self.assertEqual('For an update described by a collection path' in p['task_requirements'],applicable)
            self.assertNotIn('For an update described by a collection path',compile_test(f)['instructions'])

    def test_system_only_edit_invalidates_exact_joint_review(self):
        f=self.by_id['db_v3_update_record'];a=compile_test(f)
        accepted={'status':'accepted','prompt_digest':a['prompt_builder']['prompt_digest']}
        reviews={a['id']:{'assistant':accepted,'isaac':accepted}}
        self.assertTrue(compile_test(f,reviews)['enabled'])
        config=copy.deepcopy(normal_prompt.configuration());config['candidate']['system']+='\nAdditional system instruction.'
        with patch('test_builder.normal_prompt.configuration',return_value=config):
            b=compile_test(f,reviews)
        self.assertNotEqual(a['prompt_builder']['prompt_digest'],b['prompt_builder']['prompt_digest'])
        self.assertFalse(b['enabled'])

    def test_inserted_marker_shaped_data_is_opaque_and_optimizer_bindings_stay_structured(self):
        f=copy.deepcopy(self.by_id['db_v3_append_record'])
        text='literal <{current_state}> (1{new_information}) ${id_value}'
        f['parameters']['new_record']['name']=text
        test=compile_test(f);v=test['variants'][0]
        self.assertIn(text,messages(test,v['steps'][0],{},v)[1]['content'])
        value=bindings({'test':test,'variant':v,'presentation':'Normal JSON'}, {'earlier':text})
        self.assertEqual(value['new_information'],prompt_parts(f,'normal_json')['new_information'])
        self.assertEqual(json.loads(value['prior_outputs']),{'earlier':text})
        self.assertNotIn('expected_state',value)

    def test_invalid_normal_templates_fail_closed(self):
        config=normal_prompt.configuration()
        for kind in ('missing_label','unknown_label','empty_system'):
            c=copy.deepcopy(config)
            if kind=='missing_label':c['candidate']['user']=c['candidate']['user'].replace('<{current_state}>','')
            elif kind=='unknown_label':c['candidate']['user']+=' <{unknown}>'
            else:c['candidate']['system']=''
            with self.subTest(kind=kind),patch('test_builder.normal_prompt.read_json',return_value=c):
                with self.assertRaises(ValueError):normal_prompt.configuration()

    def test_promotion_does_not_relax_whole_response_json_grading(self):
        f=self.by_id['db_v3_append_record'];test=compile_test(f);v=test['variants'][0]
        text=json.dumps(oracle(f)[0])
        self.assertTrue(evaluate(test,v,{'patch':text})['exact_match'])
        self.assertFalse(evaluate(test,v,{'patch':'```json\n'+text+'\n```'})['exact_match'])
