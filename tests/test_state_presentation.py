import json
import unittest
from pathlib import Path
from workbench.domain import read_json,validate_test,load_tests as load_workflow_specs
from workbench.presentation import indexed_arrays,full_paths_text,render_source,presentation_mode
from workbench.workflows import messages,evaluate,execute
from workbench.backends import DemoBackend

ROOT=Path(__file__).resolve().parents[1]
FORMATS=('raw_json','indexed_arrays','full_paths')

class StatePresentationTests(unittest.TestCase):
    def test_arrays_become_numeric_key_objects_recursively(self):
        value={'a':['x',{'b':[10,20]}],'real_numeric_object':{'0':'keep','1':'object'}}
        shown=indexed_arrays(value)
        self.assertEqual(shown['a'],{'0':'x','1':{'b':{'0':10,'1':20}}})
        self.assertEqual(shown['real_numeric_object'],{'0':'keep','1':'object'})

    def test_full_paths_flatten_recursively_and_keep_empty_containers(self):
        value={'queue_name':'Desk','tickets':[{'id':'A','tags':[]},{'id':'B'}],'meta':{}}
        shown=full_paths_text(value)
        self.assertEqual(shown,
            'queue_name: Desk\n\n'
            'tickets.0.id: A\n'
            'tickets.0.tags: []\n\n'
            'tickets.1.id: B\n\n'
            'meta: {}')
        self.assertNotIn('"',shown)

    def test_array_patch_variants_show_same_source_in_three_shapes(self):
        test=read_json(ROOT/'test_specs/array_patch_replace_004.json')
        by={v['state_presentation']:v for v in test['variants']}
        rendered={}
        for mode in FORMATS:
            msg=messages(test,by[mode]['steps'][0],{},by[mode])
            rendered[mode]=msg[1]['content'].split('Current State:\n',1)[1].split('\n\nNew Information:\n',1)[0]
        raw=json.loads(rendered['raw_json']);indexed=json.loads(rendered['indexed_arrays'])
        self.assertIsInstance(raw['tickets'],list)
        self.assertIsInstance(indexed['tickets'],dict)
        self.assertEqual(indexed['tickets']['73'],raw['tickets'][73])
        self.assertIn('tickets.73.ticket_id: SR-60432',rendered['full_paths'])
        self.assertIn('review_samples: []',rendered['full_paths'])

    def test_time_only_direct_prompt_is_conversational_pretty_and_minimal(self):
        test=read_json(ROOT/'test_specs/time_only.json')
        variant=next(v for v in test['variants'] if v['id']=='direct_json_patch__raw_json')
        prompt=messages(test,variant['steps'][0],{},variant)
        self.assertEqual(prompt[0],{'role':'system','content':'You help update an existing JSON state when new information is provided.'})
        self.assertEqual(len(prompt),2);user=prompt[1]['content']
        self.assertTrue(user.startswith('I need you to write a JSON Patch to update the existing state with the new information.\n\nCurrent State:\n{\n  "time": "14:15",'))
        self.assertIn('\n\nNew Information:\nExactly five minutes pass.\n\n',user)
        self.assertIn('Please return only the JSON Patch array.',user)
        self.assertNotIn('SOURCE',user)

    def test_time_only_has_all_three_presentations_for_each_workflow(self):
        test=read_json(ROOT/'test_specs/time_only.json')
        for base in ('direct_json_patch','analyze_json_patch','direct_semantic','analyze_semantic'):
            self.assertEqual({v['state_presentation'] for v in test['variants'] if v['id'].startswith(base+'__')},set(FORMATS))

    def test_prompt_calibration_v1_is_balanced_across_presentations(self):
        test=read_json(ROOT/'test_specs/prompt_calibration_001_time.json')
        trio=[v for v in test['variants'] if v['id'].startswith('v1_original_clinical__')]
        self.assertEqual({v['state_presentation'] for v in trio},set(FORMATS))
        self.assertEqual(len({v.get('new_information_override') for v in trio}),1)
        systems={v['state_presentation']:messages(test,v['steps'][0],{},v)[0]['content'] for v in trio}
        self.assertIn('ordinary JSON',systems['raw_json'])
        self.assertIn('indexed view',systems['indexed_arrays'])
        self.assertIn('flattened dot-path view',systems['full_paths'])

    def test_prompt_calibration_modifiers_are_distinct(self):
        test=read_json(ROOT/'test_specs/prompt_calibration_001_time.json')
        rendered={v['id'].split('__',1)[0]:messages(test,v['steps'][0],{},v)[-1]['content']
                  for v in test['variants'] if v['state_presentation']=='raw_json'}
        self.assertIn('Only include fields that actually changed.',rendered['v3_only_changed'])
        self.assertIn('Make the smallest JSON Patch needed',rendered['v4_smallest_patch'])
        self.assertIn('only when the value in the updated state should be different',rendered['v5_change_rule'])
        self.assertIn('Example:\nCurrent State:',rendered['v6_one_example'])

    def test_dialogue_test_uses_direct_prompt_only(self):
        test=read_json(ROOT/'test_specs/dialogue_test.json');variant=test['variants'][0]
        prompt=messages(test,variant['steps'][0],{},variant)
        self.assertEqual(prompt,[{'role':'system','content':"Follow the user's prompt."},
                                 {'role':'user','content':variant['steps'][0]['prompt']}])
        self.assertEqual(test['repetitions'],3)

    def test_default_presentation_is_indexed_arrays(self):
        self.assertEqual(presentation_mode({'source':{}},{}),'indexed_arrays')

    def test_required_operation_is_part_of_task_success(self):
        test={'source':{'initial_state':{'x':1}},'expected_state':{'x':2}}
        variant={'result':{'step':'patch','representation':'json_patch','required_ops':['replace']}}
        right=evaluate(test,variant,{'patch':'[{"op":"replace","path":"/x","value":2}]'})
        wrong=evaluate(test,variant,{'patch':'[{"op":"add","path":"/x","value":2}]'})
        self.assertTrue(right['exact_match']);self.assertTrue(right['patch_ops_match'])
        self.assertTrue(wrong['state_exact_match']);self.assertFalse(wrong['patch_ops_match']);self.assertFalse(wrong['exact_match'])

    def test_validation_accepts_three_presentations_and_rejects_unknown(self):
        original=read_json(ROOT/'test_specs/array_patch_replace_004.json')
        for mode in FORMATS:
            test=json.loads(json.dumps(original));test['variants'][0]['state_presentation']=mode;validate_test(test)
        test=json.loads(json.dumps(original));test['variants'][0]['state_presentation']='mystery'
        with self.assertRaises(ValueError):validate_test(test)

    def test_every_enabled_fixture_demo_path_is_exact_or_intentionally_open(self):
        for test in load_workflow_specs(ROOT/'test_specs'):
            for variant in test['variants']:
                if not variant.get('enabled',True):continue
                with self.subTest(test=test['id'],variant=variant['id']):
                    result=execute(test,variant,DemoBackend())
                    locating_only=test.get('provenance',{}).get('purpose')=='Isolate array index selection from JSON Patch construction.'
                    if locating_only:
                        self.assertTrue(result['score']['valid'],result['score'])
                    elif 'expected_state' not in test and variant.get('result',{}).get('representation')=='answers' and not variant.get('expected_answers'):
                        self.assertTrue(result['score']['valid'],result['score'])
                        self.assertIsNone(result['score']['exact_match'],result['score'])
                    else:
                        self.assertTrue(result['score']['exact_match'],result['score'])

if __name__=='__main__':unittest.main()
