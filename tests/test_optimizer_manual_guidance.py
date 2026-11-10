"""Optional writer-only context, including durable Codex/LPIL propagation."""
import copy
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from optimization import engine
from optimization.engine import Engine, create, generation_packet, packet_messages, settings, update_settings
from optimization.storage import Store
from tests import test_prompt_optimization as fixtures
from tests.test_codex_optimization import OPTIONS, WRITER
from workbench.domain import digest, experiment_spec, write_json

GUIDANCE = 'Missing full paths are widespread. Literal markers: (2{current_state}) <{current_state}> <|text|> `unclosed'


class ManualGuidanceTests(unittest.TestCase):
    def setUp(self):
        fixtures.OptimizationTests.setUp(self)

    def test_absent_empty_and_whitespace_preserve_exact_writer_messages(self):
        packet = generation_packet(self.session, self.cohort['models'], [], self.store)
        absent = copy.deepcopy(self.session)
        absent['settings'].pop('manual_guidance', None)
        expected = packet_messages(absent, packet)
        for value in ('', '   \n\t'):
            session = copy.deepcopy(absent)
            session['settings'] = settings({'manual_guidance': value})
            self.assertEqual(session['settings']['manual_guidance'], '')
            self.assertEqual(packet_messages(session, packet), expected)
        legacy = copy.deepcopy(absent)
        legacy.pop('prompt_builder', None)
        expected = packet_messages(legacy, packet)
        legacy['settings']['manual_guidance'] = ''
        self.assertEqual(packet_messages(legacy, packet), expected)

    def test_supplied_guidance_is_literal_after_lpil_and_present_on_later_rounds(self):
        self.session['settings']['manual_guidance'] = GUIDANCE
        packet = generation_packet(self.session, self.cohort['models'], [], self.store)
        first = packet_messages(self.session, packet)
        self.assertTrue(first[-1]['content'].endswith(GUIDANCE))
        self.assertIn('for prompt writing only', first[-1]['content'])
        self.assertEqual(first[-1]['content'].count(GUIDANCE), 1)
        self.session['attempts'].append({'number': 1, 'status': 'invalid', 'layer': -1})
        later = packet_messages(self.session, packet)
        self.assertTrue(later[-1]['content'].endswith(GUIDANCE))
        self.assertNotEqual(first, later)

    def test_guidance_validation_and_durable_settings_history(self):
        for value in (None, 1, False, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'guidance must be text'):
                settings({'manual_guidance': value})
        update_settings(self.app, self.session['id'], {'max_attempts': 2, 'manual_guidance': GUIDANCE})
        saved = self.store.load(self.session['id'])
        self.assertEqual(saved['settings']['manual_guidance'], GUIDANCE)
        change = self.store.get_evidence(saved['id'], saved['configuration_history'][-1])
        self.assertEqual(change['settings']['manual_guidance'], GUIDANCE)
        with tempfile.TemporaryDirectory() as directory:
            imported = Store(Path(directory))
            imported.import_archive(self.store.export(saved['id']))
            self.assertEqual(imported.load(saved['id'])['settings']['manual_guidance'], GUIDANCE)
        update_settings(self.app, saved['id'], {'max_attempts': 2, 'manual_guidance': ''})
        cleared = self.store.load(saved['id'])
        self.assertEqual(cleared['settings']['manual_guidance'], '')
        previous = self.store.get_evidence(saved['id'], cleared['configuration_history'][-1])
        self.assertEqual(previous['previous']['manual_guidance'], GUIDANCE)

    def test_controller_api_path_accepts_text_and_rejects_nontext_before_dispatch(self):
        payload = {'generator_id': 'local-a', 'settings': {'manual_guidance': GUIDANCE}}
        with patch('optimization.engine.dispatch') as dispatch:
            self.app.start('optimization', payload)
            self.app.thread.join(5)
            self.assertFalse(self.app.thread.is_alive())
            self.assertEqual(dispatch.call_args.args[1]['settings']['manual_guidance'], GUIDANCE)
        with patch('optimization.engine.dispatch') as dispatch, self.assertRaisesRegex(ValueError, 'guidance must be text'):
            self.app.start('optimization', {'generator_id': 'local-a', 'settings': {'manual_guidance': None}})
        dispatch.assert_not_called()

    def test_codex_rounds_save_actual_guidance_without_target_prompt_injection(self):
        with patch('optimization.codex.discover', return_value=OPTIONS):
            session = create(self.app, {'prompt_writer': WRITER, 'settings': {'max_attempts': 2, 'manual_guidance': GUIDANCE}}, self.cohort)
        captured = []
        def generator(app, saved, save):
            saved.setdefault('codex_thread', {'id': 'synthetic-guidance-thread'})
            save()
            def propose(messages, sampling, limit, cancel):
                captured.append(copy.deepcopy(messages))
                text = fixtures.proposal('bad' if len(captured) == 1 else 'good')
                text = re.sub(r'\$\{([A-Za-z_][A-Za-z_0-9]*)\}', r'(1{\1})', text)
                return {'text': text, 'finish_reason': 'stop'}
            return SimpleNamespace(propose=propose, close=lambda: None, load_metadata={})
        with patch('optimization.codex.Generator', side_effect=generator):
            Engine(self.app, session['id'], fixtures.MockRuntime).run(cohort=self.cohort)
        saved = self.store.load(session['id'])
        self.assertEqual(saved['status'], 'perfect')
        self.assertEqual(len(captured), 2)
        for attempt, messages in zip(saved['attempts'], captured):
            request = self.store.get_evidence(saved['id'], attempt['request_evidence'])
            self.assertEqual(request['manual_guidance'], GUIDANCE)
            self.assertEqual(request['manual_guidance_sha256'], digest(GUIDANCE))
            self.assertEqual(request['manual_guidance_scope'], 'prompt_writer_only')
            self.assertEqual(request['messages'], messages)
            self.assertTrue(messages[-1]['content'].endswith(GUIDANCE))
        for record in self.store.observations(saved):
            for call in record.get('calls', []):
                self.assertNotIn(GUIDANCE, str(call.get('request_messages')))


class DotOptimizerScopeTests(unittest.TestCase):
    def test_versioned_dot_contract_is_registered_selected_and_frozen_without_relaxation(self):
        import json
        from tests.helpers.frozen_prompts import definition
        from tools.build_prompt_sharing import build
        from optimization.templates import freeze
        from optimization.selection import targets
        from workbench.judgements import definition_id
        test = definition('db_v3_move_value_empty', 'dot_patch_v1')
        test['enabled'] = True
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root/'test_specs'/(test['id']+'.json'), test)
            labels = {test['id']:{v['id']:{'reviewed_definition':digest(experiment_spec(test,v)), 'task_type':'Array move', 'input_presentation':v['id']}for v in test['variants']}}
            write_json(root/'reporting/grouping_metadata.json', labels)
            data = build(root)
            with patch('optimization.templates.catalog', return_value=data):
                selected = targets(root)
                self.assertEqual(len(selected), 3)
                variant = next(v for v in test['variants'] if v['id']=='id_keyed_arrays')
                scope = freeze(root, {'test_id':test['id'],'variant_id':variant['id'],'definition_id':definition_id(test,variant)})
            self.assertEqual(len(scope['cases']), 3)
            for case in scope['cases'].values():
                self.assertEqual(case['variant']['result']['representation'], 'dot_patch_v1')
                self.assertEqual(case['variant']['result']['required_ops'], ['move'])
                self.assertEqual(case['test']['state_schema'], test['state_schema'])
                self.assertEqual(case['test']['expected_state'], test['expected_state'])


if __name__ == '__main__':
    unittest.main()
