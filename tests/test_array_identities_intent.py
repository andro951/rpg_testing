"""Explicit validator metadata is independent of prompts and final-state oracles."""
import copy
import json
import unittest

from evaluation import array_identities_intent as host
from evaluation import schema_free_intent as legacy
from workbench.domain import validate_test
from workbench.workflows import evaluate


def mapping(path=('items',), field='key'):
    return {'path': list(path), 'id_field': field}


def fixture():
    initial = {'items': [{'key': 'a', 'id': 1, 'owner_id': 8, 'value': 1},
                         {'key': 'b', 'id': 2, 'owner_id': 8, 'value': 2}]}
    expected = copy.deepcopy(initial)
    expected['items'] = [expected['items'][1]]
    expected['items'][0]['value'] = 3
    variant = {'id': 'normal', 'prompt_style': 'direct_text_v1',
               'steps': [{'id': 'patch', 'type': 'generate', 'prompt': 'Update data.', 'output': {'type': 'text'}}],
               'result': {'step': 'patch', 'representation': 'dot_patch_v1',
                          'output_format': 'json_dot', 'evaluator': host.configuration()},
               'expected_patch': [{'op': 'remove', 'path': 'items.a'},
                                  {'op': 'replace', 'path': 'items.b.value', 'value': 3}]}
    return {'schema_version': 2, 'id': 'explicit-identity', 'workflow': 'steps', 'enabled': True,
            'repetitions': 1, 'timeout_seconds': 120,
            'source': {'initial_state': initial, 'array_identities': [mapping()]},
            'expected_state': expected, 'variants': [variant]}


