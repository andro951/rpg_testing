"""Validator-only metadata affects trial identity, never optimizer messages."""
import copy
import json
import unittest

from optimization.feedback import EvidencePacket, diagnostic
from optimization.templates import bindings, projection
from prompt_builder.builder import compile_test


class IdentityOptimizerBoundaryTests(unittest.TestCase):
    def record(self):
        secret = 'SECRET_ID_FIELD_AND_PATH'
        return {'variant_definition': {'result': {'evaluator': {'version': 'array-identities-intent-v1'}}},
                'score': {'evaluation': {'version': 'array-identities-intent-v1', 'failure_stage': 'normalization'}},
                'error': secret, 'evaluation': {'objective_outcome': 'FAIL', 'primary_reason': secret,
                    'checks': [{'code': 'intent.normalization', 'status': 'failed',
                                'explanation': secret, 'path': secret, 'field': secret}]},
                'outputs': {'patch': 'MODEL_OUTPUT_RETAINED'},
                'calls': [{'step': 'patch', 'text': 'MODEL_OUTPUT_RETAINED',
                           'messages': [{'role': 'user', 'content': 'PROMPT_RETAINED'}]}]}

    def test_identity_diagnostics_redacted_without_mutating_evidence(self):
        record = self.record()
        original = copy.deepcopy(record)
        packet = EvidencePacket()
        item = packet.trial(record)
        self.assertNotIn('SECRET_ID_FIELD_AND_PATH', json.dumps(item))
        self.assertIn('MODEL_OUTPUT_RETAINED', json.dumps(item))
        self.assertIn('PROMPT_RETAINED', json.dumps(packet.prompts))
        self.assertEqual(record, original)

    def test_legacy_diagnostics_remain_exact(self):
        record = self.record()
        record['variant_definition']['result']['evaluator']['version'] = 'schema-free-intent-v1'
        self.assertEqual(diagnostic(record)['primary_reason'], record['error'])
        self.assertEqual(EvidencePacket().trial(record)['error'], record['error'])

    def test_configuration_check_without_score_is_redacted(self):
        record = self.record()
        del record['score']
        record['evaluation']['checks'][0]['code'] = 'intent.configuration'
        self.assertNotIn('SECRET_ID_FIELD_AND_PATH', json.dumps(EvidencePacket().trial(record)))

    def test_map_changes_trial_identity_but_not_prompt_bindings(self):
        test = compile_test('update_record_field', 'json_dot', input_formats=['normal_json'])
        case = {'test': test, 'variant': test['variants'][0], 'presentation': 'Normal JSON'}
        changed = copy.deepcopy(case)
        changed['test']['source']['array_identities'][0]['id_field'] = 'different-authoritative-field'
        self.assertEqual(bindings(case), bindings(changed))
        for remote in (False, True):
            self.assertNotEqual(projection(case, None, remote), projection(changed, None, remote))
        # The new field must not alter historic trial keys, even if extra metadata is present.
        case['variant']['result']['evaluator']['version'] = 'schema-free-intent-v1'
        changed['variant']['result']['evaluator']['version'] = 'schema-free-intent-v1'
        self.assertEqual(projection(case, None), projection(changed, None))


if __name__ == '__main__':
    unittest.main()
