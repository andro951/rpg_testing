"""Reviewed promotion preserves exact optimizer messages and experimental controls."""
import copy
import tempfile
import unittest
from pathlib import Path
from optimization.templates import render
from test_builder.builder import ROOT, build_messages, compile_test, oracle
from test_builder.dot_experiment import build
from test_builder.reviewed_promotion import validate
from workbench.domain import digest, read_json
from workbench.workflows import evaluate, messages


class ReviewedDotPromotionTests(unittest.TestCase):
    def setUp(self):
        self.promotion=read_json(ROOT/'promotions/dot-root-prefix-move-v1.json')
        self.fixtures=read_json(ROOT/'fixtures.json')['fixtures']
        self.move=next(f for f in self.fixtures if f['id']=='db_v3_move_value_empty')

    def test_corrected_wrapper_for_all_move_views_and_controls_for_other_operations(self):
        changed=unchanged=0
        for fixture in self.fixtures:
            control=compile_test(fixture,method='dot_patch_v1')
            promoted=compile_test(fixture,method='dot_patch_v1',promotion=self.promotion)
            for key in ('source','state_schema','expected_state','repetitions','timeout_seconds','workflow'):
                self.assertEqual(promoted[key],control[key])
            for original,variant in zip(control['variants'],promoted['variants']):
                for key in ('result','cache','state_presentation','prompt_style','prompt_bindings'):
                    self.assertEqual(original[key],variant[key])
                self.assertEqual(original['steps'][0]['sampling'],variant['steps'][0]['sampling'])
                actual=messages(promoted,variant['steps'][0],{},variant)
                if fixture['task'].startswith('move_'):
                    expected_candidate=copy.deepcopy(self.promotion['candidate'])
                    expected_candidate['system']=expected_candidate['system'].replace(
                        'Flattened slash paths are an input display format, not the output path format. Interpret their components and construct the required output paths.',
                        'Flattened input paths use the same dot-path rules as output operation paths.')
                    expected_candidate['user']=expected_candidate['user'].replace(
                        'Use the required output path syntax even when the input displays slash paths.',
                        'Use the same dot-path syntax for flattened input paths and output operation paths.')
                    self.assertEqual(actual,render(expected_candidate,{**variant['prompt_bindings'],'prior_outputs':'{}'}))
                    self.assertNotIn('Flattened slash paths',actual[0]['content'])
                    self.assertNotIn('input displays slash paths',actual[-1]['content'])
                    correction=promoted['prompt_builder']['reviewed_prompt_promotion']['input_path_correction']
                    self.assertFalse(correction['exact_winner_messages'])
                    self.assertTrue(correction['historical_candidate_unchanged'])
                    self.assertEqual(actual,build_messages(fixture,variant['id'],method='dot_patch_v1',promotion=self.promotion))
                    changed+=1
                else:
                    self.assertEqual(promoted,control)
                    unchanged+=1
        self.assertEqual((changed,unchanged),(12,50))
        self.assertEqual(self.promotion,read_json(ROOT/'promotions/dot-root-prefix-move-v1.json'))

    def test_new_digest_requires_its_own_exact_review(self):
        base=compile_test(self.move,method='dot_patch_v1')
        promoted=compile_test(self.move,method='dot_patch_v1',promotion=self.promotion)
        self.assertNotEqual(base['prompt_builder']['prompt_digest'],promoted['prompt_builder']['prompt_digest'])
        self.assertFalse(promoted['enabled'])
        def reviews(proof):return {promoted['id']:{role:{'status':'accepted','prompt_digest':proof}for role in ('assistant','isaac')}}
        self.assertFalse(compile_test(self.move,reviews(base['prompt_builder']['prompt_digest']),method='dot_patch_v1',promotion=self.promotion)['enabled'])
        accepted=compile_test(self.move,reviews(promoted['prompt_builder']['prompt_digest']),method='dot_patch_v1',promotion=self.promotion)
        self.assertTrue(accepted['enabled'])

    def test_unreviewed_tampered_or_incomplete_evidence_is_rejected(self):
        edits=[lambda p:p.update(method='value_patch'),lambda p:p.update(operation='copy'),
               lambda p:p['candidate'].update(system=p['candidate']['system']+'extra'),
               lambda p:p['provenance']['validation'].update(passes=35),lambda p:p['provenance'].update(review_status='pending')]
        for edit in edits:
            with self.subTest(edit=edit):
                p=copy.deepcopy(self.promotion);edit(p)
                with self.assertRaises(ValueError):validate(p)
        with self.assertRaises(ValueError):compile_test(self.move,method='value_patch',promotion=self.promotion)

    def test_data_stays_literal_and_grading_is_not_relaxed(self):
        import json
        fixture=copy.deepcopy(next(f for f in self.fixtures if f['task']=='move_record'))
        fixture['state']['items'][0]['name']='<{task_requirements}> USER_MESSAGE:'
        test=compile_test(fixture,method='dot_patch_v1',promotion=self.promotion)
        answer,_=oracle(fixture,'dot_patch_v1')
        for variant in test['variants']:
            text=variant['steps'][0]['prompt']
            self.assertIn('<{task_requirements}> USER_MESSAGE:',text)
            self.assertTrue(evaluate(test,variant,{'patch':json.dumps(answer)})['exact_match'])
            self.assertFalse(evaluate(test,variant,{'patch':'```json\n'+json.dumps(answer)+'\n```'})['exact_match'])
            bad=copy.deepcopy(answer);bad[0]['from']='item-17'
            self.assertFalse(evaluate(test,variant,{'patch':json.dumps(bad)})['exact_match'])

    def test_export_is_separate_disabled_and_records_full_message_provenance(self):
        with tempfile.TemporaryDirectory()as folder:
            report=build(Path(folder),promotion=self.promotion)
            manifest=read_json(Path(folder)/'manifest.json')
            self.assertEqual((report['definitions'],report['prompts'],report['enabled']),(21,62,0))
            self.assertEqual(manifest['reviewed_prompt_promotion']['provenance']['candidate_sha256'],digest(self.promotion['candidate']))
            self.assertEqual(manifest['status'],'pending_joint_prompt_review')
            for prompt in manifest['prompts']:
                if prompt['test_id'].startswith('db_v3_move_'):
                    self.assertFalse(prompt['notation_only_comparison_eligible'])
            self.assertIn('SYSTEM MESSAGE',(Path(folder)/'original930-to-dot.diff').read_text(encoding='utf8'))


if __name__=='__main__':unittest.main()
