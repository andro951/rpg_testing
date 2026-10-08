import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.audit_case_preservation import audit, BASELINE, FINGERPRINT_FILES
from workbench.domain import write_json
from workbench.inventory import automatic_context


class PreservationAuditTests(unittest.TestCase):
    def fixture(self):
        return {'schema_version': 2, 'id': 'audit_fixture', 'name': 'Audit fixture', 'workflow': 'steps',
                'repetitions': 2, 'timeout_seconds': 120, 'provenance': {'presentation': 'full_paths'},
                'source': {'initial_state': {'padding': 'x' * 50000}, 'new_information': ''},
                'variants': [{'id': 'v', 'prompt_style': 'direct_text_v1', 'steps': [
                    {'id': 'answer', 'type': 'generate', 'prompt': 'Return READY.', 'output': {'type': 'text'}}],
                    'result': {'step': 'answer', 'representation': 'answers'}, 'expected_answers': {'answer': 'READY'}}]}

    def run_audit(self, after=None, changed_code=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            test = self.fixture()
            write_json(root / 'test_specs/audit_fixture.json', after or test)
            for name in FINGERPRINT_FILES:
                (root / 'workbench').mkdir(exist_ok=True)
                (root / 'workbench' / name).write_text('original')
            def fake_git(folder, *args):
                if args[0] == 'ls-tree':
                    return b'test_specs/audit_fixture.json\n'
                if args[0] == 'rev-parse':
                    return BASELINE.encode()
                if args[1].endswith(':test_specs/audit_fixture.json'):
                    return json.dumps(test).encode()
                return b'changed' if changed_code else b'original'
            with patch('scripts.audit_case_preservation.git', side_effect=fake_git):
                return audit(root, BASELINE)

    def test_same_full_path_context_projection_and_wrong_answers_stay_completed(self):
        raw = automatic_context([self.fixture()], {'planning.context_length': 2**63 - 1})['allocated_tokens']
        result = self.run_audit()
        self.assertNotEqual(raw, result['context_recipe_before'])
        self.assertEqual(result['context_recipe_before'], result['context_recipe_after'])
        self.assertEqual(result['existing_cases_checked_per_model'], 2)
        self.assertEqual(result['newly_invalidated_old_cases'], 0)
        self.assertFalse(result['inference_performed'])

    def test_actual_prompt_edits_still_fail_the_preservation_guard(self):
        changed = copy.deepcopy(self.fixture())
        changed['variants'][0]['steps'][0]['prompt'] = 'Different request'
        with self.assertRaisesRegex(AssertionError, 'definition|experiment|prompt|request'):
            self.run_audit(changed)

    def test_actual_core_file_edits_still_fail_the_preservation_guard(self):
        with self.assertRaisesRegex(AssertionError, 'Fingerprint-bearing file changed'):
            self.run_audit(changed_code=True)


if __name__ == '__main__':
    unittest.main()
