"""A reviewed loading-only update must not reopen existing benchmark results."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from workbench import domain
from workbench.planning import pending_plan

ROOT = Path(__file__).resolve().parents[1]


class OperationalSourceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.review = domain.read_json(ROOT / 'workbench/operational-source-compatibility.json')
        self.original = self.review['canonical_workflow_fingerprint']

    def test_only_exact_reviewed_source_preserves_previous_experiment_identity(self):
        current = domain.implementation_fingerprint()
        self.assertEqual(self.review['equivalent_implementations'][current], self.original)
        self.assertEqual(domain.code_fingerprint(), self.original)
        self.assertNotEqual(current, self.original)
        with patch.object(domain, 'implementation_fingerprint', return_value='f' * 64):
            self.assertEqual(domain.code_fingerprint(), 'f' * 64)

    def test_existing_completed_result_keeps_same_id_and_stays_complete(self):
        model = {'id': 'local-fixture', 'files': ['fixture.gguf'], 'required_vram_gb': 8}
        test = domain.read_json(ROOT / 'test_specs/time_only.json')
        variant = test['variants'][0]
        target = {'vram_gb': 8}
        with patch.object(domain, 'code_fingerprint', return_value=self.original):
            original_id = domain.case_id(model, test, variant, 0, target)
        self.assertEqual(domain.case_id(model, test, variant, 0, target), original_id)
        with tempfile.TemporaryDirectory() as folder:
            store = domain.ResultStore(Path(folder))
            store.save({'status': 'completed', 'model_id': model['id'], 'case_id': original_id,
                        'provenance': {'workflow_code': self.original}, 'raw': 'unchanged saved answer'})
            saved = store.path(model['id'], original_id).read_bytes()
            plan = pending_plan([model], [test], target, store,
                                {'model_id': model['id'], 'test_id': test['id'], 'variant_id': variant['id']})
            self.assertEqual(plan['complete'], 1)
            self.assertEqual(plan['pending'], test.get('repetitions', 1) - 1)
            self.assertEqual(store.path(model['id'], original_id).read_bytes(), saved)
