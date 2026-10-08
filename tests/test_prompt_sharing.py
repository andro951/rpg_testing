import copy
import unittest
from collections import Counter
from pathlib import Path
from optimization.catalog import catalog, expansion, locate, registration, rendered, steps, validate
from workbench.domain import code_fingerprint, read_json

ROOT = Path(__file__).resolve().parents[1]


def definition(filename, variant_index=0):
    test = read_json(ROOT / 'test_specs' / (filename + '.json'))
    return test, test['variants'][variant_index]


class PromptSharingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = catalog()

    def test_complete_coverage_and_every_reviewed_span(self):
        result = validate(data=self.data)
        self.assertEqual((result['definitions'], result['variants']), (61, 179))
        eligible = [e for e in self.data['variants'].values() if e['objective_optimization_eligible']]
        self.assertEqual(len(eligible), 159)
        self.assertEqual(Counter(e['output_contract'] for e in eligible),
                         {'json_patch': 123, 'semantic': 12, 'answers': 24})

    def test_formatter_expands_without_crossing_output_contracts(self):
        test, variant = definition('array_patch_move_007')
        layers = expansion(test, variant, 'json_patch_formatting', self.data)
        self.assertEqual([len(s['members']) for s in layers[:2]], [1, 3])
        self.assertEqual(len(layers[2]['members']), 18)
        self.assertEqual(len(layers[-1]['members']), 123)
        for layer in layers:
            self.assertTrue(all(self.data['variants'][k]['output_contract'] == 'json_patch' for k in layer['members']))
        with self.assertRaisesRegex(ValueError, 'Incompatible'):
            expansion(test, variant, 'semantic_formatting', self.data)

    def test_move_and_inventory_task_wording_stop_at_their_families(self):
        for filename, expected in [('array_patch_move_007', 3), ('inventory_net_stock_001', 6)]:
            test, variant = definition(filename)
            layers = expansion(test, variant, 'task_instructions', self.data)
            self.assertEqual(len(layers[-1]['members']), expected)
            self.assertEqual(layers[-1]['models'], 'all_eligible_models')
            self.assertEqual(layers[-1]['repetitions'], 'full_configured_count')

    def test_pair_and_single_index_formatting_are_separate(self):
        test, variant = definition('array_index_move_013')
        self.assertEqual(len(expansion(test, variant, 'pair_index_formatting', self.data)[-1]['members']), 3)
        with self.assertRaises(ValueError):
            expansion(test, variant, 'single_index_formatting', self.data)
        test, variant = definition('array_index_replace_010')
        self.assertEqual(len(expansion(test, variant, 'single_index_formatting', self.data)[-1]['members']), 21)
        self.assertEqual(len(expansion(test, variant, 'index_location', self.data)[-1]['members']), 24)

    def test_embedded_data_and_required_operations_remain_outside_formatter_slot(self):
        test, variant = definition('array_patch_move_007_full_paths')
        entry = registration(test, variant, self.data)
        slot = entry['components']['json_patch_formatting']['slots'][0]
        resolved = locate(test, variant, slot, self.data)
        text = resolved['text']
        self.assertIn('tickets.0.ticket_id:', text)
        self.assertIn('exactly one move operation', text)
        self.assertEqual((resolved['start'], resolved['end']), (len(text), len(text)))
        self.assertEqual(entry['constraints']['required_ops'], ['move'])

    def test_analysis_edit_preserves_embedded_input_and_workflow(self):
        test, variant = definition('household_coat_add_003_full_paths', 1)
        entry = registration(test, variant, self.data)
        slot = entry['components']['analysis_instructions']['slots'][0]
        resolved = locate(test, variant, slot, self.data)
        self.assertIn('Current State:', resolved['text'][:resolved['start']])
        self.assertNotIn('Current State:', slot['original_text'])
        final = entry['constraints']['workflow'][-1]
        self.assertEqual(final['uses'], ['analysis'])
        self.assertEqual(len(expansion(test, variant, 'analysis_instructions', self.data)[-1]['members']), 21)
        direct = test['variants'][0]
        with self.assertRaises(ValueError):
            expansion(test, direct, 'analysis_instructions', self.data)

    def test_legacy_system_span_preserves_presentation_instruction(self):
        for filename, expected in [('prompt_calibration_001_time', 'SOURCE is an indexed view'),
                                   ('prompt_calibration_001_time_v1_full_paths', 'SOURCE is a flattened dot-path view')]:
            test, variant = definition(filename)
            entry = registration(test, variant, self.data)
            span = locate(test, variant, entry['components']['established_facts']['slots'][0], self.data)
            self.assertIn(expected, span['text'][span['end']:])

    def test_task_wording_does_not_cross_semantic_patch_contract(self):
        test, variant = definition('clothing_append')
        members = expansion(test, variant, 'task_instructions', self.data)[-1]['members']
        self.assertTrue(all(self.data['variants'][k]['output_contract'] == 'json_patch' for k in members))

    def test_changed_input_prompt_or_oracle_requires_review(self):
        test, variant = definition('array_patch_move_007')
        for field in ('source', 'expected_state', 'instructions'):
            changed = copy.deepcopy(test)
            changed[field] = {'changed': True} if field != 'instructions' else 'Different instructions'
            with self.assertRaisesRegex(ValueError, 'stale'):
                registration(changed, variant, self.data)
        changed_variant = copy.deepcopy(variant)
        changed_variant['steps'][0]['prompt'] += ' Changed'
        with self.assertRaisesRegex(ValueError, 'stale'):
            registration(test, changed_variant, self.data)

    def test_timeout_change_keeps_compatibility_and_native_identity(self):
        test, variant = definition('array_patch_move_007')
        test['timeout_seconds'] += 100
        registration(test, variant, self.data)
        self.assertEqual(code_fingerprint(), '56502881bc3c89f6b58c8f5e755b32f58cbd675274ed5363293b598aaddf9787')

    def test_dialogue_and_inactive_examples_cannot_expand(self):
        test, variant = definition('dialogue_test')
        self.assertEqual(registration(test, variant, self.data)['exclusion'], 'dialogue_quality_rubric_required')
        with self.assertRaisesRegex(ValueError, 'outside'):
            expansion(test, variant, 'task_instructions', self.data)
        test = read_json(ROOT / 'examples/test_specs/verify_repair.json')
        with self.assertRaisesRegex(ValueError, 'outside'):
            expansion(test, test['variants'][0], 'task_instructions', self.data)

    def test_incompatible_scope_member_is_rejected(self):
        changed = copy.deepcopy(self.data)
        test, variant = definition('array_patch_move_007')
        scope = expansion(test, variant, 'json_patch_formatting', changed)[-1]
        scope['members'].append('array_index_move_013/raw_array_index')
        with self.assertRaisesRegex(ValueError, 'Incompatible'):
            validate(data=changed)

    def test_tampered_span_is_rejected(self):
        test, variant = definition('array_patch_move_007')
        slot = copy.deepcopy(registration(test, variant, self.data)['components']['json_patch_formatting']['slots'][0])
        slot['end'] += 1
        with self.assertRaisesRegex(ValueError, 'stale'):
            locate(test, variant, slot, self.data)

    def test_caller_cannot_retarget_a_slot_into_input_text(self):
        test, variant = definition('array_patch_move_007_full_paths')
        slot = copy.deepcopy(registration(test, variant, self.data)['components']['json_patch_formatting']['slots'][0])
        text = locate(test, variant, slot, self.data)['text']
        start = text.index('tickets.0.ticket_id:')
        slot.update(start=start, end=start+len('tickets.0.ticket_id:'), original_text='tickets.0.ticket_id:')
        with self.assertRaisesRegex(ValueError, 'unregistered'):
            locate(test, variant, slot, self.data)
