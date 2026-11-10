"""Frozen reviewed-dot artifacts and maintained promotion retain exact controls."""
import copy
import hashlib
import json
import unittest
from optimization.promotion import apply
from optimization.templates import render
from tests.helpers.frozen_prompts import INPUTS, REPO, definition, reference
from workbench.domain import digest, read_json, validate_test
from workbench.workflows import evaluate, messages


class ReviewedDotPromotionTests(unittest.TestCase):
    def setUp(self):
        self.promotion=read_json(INPUTS/'promotions/dot-root-prefix-move-v1.json')
        self.frozen=read_json(REPO/'tests/data/frozen_reviewed_dot_promotion.json')

    def corrected_candidate(self):
        candidate=copy.deepcopy(self.promotion['candidate'])
        candidate['system']=candidate['system'].replace(
            'Flattened slash paths are an input display format, not the output path format. Interpret their components and construct the required output paths.',
            'Flattened input paths use the same dot-path rules as output operation paths.')
        candidate['user']=candidate['user'].replace(
            'Use the required output path syntax even when the input displays slash paths.',
            'Use the same dot-path syntax for flattened input paths and output operation paths.')
        return candidate

    def recipe(self,test):
        candidate=self.corrected_candidate();provenance=self.promotion['provenance']
        return {'review_status':'accepted','candidate':candidate,'candidate_digest':digest(candidate),
                'base_definition_digest':digest(test),'validation':copy.deepcopy(provenance['validation']),
                'session_id':provenance['session_id'],'approval_basis':provenance['approval_basis']}

    def test_corrected_frozen_move_views_and_unchanged_other_operation_controls(self):
        changed=unchanged=0
        for fixture_id,promoted in self.frozen['definitions'].items():
            control=definition(fixture_id,'dot_patch_v1');validate_test(promoted)
            for key in ('source','state_schema','expected_state','repetitions','timeout_seconds','workflow'):
                self.assertEqual(promoted[key],control[key])
            for original,variant in zip(control['variants'],promoted['variants']):
                for key in ('result','cache','state_presentation','prompt_style','prompt_bindings'):
                    self.assertEqual(original[key],variant[key])
                self.assertEqual(original['steps'][0]['sampling'],variant['steps'][0]['sampling'])
                actual=messages(promoted,variant['steps'][0],{},variant)
                if promoted['prompt_builder']['operation']=='move':
                    candidate=self.corrected_candidate()
                    self.assertEqual(actual,render(candidate,{**variant['prompt_bindings'],'prior_outputs':'{}'}))
                    self.assertNotIn('Flattened slash paths',actual[0]['content'])
                    self.assertNotIn('input displays slash paths',actual[-1]['content'])
                    correction=promoted['prompt_builder']['reviewed_prompt_promotion']['input_path_correction']
                    self.assertFalse(correction['exact_winner_messages'])
                    self.assertTrue(correction['historical_candidate_unchanged'])
                    self.assertEqual(correction['applied_candidate_sha256'],digest(candidate))
                    changed+=1
                else:
                    self.assertEqual(promoted,control);unchanged+=1
        self.assertEqual((changed,unchanged),(12,50))
        self.assertEqual(hashlib.sha256((INPUTS/'promotions/dot-root-prefix-move-v1.json').read_bytes()).hexdigest(),self.frozen['promotion_sha256'])

    def test_frozen_promotion_has_distinct_digest_and_no_unreviewed_activation(self):
        for fixture_id,promoted in self.frozen['definitions'].items():
            if promoted['prompt_builder']['operation']!='move':continue
            control=definition(fixture_id,'dot_patch_v1')
            requests={v['id']:messages(promoted,v['steps'][0],{},v) for v in promoted['variants']}
            self.assertEqual(digest(requests),promoted['prompt_builder']['prompt_digest'])
            self.assertNotEqual(control['prompt_builder']['prompt_digest'],promoted['prompt_builder']['prompt_digest'])
            self.assertFalse(promoted['enabled'])
            self.assertEqual(promoted['prompt_builder']['review_status'],'needs_review')

    def test_maintained_promotion_replays_exact_frozen_requests_and_rejects_bad_evidence(self):
        test=definition('db_v3_move_value_empty','dot_patch_v1');recipe=self.recipe(test)
        promoted=apply(test,recipe);saved=self.frozen['definitions']['db_v3_move_value_empty']
        for actual,expected in zip(promoted['variants'],saved['variants']):
            self.assertEqual(messages(promoted,actual['steps'][0],{},actual),messages(saved,expected['steps'][0],{},expected))
        edits=[lambda p:p['candidate'].update(system=p['candidate']['system']+'extra'),
               lambda p:p['validation'].update(passes=35),lambda p:p.update(review_status='pending'),
               lambda p:p.update(base_definition_digest='stale'),lambda p:p['validation'].update(complete=False)]
        for edit in edits:
            edited=copy.deepcopy(recipe);edit(edited)
            with self.subTest(edited=edited),self.assertRaises(ValueError):apply(test,edited)

    def test_runtime_literal_bindings_and_strict_grading_survive_promotion(self):
        test=definition('db_v3_move_record','dot_patch_v1')
        literal='<{task_requirements}> USER_MESSAGE:'
        test['source']['initial_state']['items'][0]['name']=literal
        test['expected_state']['items'][0]['name']=literal
        for variant in test['variants']:variant['prompt_bindings']['current_state']+='\n'+literal
        promoted=apply(test,self.recipe(test));answer=reference('db_v3_move_record','dot_patch_v1')[0]
        for variant in promoted['variants']:
            self.assertIn(literal,variant['steps'][0]['prompt'])
            self.assertTrue(evaluate(promoted,variant,{'patch':json.dumps(answer)})['exact_match'])
            self.assertFalse(evaluate(promoted,variant,{'patch':'```json\n'+json.dumps(answer)+'\n```'})['exact_match'])
            bad=copy.deepcopy(answer);bad[0]['from']='item-17'
            self.assertFalse(evaluate(promoted,variant,{'patch':json.dumps(bad)})['exact_match'])

    def test_all_frozen_promotion_references_still_pass_without_mutating_artifacts(self):
        before=copy.deepcopy(self.frozen);count=0
        for fixture_id,test in self.frozen['definitions'].items():
            answer=reference(fixture_id,'dot_patch_v1')[0]
            for variant in test['variants']:
                self.assertTrue(evaluate(test,variant,{'patch':json.dumps(answer)})['exact_match']);count+=1
        self.assertEqual(count,62);self.assertEqual(self.frozen,before)
