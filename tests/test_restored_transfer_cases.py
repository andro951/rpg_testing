"""The eight restored tasks retain their data, not historical schema prompts."""
import json
from pathlib import Path
import unittest
from prompt_builder.builder import ROOT, load_case, prompt
from prompt_builder.reference_output import encode
from evaluation.array_identities_intent import normalize_response, unordered


class RestoredTransferCasesTests(unittest.TestCase):
    def test_preserved_eight_tasks_with_current_metadata_and_no_schema_hints(self):
        repository = ROOT.parents[1]
        source = json.loads((repository / 'archives/prompt-builder-inputs/fixtures.json').read_text())
        cases = [case for case in source['fixtures'] if case['task'].startswith(('move_', 'copy_'))]
        self.assertEqual(len(cases), 8)
        for old in cases:
            name = old['id'].removeprefix('db_v3_').replace('_empty', '_to_empty_array')
            with self.subTest(case=name):
                case = load_case(name)
                archived = json.loads((repository / 'archives/pre-template-builder/test_specs' /
                                       (old['id'] + '__value_patch.json')).read_text())
                self.assertEqual(case['starting_data'], old['state'])
                self.assertEqual(case['expected_result'], archived['expected_state'])
                patch = case['expected_patch']
                self.assertEqual(len(patch), 1)
                self.assertEqual(patch[0]['op'], old['task'].split('_')[0])
                self.assertEqual(set(patch[0]), {'op', 'from', 'path'})
                self.assertFalse((ROOT / 'test_cases' / name / 'schema.json').exists())
                for mode in ('normal_json', 'id_keyed_arrays', 'full_paths'):
                    messages = prompt(case, mode, 'json_dot')
                    wording = '\n'.join(message['content'] for message in messages)
                    self.assertNotIn('Database structure:', wording)
                    self.assertNotIn('schema-declared', wording)
                    self.assertNotIn('additionalProperties', wording)
                    self.assertIn(case['requested_change'], wording)

    def test_all_transfer_formats_roundtrip_without_model_or_oracle_normalization_input(self):
        formats = ['json_dot', 'json_slash', 'path_list', 'literal_line',
                   'end_marked_line', 'typed_lines', 'two_line_text', 'free_format']
        for op in ('move', 'copy'):
            for payload in ('value', 'record'):
                for suffix in ('', '_to_empty_array'):
                    case = load_case(f'{op}_{payload}{suffix}')
                    for form in formats:
                        with self.subTest(case=case['id'], output=form):
                            raw = encode(case['starting_data'], case['expected_patch'], form, case['array_identities'])
                            actual = normalize_response(raw, case['starting_data'], form, case['array_identities'])
                            self.assertEqual(unordered(actual['final_state']), unordered(case['expected_result']))
                            self.assertEqual(actual['normalized_patch'], case['expected_patch'])

    def test_all_prompt_arms_keep_scalar_add_example_and_transfer_semantics(self):
        for form in ('json_dot', 'json_slash', 'path_list', 'literal_line', 'end_marked_line', 'typed_lines'):
            case = load_case('move_record')
            wording = '\n'.join(m['content'] for m in prompt(case, 'normal_json', form))
            self.assertIn('Move', wording)
            self.assertIn('Copy', wording)
        wording = (ROOT / 'output_format/json_dot/format.txt').read_text()
        self.assertIn('[{"op":"add","path":"example_places","value":"example-new"}]', wording)


if __name__ == '__main__':
    unittest.main()
