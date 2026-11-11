"""The reviewed suite cannot silently shrink or be relabeled as complete."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from prompt_builder.builder import ROOT, applicable, build, install
from prompt_builder.coverage import contract, runtime_report, validate_manifest
from workbench.domain import read_json, write_json


class SuiteCoverageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.templates = self.base / 'templates'
        shutil.copytree(ROOT, self.templates)
        self.output = self.base / 'build'

    def edit_selection(self, **changes):
        path = self.templates / 'common/selection.json'
        value = read_json(path)
        value.update(changes)
        write_json(path, value)

    def repo(self):
        repo = self.base / 'repo'
        repo.mkdir(exist_ok=True)
        for name, value in {'evaluation/catalog.json': {'definitions': []},
                            'evaluation/fixtures.json': {'fixtures': []},
                            'reporting/grouping_metadata.json': {},
                            'reporting/timing_expectations.json': {}}.items():
            write_json(repo / name, value)
        shutil.copytree(self.templates, repo / 'prompt_builder/templates')
        return repo

    def partial(self, **kwargs):
        return build(self.output, root=self.templates, cases=['update_field'],
                     output_formats=['json_dot'], **kwargs)

    def test_reviewed_full_matrix_and_single_repetition(self):
        manifest = build(self.output, root=self.templates)
        coverage = manifest['coverage']
        self.assertEqual(len(contract(self.templates)['test_cases']), 21)
        self.assertEqual(len(contract(self.templates)['output_formats']), 6)
        self.assertEqual((manifest['prompt_count'], manifest['observations_per_model']), (372, 372))
        self.assertEqual(len(manifest['test_spec_files']), 126)
        self.assertEqual(coverage['scope'], 'full')
        self.assertTrue(coverage['complete'])
        self.assertEqual(coverage['expected']['candidate_prompt_count'], 378)
        self.assertEqual(coverage['expected']['input_variants_by_case']['update_field'], ['full_paths', 'normal_json'])
        self.assertEqual(len(coverage['input_exclusions']), 1)
        self.assertEqual(coverage['omitted']['distinct_prompt_count'], 0)
        self.assertEqual(manifest['unsupported'], [])
        self.assertEqual(validate_manifest(manifest, self.templates), coverage)

    def test_default_selection_cannot_drop_eight_cases_or_an_output_or_input(self):
        original = read_json(self.templates / 'common/selection.json')
        for key, value in [('test_cases', original['test_cases'][:13]),
                           ('output_formats', ['json_dot']), ('input_formats', ['normal_json'])]:
            with self.subTest(dimension=key):
                write_json(self.templates / 'common/selection.json', original)
                self.edit_selection(**{key: value})
                with self.assertRaisesRegex(ValueError, 'complete current suite'):
                    build(self.output, root=self.templates)
                self.assertFalse(self.output.exists())

    def test_missing_required_folders_cannot_redefine_the_suite(self):
        original = read_json(self.templates / 'common/selection.json')
        for case in original['test_cases'][13:]:
            shutil.rmtree(self.templates / 'test_cases' / case)
        self.edit_selection(test_cases=original['test_cases'][:13])
        with self.assertRaisesRegex(ValueError, 'Required test_cases folders missing'):
            build(self.output, root=self.templates)

    def test_missing_active_format_fails_even_if_removed_from_selection(self):
        shutil.rmtree(self.templates / 'output_format/typed_lines')
        s = read_json(self.templates / 'common/selection.json')
        self.edit_selection(output_formats=[f for f in s['output_formats'] if f != 'typed_lines'])
        with self.assertRaisesRegex(ValueError, 'Required output_format folders missing'):
            build(self.output, root=self.templates)

    def test_subset_export_names_every_omission_without_multiplying_prompts(self):
        manifest = self.partial(repetitions=3)
        c = manifest['coverage']
        self.assertEqual((manifest['prompt_count'], manifest['observations_per_model']), (2, 6))
        self.assertFalse(c['complete'])
        self.assertEqual(c['scope'], 'subset')
        self.assertEqual(c['actual']['test_cases'], ['update_field'])
        self.assertEqual(len(c['omitted']['test_cases']), 20)
        self.assertEqual(len(c['omitted']['output_formats']), 5)
        self.assertEqual(c['omitted']['distinct_prompt_count'], 370)
        self.assertEqual(c['omitted']['observations_per_model'], 1110)

    def test_empty_explicit_selector_is_not_implicit_all(self):
        for key in ('cases', 'input_formats', 'output_formats'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'nonempty'):
                build(self.output, root=self.templates, **{key: []})
        for reps in (0, -1, True, 1.5):
            with self.subTest(repetitions=reps), self.assertRaisesRegex(ValueError, 'positive integer'):
                self.partial(repetitions=reps)

    def test_new_case_and_active_format_extend_coverage_without_code_edits(self):
        shutil.copytree(self.templates / 'test_cases/update_field', self.templates / 'test_cases/new_case')
        shutil.copytree(self.templates / 'output_format/json_dot', self.templates / 'output_format/new_json')
        with self.assertRaisesRegex(ValueError, 'complete current suite'):
            build(self.output, root=self.templates)
        s = read_json(self.templates / 'common/selection.json')
        self.edit_selection(test_cases=s['test_cases'] + ['new_case'], output_formats=s['output_formats'] + ['new_json'])
        manifest = build(self.output, root=self.templates)
        self.assertTrue(manifest['coverage']['complete'])
        self.assertEqual((len(manifest['test_cases']), len(manifest['output_formats']), manifest['prompt_count']), (22, 7, 448))

    def test_historical_and_experimental_formats_require_explicit_selection(self):
        s = read_json(self.templates / 'common/selection.json')
        self.edit_selection(output_formats=s['output_formats'] + ['two_line_text'])
        with self.assertRaisesRegex(ValueError, 'noncurrent'):
            build(self.output, root=self.templates)
        manifest = build(self.output, root=self.templates, cases=['update_field'],
                         output_formats=['two_line_text', 'free_format'])
        self.assertEqual(manifest['coverage']['noncurrent_output_formats'], [
            {'output_format': 'free_format', 'status': 'experimental'},
            {'output_format': 'two_line_text', 'status': 'historical'}])
        self.assertFalse(manifest['coverage']['complete'])

    def test_unsupported_combination_is_reported_and_never_complete(self):
        def support(case, form, root=ROOT):
            if case['id'] == 'move_value' and form == 'typed_lines':
                return 'simulated unsupported operation'
            return applicable(case, form, root)
        with patch('prompt_builder.builder.applicable', side_effect=support):
            with self.assertRaisesRegex(ValueError, 'move_value/typed_lines: simulated unsupported operation'):
                build(self.output, root=self.templates)
            self.assertFalse(self.output.exists())
            manifest = build(self.output, root=self.templates, cases=['move_value', 'copy_value'])
            self.assertEqual(manifest['prompt_count'], 33)
            self.assertEqual(manifest['coverage']['scope'], 'subset')
            self.assertFalse(manifest['coverage']['complete'])
            self.assertEqual(manifest['coverage']['unsupported_distinct_prompt_count'], 3)
            self.assertEqual(manifest['unsupported'], [{'test_case': 'move_value', 'output_format': 'typed_lines',
                                                      'reason': 'simulated unsupported operation'}])
            with self.assertRaisesRegex(ValueError, 'subset/incomplete'):
                install(self.output, self.repo())

    def test_partial_install_needs_separate_explicit_opt_in(self):
        self.partial()
        repo = self.repo()
        with self.assertRaisesRegex(ValueError, 'allow-subset-install'):
            install(self.output, repo)
        self.assertFalse((repo / 'test_specs').exists())
        result = install(self.output, repo, allow_subset=True)
        self.assertTrue(result['subset_install_explicitly_allowed'])
        self.assertFalse(read_json(repo / 'prompts/current-suite/manifest.json')['coverage']['complete'])
        with self.assertRaisesRegex(ValueError, 'Run all requires complete'):
            runtime_report(repo)
        with self.assertRaisesRegex(ValueError, 'Run all requires complete'):
            runtime_report(repo, {'model_id': 'one-model'})
        report = runtime_report(repo, {'model_id': 'one-model', 'test_id': 'update_field__json_dot'})
        self.assertEqual(report['run_scope'], 'explicit_subset')
        self.assertEqual(report['run_actual']['distinct_prompt_count'], 2)
        self.assertEqual(report['run_omitted_distinct_prompt_count'], 370)

    def test_tampered_manifest_scope_counts_or_rows_rejected_before_install(self):
        original = self.partial()
        repo = self.repo()
        for field, value in [('coverage', {**original['coverage'], 'complete': True}),
                             ('prompt_count', 372), ('observations_per_model', 372),
                             ('test_cases', ['no_change']), ('unsupported', [{'test_case': 'move_value'}])]:
            with self.subTest(field=field):
                value_manifest = {**copy.deepcopy(original), field: value}
                write_json(self.output / 'manifest.json', value_manifest)
                with self.assertRaises((ValueError, KeyError)):
                    install(self.output, repo, allow_subset=True)
                self.assertFalse((repo / 'test_specs').exists())
        write_json(self.output / 'manifest.json', original)
        original['prompts'][0]['test_case'] = 'no_change'
        write_json(self.output / 'manifest.json', original)
        with self.assertRaisesRegex(ValueError, 'scope'):
            install(self.output, repo, allow_subset=True)

    def test_stale_sources_rejected_before_install(self):
        self.partial()
        repo = self.repo()
        path = repo / 'prompt_builder/templates/common/allowed_changes.txt'
        path.write_text(path.read_text() + '\nChanged after build.')
        with self.assertRaisesRegex(ValueError, 'sources are stale'):
            install(self.output, repo, allow_subset=True)
        self.assertFalse((repo / 'test_specs').exists())

    def test_full_runtime_report_verifies_inventory_enabled_views_and_crlf(self):
        manifest = build(self.output, root=self.templates)
        repo = self.repo()
        install(self.output, repo)
        report = runtime_report(repo)
        self.assertEqual(report['run_actual']['observations_per_model'], 372)
        self.assertEqual(report['run_actual']['distinct_prompt_count'], 372)
        self.assertEqual(report['run_scope'], 'all_current_tests')
        for directory in ('test_specs', 'prompt_builder/templates'):
            for path in (repo / directory).rglob('*'):
                if path.is_file() and path.suffix in ('.txt', '.json'):
                    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        self.assertTrue(runtime_report(repo)['complete'])
        tests = [read_json(path) for path in (repo / 'test_specs').glob('*.json')]
        tests[0]['variants'][0]['enabled'] = False
        with self.assertRaisesRegex(ValueError, 'disabled or rejected'):
            runtime_report(repo, tests=tests)
        path = repo / 'test_specs' / next(iter(manifest['test_spec_files']))
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            runtime_report(repo)

    def test_unregistered_enabled_tests_cannot_hide_outside_reported_scope(self):
        self.partial()
        repo = self.repo()
        install(self.output, repo, allow_subset=True)
        extra = read_json(repo / 'test_specs/update_field__json_dot.json')
        extra['id'] = 'custom_extra'
        extra.pop('prompt_builder')
        write_json(repo / 'test_specs/custom_extra.json', extra)
        with self.assertRaisesRegex(ValueError, 'outside the verified coverage manifest'):
            runtime_report(repo, {'model_id': 'one-model', 'test_id': 'custom_extra'})
        with self.assertRaisesRegex(ValueError, 'outside the verified coverage manifest'):
            runtime_report(repo, {'model_id': 'one-model', 'test_ids': ['update_field__json_dot', 'custom_extra']})
        report = runtime_report(repo, {'model_id': 'one-model', 'test_id': 'update_field__json_dot'})
        self.assertEqual(report['run_actual']['distinct_prompt_count'], 2)
        build(self.output, root=self.templates)
        install(self.output, repo)
        with self.assertRaisesRegex(ValueError, 'Run all includes enabled tests outside'):
            runtime_report(repo)
        extra['enabled'] = False
        write_json(repo / 'test_specs/custom_extra.json', extra)
        self.assertEqual(runtime_report(repo)['run_actual']['distinct_prompt_count'], 372)

    def test_windows_build_pins_and_legacy_raw_pins_survive_linux_install(self):
        import hashlib
        from evaluation.catalog import definition_source_sha256
        def windows_write(path, value):
            write_json(path, value)
            if Path(path).parent.name == 'test_specs':
                Path(path).write_bytes(Path(path).read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        with patch('prompt_builder.builder.write_json', side_effect=windows_write):
            manifest = self.partial()
        spec = self.output / 'test_specs/update_field__json_dot.json'
        self.assertIn(b'\r\n', spec.read_bytes())
        self.assertEqual(manifest['test_spec_files'][spec.name], definition_source_sha256(spec))
        self.assertNotEqual(manifest['test_spec_files'][spec.name], hashlib.sha256(spec.read_bytes()).hexdigest())
        repo = self.repo()
        install(self.output, repo, allow_subset=True)
        selected = {'model_id': 'one-model', 'test_id': 'update_field__json_dot'}
        self.assertEqual(runtime_report(repo, selected)['run_actual']['distinct_prompt_count'], 2)
        # Retain compatibility with already-exported Windows raw-byte pins.
        manifest['test_spec_files'][spec.name] = hashlib.sha256(spec.read_bytes()).hexdigest()
        write_json(self.output / 'manifest.json', manifest)
        install(self.output, repo, allow_subset=True)
        saved = read_json(repo / 'prompts/current-suite/manifest.json')
        self.assertEqual(saved['test_spec_files'][spec.name], definition_source_sha256(repo / 'test_specs' / spec.name))
        self.assertEqual(runtime_report(repo, selected)['run_actual']['distinct_prompt_count'], 2)

    def test_accepted_promotion_refresh_keeps_runtime_hashes_valid(self):
        from optimization.promotion import refresh_current_previews
        from workbench.domain import digest
        from workbench.workflows import messages
        self.partial()
        repo = self.repo()
        install(self.output, repo, allow_subset=True)
        path = repo / 'test_specs/update_field__json_dot.json'
        test = read_json(path)
        test['instructions'] += '\nReviewed general guidance.'
        requests = {v['id']: messages(test, v['steps'][0], {}, v) for v in test['variants']}
        test['prompt_builder']['prompt_digest'] = digest(requests)
        test['prompt_builder']['automatic_promotion'] = {'session_id': 'synthetic-regression'}
        write_json(path, test)
        with self.assertRaisesRegex(ValueError, 'hash'):
            runtime_report(repo, {'model_id': 'one-model', 'test_id': test['id']})
        # A promotion performed on Windows must also remain valid after an LF checkout.
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        refresh_current_previews(repo, {test['id']: test})
        from evaluation.catalog import definition_source_sha256
        saved = read_json(repo / 'prompts/current-suite/manifest.json')
        self.assertEqual(saved['test_spec_files'][path.name], definition_source_sha256(path))
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
        report = runtime_report(repo, {'model_id': 'one-model', 'test_id': test['id']})
        self.assertEqual(report['run_actual']['distinct_prompt_count'], 2)

    def test_preflight_blocks_missing_manifest_before_runtime_or_provider_checks(self):
        from workbench.controller import Controller
        repo = self.repo()
        app = Controller(repo, demo=True)
        with patch('workbench.preflight.build') as native, patch('workbench.perchance.preflight') as remote:
            report, plan = app.build_preflight()
        self.assertFalse(report['ready'])
        self.assertEqual(report['issues'][0]['id'], 'suite_coverage')
        self.assertEqual(plan['pending'], 0)
        native.assert_not_called()
        remote.assert_not_called()


if __name__ == '__main__':
    unittest.main()
