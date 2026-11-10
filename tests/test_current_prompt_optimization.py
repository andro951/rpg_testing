"""Create current-template OPRO sessions for every decoder without model calls."""
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from evaluation.schema_free_intent import OUTPUT_FORMATS
from optimization.engine import create, generation_packet, packet_messages
from optimization.storage import Store
from prompt_builder.builder import compile_test
from tools.build_prompt_sharing import build as sharing
from workbench.domain import digest, experiment_spec, write_json

REPO = Path(__file__).resolve().parents[1]


class CurrentTemplateOptimizationTests(unittest.TestCase):
    def test_current_builder_routes_all_formats_to_schema_free_task(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('optimization/definitions', 'docs/prompt-optimization'):
                shutil.copytree(REPO / folder, root / folder)
            tests = {}
            groups = {}
            for output_format in OUTPUT_FORMATS:
                test = compile_test('update_field', output_format, input_formats=['normal_json'], promotion_root=root)
                write_json(root / 'test_specs' / (test['id'] + '.json'), test)
                tests[output_format] = test
                groups[test['id']] = {v['id']: {'reviewed_definition': digest(experiment_spec(test, v)),
                    'task_type': 'Schema-free database update', 'input_presentation': v['id']} for v in test['variants']}
            write_json(root / 'reporting/grouping_metadata.json', groups)
            catalog = sharing(root)
            model = {'id': 'synthetic-native', 'identity': 'synthetic', 'provider': 'native'}
            cohort = {'models': [model], 'simulated': True}
            app = SimpleNamespace(root=root)
            with patch('optimization.templates.catalog', return_value=catalog), patch('optimization.engine.discover') as discover:
                for output_format, test in tests.items():
                    with self.subTest(output_format=output_format):
                        target = {'test_id': test['id'], 'variant_id': 'normal_json'}
                        session = create(app, {'generator_id': model['id'], 'target': target}, cohort)
                        definition = session['definition']
                        self.assertEqual(definition['id'], 'file_template_prompt_optimization')
                        self.assertEqual(definition['target']['test_id'], test['id'])
                        self.assertEqual(definition['selected_output_format'], output_format)
                        self.assertEqual(set(definition['scope_plan']['output_formats']), set(OUTPUT_FORMATS))
                        self.assertEqual(definition['prompt_files']['task_definition'], 'schema-free-task.txt')
                        self.assertNotIn('one move', json.dumps(definition))
                        self.assertNotIn('predefined database structure', json.dumps(definition))
                        self.assertEqual(set(definition['required_labels']),
                            {'current_state', 'new_information', 'task_requirements', 'presentation_notes', 'prior_outputs'})
                        packet = generation_packet(session, [model], [], Store(root))
                        self.assertEqual(packet['scope']['starting_output_format'], output_format)
                        self.assertEqual(set(packet['scope']['output_formats']), set(OUTPUT_FORMATS))
                        request = packet_messages(session, packet)
                        self.assertEqual([m['role'] for m in request], ['user'])
                        self.assertIn("that member's supplied output-format instructions", request[0]['content'])
                        self.assertNotIn('containing one move operation', request[0]['content'])
                        self.assertNotIn('predefined database structure', request[0]['content'])
                        self.assertEqual(session['attempts'], [])
                        self.assertEqual(session['observations'], [])
                # Existing API clients without a target can choose a current
                # reviewed origin even after the historical Move suite retires.
                session = create(app, {'generator_id': model['id']}, cohort)
                self.assertEqual(session['definition']['id'], 'file_template_prompt_optimization')
                discover.assert_not_called()


if __name__ == '__main__':
    unittest.main()
