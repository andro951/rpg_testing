"""Copy override compatibility without writing or promoting any suite state."""
import copy
import json
import unittest
from unittest.mock import patch
from scripts import generate_paired_suite_240 as generator


class CopyOverrideTests(unittest.TestCase):
    def recipe(self):
        # Small synthetic Bramble-shaped state, not a replacement for its authentic fixture.
        state = {
            'player': {'state_of_mind': 'Concerned',
                       'inventory': ['A folded route map', 'A length of spare twine'],
                       'known_facts': ['Rowan knows Mira.', 'Rowan carries messages.']},
            'npc_directory': {'locations': {'bramble-bridge': {'characters': {
                'Mira Bellweather': {'full_character': {'inventory': ['A workshop key']}}
            }}}},
            'story_memory': {'world_notes': ['The festival begins this evening.']},
        }
        destination = 'npc_directory.locations.bramble-bridge.characters.Mira Bellweather.full_character.inventory'
        identities = [
            {'path': ['player', 'inventory'], 'id_field': None},
            {'path': ['player', 'known_facts'], 'id_field': None},
            {'path': ['npc_directory', 'locations', 'bramble-bridge', 'characters',
                      'Mira Bellweather', 'full_character', 'inventory'], 'id_field': None},
            {'path': ['story_memory', 'world_notes'], 'id_field': None},
        ]
        return {
            'name': 'synthetic_bramble', 'state': state, 'array_identities': identities,
            'source': 'player.inventory', 'destination': destination,
            'selected': 'A length of spare twine',
            'append_path': 'player.inventory', 'new_element': 'A clean cloth',
            'remove_path': 'player.inventory.A length of spare twine',
            'update_path': 'player.state_of_mind', 'update_value': 'Reassured',
            'copy_source': 'player.known_facts', 'copy_selected': 'Rowan knows Mira.',
            'copy_destination': 'story_memory.world_notes', 'originals': [],
        }

    def test_all_current_case_files_remain_byte_identical(self):
        count = 0
        for name, recipe, _, operations, expected, text in generator.cases():
            directory = generator.ROOT / 'prompt_builder/templates/test_cases' / name
            values = {'starting_data.json': recipe['state'],
                      'array_identities.json': recipe['array_identities'],
                      'expected_patch.json': operations,
                      'expected_result.json': expected}
            for filename, data in values.items():
                serialized = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
                self.assertEqual((directory / filename).read_bytes(), serialized, (name, filename))
            self.assertEqual((directory / 'requested_change.txt').read_bytes(), (text + '\n').encode('utf-8'), name)
            count += 1
        self.assertEqual(count, 240)

    def test_bramble_copy_and_move_have_independent_sources_and_destinations(self):
        recipe = self.recipe()
        original = copy.deepcopy(recipe)
        rows = {row[2]: row for row in generator.cases([recipe])}
        copied = rows['copy'][4]
        expected = copy.deepcopy(original['state'])
        expected['story_memory']['world_notes'].append('Rowan knows Mira.')
        self.assertEqual(copied, expected)
        self.assertEqual(rows['copy'][3][0]['path'], 'story_memory.world_notes')
        self.assertTrue(rows['copy'][3][0]['from'].startswith('player.known_facts.'))
        self.assertIn('Rowan knows Mira.', rows['copy'][5])
        self.assertIn('known_facts', rows['copy'][5])
        self.assertIn('world_notes', rows['copy'][5])
        self.assertNotIn('spare twine', rows['copy'][5])
        moved = rows['move'][4]
        self.assertNotIn('A length of spare twine', moved['player']['inventory'])
        self.assertIn('A length of spare twine', moved['npc_directory']['locations']['bramble-bridge']['characters']['Mira Bellweather']['full_character']['inventory'])
        self.assertEqual(moved['story_memory'], original['state']['story_memory'])
        self.assertEqual(rows['no_op'][4], original['state'])
        self.assertEqual(recipe, original)  # Every arm starts from the same unmodified state.

    def test_partial_override_keeps_unspecified_defaults(self):
        recipe = self.recipe()
        del recipe['copy_source']
        del recipe['copy_selected']
        row = next(row for row in generator.cases([recipe]) if row[2] == 'copy')
        self.assertEqual(row[4]['player']['inventory'], recipe['state']['player']['inventory'])
        self.assertEqual(row[4]['story_memory']['world_notes'][-1], 'A length of spare twine')

    def test_expected_mutation_is_independent_of_evaluator_output(self):
        original_apply = generator.apply_patch
        def incorrect_copy(state, operations, identities):
            result = original_apply(state, operations, identities)
            if operations and operations[0]['op'] == 'copy':
                result['final_state']['story_memory']['world_notes'].append('unrequested mutation')
            return result
        with patch.object(generator, 'apply_patch', side_effect=incorrect_copy):
            with self.assertRaises(AssertionError):
                list(generator.cases([self.recipe()]))


if __name__ == '__main__':
    unittest.main()