class ArrayIdentityTests(unittest.TestCase):
    def test_stable_after_remove_and_reference_scoring(self):
        test = fixture()
        validate_test(test)
        raw = 'Remove items.a\nUpdate items.b.value = 3'
        # Actual JSON operation format uses the existing grammar, unchanged.
        raw = json.dumps([{'op': 'remove', 'path': 'items.a'},
                          {'op': 'update', 'path': 'items.b.value', 'value': 3}])
        score = evaluate(test, test['variants'][0], {'patch': raw})
        self.assertTrue(score['exact_match'], score)
        self.assertTrue(score['expected_patch_match'], score)
        self.assertEqual(score['evaluation']['version'], host.VERSION)

    def test_arbitrary_exact_names_nested_empty_arrays(self):
        state = {'a.b/~': []}
        declarations = [mapping(('a.b/~',), ''), mapping(('a.b/~', None, 'x.y/~'), None)]
        host.validate_data(state, declarations)
        patch = [{'op': 'add', 'path': 'a%2Eb%2F~', 'value': {'': 'one', 'x.y/~': []}},
                 {'op': 'add', 'path': 'a%2Eb%2F~.one.x%2Ey%2F~', 'value': 'ok'}]
        result = host.apply_patch(state, patch, declarations)
        self.assertEqual(result['final_state']['a.b/~'][0]['x.y/~'], ['ok'])

    def test_root_arrays_and_special_wildcard_property(self):
        data = [{'key': 'a', '*': ['x']}]
        declarations = [mapping((), 'key'), mapping((None, '*'), None)]
        host.validate_data(data, declarations)
        self.assertEqual(host.resolve(data, 'a.*.x', declarations)[0], 'x')

    def test_missing_duplicate_invalid_misleading_metadata(self):
        cases = [None, {}, [mapping(), mapping()], [mapping(field=1)],
                 [{'path': ['items'], 'id_field': 'key', 'type': 'object'}],
                 [mapping(('items', None, 'children'))],
                 [mapping(('absent',))], [mapping(('items', 'not-an-element'))],
                 [mapping(field=None)], [mapping(field='missing')],
                 [mapping(), mapping(('items', None, 'value'))]]
        for metadata in cases:
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                host.validate_data(fixture()['source']['initial_state'], metadata)
        with self.assertRaisesRegex(ValueError, 'Missing array identity'):
            host.validate_data({'items': []}, [])
        with self.assertRaisesRegex(ValueError, 'Primitive identity array'):
            host.validate_data({'items': []}, [mapping(field=None), mapping(('items', None, 'child'))])

    def test_duplicates_typed_collisions_and_mixed_values(self):
        for state in ({'items': [{'key': 'a'}, {'key': 'a'}]},
                      {'items': [{'key': 1}, {'key': '1'}]},
                      {'items': [{'key': []}]}, {'items': [{'key': 'a'}, 'b']}):
            with self.subTest(state=state), self.assertRaises(ValueError):
                host.validate_data(state, [mapping()])
        for values in ([1, 1.0], [1, '1'], ['x', {}], [[1]]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                host.validate_data({'items': values}, [mapping(field=None)])

    def test_append_must_obey_declared_empty_collection_identity(self):
        with self.assertRaisesRegex(ValueError, 'scalar field'):
            host.apply_patch({'items': []}, [{'op': 'add', 'path': 'items', 'value': {'id': 'a'}}], [mapping()])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            host.apply_patch({'items': [{'key': 'a'}]},
                             [{'op': 'add', 'path': 'items', 'value': {'key': 'a'}}], [mapping()])

    def test_absent_optional_descendant_after_removal(self):
        state = {'items': [{'key': 'a', 'children': []}, {'key': 'b'}]}
        result = host.apply_patch(state, [{'op': 'remove', 'path': 'items.a'}],
                                  [mapping(), mapping(('items', None, 'children'), None)])
        self.assertEqual(result['final_state'], {'items': [{'key': 'b'}]})

    def test_expected_state_cannot_supply_identity(self):
        test = fixture()
        del test['source']['array_identities']
        with self.assertRaisesRegex(ValueError, 'array_identities'):
            host.validate_selection(test, test['variants'][0])
        with self.assertRaisesRegex(ValueError, 'array_identities'):
            host.normalize_response('[]', test['source']['initial_state'])

    def test_typed_lines_receives_explicit_context(self):
        state = {'items': [{'key': 'a', 'owner_id': 2}], 'note': 'old', 'tags': []}
        declarations = [mapping(), mapping(('tags',), None)]
        # Exact existing typed-lines syntax, no new selectors or object append.
        result = host.normalize_response('set: /note\ntext: new', state, 'typed_lines', declarations)
        self.assertEqual(result['final_state']['note'], 'new')

    def test_all_prompt_styles_omit_validator_metadata(self):
        from workbench.workflows import messages
        from workbench.domain import PROMPT_STYLES
        test = fixture()
        for style in PROMPT_STYLES:
            variant = {**test['variants'][0], 'prompt_style': style}
            prompts = messages(test, variant['steps'][0], {}, variant)
            self.assertNotIn('array_identities', json.dumps(prompts), style)
            altered = copy.deepcopy(test)
            altered['source']['array_identities'] = [mapping(field='owner_id')]
            self.assertEqual(prompts, messages(altered, variant['steps'][0], {}, variant), style)

    def test_invalid_configuration_is_unscored_not_model_failure(self):
        from evaluation.core import assess_record
        from reporting.matrix import outcome
        from reporting.feedback import summarize
        for alteration in ('missing', 'invalid', 'stale'):
            test = fixture()
            variant = test['variants'][0]
            if alteration == 'missing':
                del test['source']['array_identities']
            elif alteration == 'invalid':
                test['source']['array_identities'] = [mapping(field='missing')]
            else:
                variant['result']['evaluator']['fingerprint'] = 'stale'
            score = evaluate(test, variant, {'patch': '[]'})
            self.assertEqual(score['status'], 'configuration_error')
            self.assertIsNone(score['exact_match'])
            self.assertEqual(score['evaluation']['failure_stage'], 'configuration')
            record = {'status': 'completed', 'test_definition': test, 'variant_definition': variant,
                      'outputs': {'patch': '[]'}, 'score': score, 'calls': []}
            self.assertEqual(outcome(record), 'unscored')
            assessment = assess_record(record)
            self.assertEqual(assessment['objective_outcome'], 'UNSCORED', assessment)
            self.assertEqual(summarize(record)['objective_outcome'], 'UNSCORED')
            self.assertIn('configuration error', summarize(record)['reason'])

    def test_legacy_inference_is_explicitly_retired(self):
        self.assertEqual(legacy.VERSION, 'schema-free-intent-v1')
        self.assertNotEqual(host.VERSION, legacy.VERSION)
        with self.assertRaisesRegex(ValueError, '[Rr]etired'):
            legacy.normalize_response('[]', {'items': [{'id': 'a', 'owner_id': 'x'}]})
        host.validate_data({'items': [{'id': 'a', 'owner_id': 'x'}]}, [mapping(field='id')])


if __name__ == '__main__':
    unittest.main()
