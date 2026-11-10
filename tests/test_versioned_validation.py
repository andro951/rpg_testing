"""Offline lineage, immutable replay and unchanged generation policy."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from evaluation.__main__ import replay
from evaluation.core import assess_record
from evaluation.validation import get_validator
from workbench.domain import ResultStore, code_fingerprint, digest
from tests.test_dot_separator_validator import SCHEMA


def record():
    variant = {'id': 'direct', 'steps': [{'id': 'patch', 'type': 'generate',
               'output': {'type': 'text'}}],
               'result': {'step': 'patch', 'representation': 'dot_patch_v1', 'required_ops': ['replace']}}
    test = {'id': 'synthetic_offline_separator', 'source': {'initial_state': {
        'elements': [{'id': 'a.b', 'value': 'old'}]}}, 'state_schema': SCHEMA,
        'expected_state': {'elements': [{'id': 'a.b', 'value': 'new'}]}, 'variants': [variant]}
    text = json.dumps([{'op': 'replace', 'path': 'elements.a.b.value', 'value': 'new'}])
    return {'case_id': ('a' * 64), 'model_id': 'synthetic-model', 'test_id': test['id'],
            'variant_id': variant['id'], 'test_definition': test, 'status': 'completed',
            'score': {'exact_match': False}, 'outputs': {'patch': text},
            'calls': [{'step': 'patch', 'iteration': 0, 'text': text, 'finish_reason': 'stop'}],
            'provenance': {'workflow_code': 'original-generation-identity'}}


class VersionedValidationTests(unittest.TestCase):
    def test_replay_is_immutable_repeatable_and_preserves_generation_lineage(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp)/'source', Path(tmp)/'output'
            path = ResultStore(source).save(record())
            raw, generation = path.read_bytes(), code_fingerprint()
            first = replay(source, output, validator='dot-separators-v2')
            snapshot = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob('*.json')}
            second = replay(source, output, validator='dot-separators-v2')
            self.assertEqual(first, second)
            self.assertEqual(snapshot, {str(p.relative_to(output)): p.read_bytes() for p in output.rglob('*.json')})
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(code_fingerprint(), generation)
            self.assertEqual(first['outcomes'], {'PASS': 1})
            self.assertEqual(first['score_comparisons'], {'disagreement': 1})
            self.assertFalse(first['problems'])
            assessment = json.loads(next(output.glob('*/assessments/*.json')).read_text())
            self.assertEqual(assessment['original_score'], {'exact_match': False})
            self.assertEqual(assessment['validation_lineage']['generation_case_id'], ('a' * 64))
            self.assertEqual(assessment['validation_lineage']['generation_workflow_fingerprint'], 'original-generation-identity')
            self.assertEqual(assessment['validation_lineage']['outputs_sha256'], digest(record()['outputs']))
            self.assertNotEqual(assessment['validation_id'], assessment['case_id'])
            self.assertEqual(assessment['registration_status'], 'captured_contract_only')

    def test_default_parser_still_rejects_literal_dot(self):
        raw = record()
        raw['variant_definition'] = raw['test_definition']['variants'][0]
        self.assertEqual(assess_record(raw)['objective_outcome'], 'FAIL')
        self.assertEqual(assess_record(raw, validator='dot-separators-v2')['objective_outcome'], 'PASS')

    def test_timeout_is_inconclusive_and_other_methods_are_not_applicable(self):
        raw = record()
        raw['timed_out'] = True
        self.assertEqual(assess_record(raw, validator='dot-separators-v2')['objective_outcome'], 'INCONCLUSIVE')
        with tempfile.TemporaryDirectory() as tmp:
            raw = record()
            raw['test_definition']['variants'][0]['result']['representation'] = 'state'
            ResultStore(Path(tmp)/'source').save(raw)
            summary = replay(Path(tmp)/'source', Path(tmp)/'output', validator='dot-separators-v2')
            self.assertEqual(summary['assessed_records'], 0)
            self.assertEqual(len(summary['not_applicable']), 1)

    def test_checksum_corruption_and_unknown_version_are_not_repaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = ResultStore(Path(tmp)/'source').save(record())
            path.write_text(path.read_text().replace(('a' * 64), 'tampered-case'))
            summary = replay(Path(tmp)/'source', Path(tmp)/'output', validator='dot-separators-v2')
            self.assertEqual(summary['assessed_records'], 0)
            self.assertEqual(len(summary['problems']), 1)
        with self.assertRaises(ValueError):
            get_validator('unknown')

    def test_remote_schema_refs_are_rejected_offline(self):
        raw = record()
        raw['test_definition']['state_schema'] = {'$ref': 'https://example.invalid/schema'}
        with self.assertRaises(ValueError):
            assess_record(raw, validator='dot-separators-v2')


if __name__ == '__main__':
    unittest.main()
