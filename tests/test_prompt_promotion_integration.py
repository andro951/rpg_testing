"""Saved OPRO guidance survives exact template rebuilds without replacing edits."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from optimization.promotion import apply, rebuild
from prompt_builder.builder import ROOT, build, compile_test
from workbench.domain import digest, read_json, write_json
from workbench.workflows import messages


class TemplatePromotionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.template_root = self.root / 'templates'
        shutil.copytree(ROOT, self.template_root)
        self.base = compile_test('update_field', 'json_dot', root=self.template_root,
                                 input_formats=['normal_json'], promotion_root=self.root)

    def recipe(self, base, label='Reviewed synthetic template'):
        candidate = {'system': label,
                     'user': '${task_requirements}\n${presentation_notes}\n${current_state}\n${new_information}\n${prior_outputs}'}
        return {'base_test': copy.deepcopy(base), 'candidate': candidate, 'candidate_digest': digest(candidate),
                'base_definition_digest': digest(base), 'template_definition_digest': digest(self.base),
                'review_status': 'accepted', 'validation': {'complete': True, 'required': 3, 'passes': 3},
                'session_id': 'synthetic', 'approval_basis': 'Unit-test fixture only'}

    def register(self, recipe):
        write_json(self.root / 'optimization/active_promotions.json',
                   {'version': 1, 'recipes': {self.base['id']: recipe}})

    def compile(self):
        return compile_test('update_field', 'json_dot', root=self.template_root,
                            input_formats=['normal_json'], promotion_root=self.root)

    def export(self, output):
        return build(output, root=self.template_root, cases=['update_field'],
                     input_formats=['normal_json'], output_formats=['json_dot'], promotion_root=self.root)

    def test_compiler_and_export_replay_only_the_exact_base(self):
        recipe = self.recipe(self.base)
        self.register(recipe)
        expected = apply(self.base, recipe)
        self.assertEqual(self.compile(), expected)
        output = self.root / 'export'
        manifest = self.export(output)
        saved = read_json(output / 'test_specs' / (self.base['id'] + '.json'))
        self.assertEqual(saved, expected)
        entry = manifest['prompts'][0]
        request = messages(expected, expected['variants'][0]['steps'][0], {}, expected['variants'][0])
        self.assertEqual(read_json(output / entry['file']), request)
        self.assertEqual(entry['message_digest'], digest(request))
        source = self.template_root / 'common/layout/system.txt'
        source.write_text(source.read_text() + '\nUser-edited instruction.\n')
        edited = source.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Stale OPRO promotion'):
            self.compile()
        self.assertEqual(source.read_bytes(), edited)

    def test_consecutive_promotions_keep_original_template_provenance(self):
        first = apply(self.base, self.recipe(self.base))
        recipe = self.recipe(first, 'Second reviewed synthetic template')
        self.register(recipe)
        self.assertEqual(self.compile(), apply(first, recipe))
        self.assertEqual(self.compile()['prompt_builder']['automatic_promotion']['template_definition_digest'], digest(self.base))

    def test_rebuild_updates_current_previews_and_is_idempotent(self):
        output = self.root / 'export'
        manifest = self.export(output)
        shutil.copytree(output / 'test_specs', self.root / 'test_specs')
        previews = self.root / 'prompts/current-suite'
        shutil.copytree(output / 'prompts', previews)
        write_json(previews / 'manifest.json', manifest)
        recipe = self.recipe(self.base)
        self.register(recipe)
        rebuild(self.root)
        saved = read_json(self.root / 'test_specs' / (self.base['id'] + '.json'))
        self.assertEqual(saved, apply(self.base, recipe))
        variant = saved['variants'][0]
        request = messages(saved, variant['steps'][0], {}, variant)
        target = previews / saved['id'] / variant['id']
        self.assertEqual(read_json(target.with_suffix('.messages.json')), request)
        self.assertEqual(target.with_suffix('.txt').read_text(),
                         'SYSTEM MESSAGE\n' + request[0]['content'] + '\n\nUSER MESSAGE\n' + request[-1]['content'])
        refreshed = read_json(previews / 'manifest.json')['prompts'][0]
        self.assertEqual(refreshed['message_digest'], digest(request))
        self.assertEqual(refreshed['automatic_promotion'], saved['prompt_builder']['automatic_promotion'])
        before = {p: p.read_bytes() for p in previews.rglob('*') if p.is_file()}
        rebuild(self.root)
        self.assertEqual(before, {p: p.read_bytes() for p in previews.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
