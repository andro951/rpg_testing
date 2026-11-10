"""Pure rendering compatibility without any retired builder imports."""
import copy
import json
import unittest
from tests.helpers.frozen_prompts import INPUTS, snapshots
from workbench.domain import read_json
from workbench.prompt_rendering import full_paths, id_keyed_arrays, preview, render, structure_text
from workbench.workflows import messages


class FrozenRenderingTests(unittest.TestCase):
    def test_saved_original_bindings_reproduce_every_message(self):
        count = 0
        for row in snapshots()['methods']['original_value_patch_v1'].values():
            test = row['definition']
            for variant in test['variants']:
                expected = messages(test, variant['steps'][0], {}, variant)
                self.assertEqual(render(variant['prompt_bindings']), expected)
                self.assertEqual(preview(expected), '\n\n'.join(
                    m['role'].upper() + ' MESSAGE\n\n' + m['content'] for m in expected))
                count += 1
        self.assertEqual(count, 62)

    def test_archived_schema_rendering_and_id_views_remain_exact(self):
        for fixture in read_json(INPUTS / 'fixtures.json')['fixtures']:
            saved = snapshots()['methods']['original_value_patch_v1'][fixture['id']]['definition']
            for variant in saved['variants']:
                bindings = variant['prompt_bindings']
                self.assertTrue(bindings['task_requirements'].endswith(structure_text(fixture['schema'])))
                if variant['id'] == 'full_paths':
                    self.assertEqual('\n'.join(full_paths(fixture['state'], fixture['schema'])), bindings['current_state'])
                elif variant['id'] == 'id_keyed_arrays':
                    self.assertEqual(id_keyed_arrays(fixture['state'], fixture['schema']), json.loads(bindings['current_state']))

    def test_id_view_rejects_collisions_and_preserves_input(self):
        state = [42, '42']
        schema = {'type': 'array', 'uniqueItems': True, 'items': {'type': ['number', 'string']}}
        before = copy.deepcopy(state)
        with self.assertRaisesRegex(ValueError, 'collide'):
            id_keyed_arrays(state, schema)
        self.assertEqual(state, before)


if __name__ == '__main__':
    unittest.main()
