"""Offline adapter safety tests; synthetic responses, never model inference."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from evaluation.intent_replay import analyze_records, main
from workbench.domain import ResultStore


def record(text='update ["items", "a", "count"] = 2'):
    return {'case_id': 'synthetic-case', 'test_id': 'synthetic-test', 'variant_id': 'direct',
            'status': 'completed', 'outputs': {'patch': text}, 'calls': [],
            'test_definition': {'source': {'initial_state': {'items': [{'id': 'a', 'count': 1}]}},
                                'expected_state': {'SECRET_ORACLE': True}},
            'variant_definition': {'result': {'representation': 'intent', 'step': 'patch'},
                                   'expected_answers': {'SECRET_ANSWER': True}},
            'score': {'exact_match': False}}


class IntentReplayTests(unittest.TestCase):
    def test_oracles_never_enter_parser_and_inputs_are_unchanged(self):
        saved = record(); original = copy.deepcopy(saved)
        with patch('evaluation.intent_replay.replay_prepared') as replay:
            replay.return_value = {'results': [{'accepted': False, 'error': 'synthetic rejection'}]}
            result = analyze_records([saved], {'idKey': 'id'})
        prepared, options = replay.call_args.args
        self.assertEqual(prepared, [{'input': saved['test_definition']['source']['initial_state'],
                                     'output': saved['outputs']['patch']}])
        self.assertNotIn('SECRET', json.dumps(prepared))
        self.assertEqual(options, {'idKey': 'id'})
        self.assertEqual(saved, original)
        self.assertEqual(result['analyzed'], 1)
        self.assertFalse(result['liveInference'])
        self.assertFalse(result['benchmarkScoresChanged'])

    def test_incomplete_missing_and_answer_contracts_skip_without_parsing(self):
        records = []
        for change in ({'status': 'error'}, {'timed_out': True}, {'outputs': {}},
                       {'calls': [{'finish_reason': 'length'}]},
                       {'calls': [{'finish_reason': 'stop', 'incomplete': True}]},
                       {'variant_definition': {'result': {'representation': 'answers'}}}):
            value = record(); value.update(change); records.append(value)
        with patch('evaluation.intent_replay.replay_prepared') as replay:
            result = analyze_records(records)
        replay.assert_not_called()
        self.assertEqual(result['skipped'], 6)

    def test_legacy_rfc_and_unknown_dialects_are_not_reinterpreted(self):
        records = []
        # RFC add can replace a field or insert positionally. Neither is append.
        for dialect in ('json_patch', 'semantic', None, 'unknown'):
            saved = record('[{"op":"add","path":"/items/0","value":42}]')
            saved['variant_definition']['result']['representation'] = dialect
            records.append(saved)
        with patch('evaluation.intent_replay.replay_prepared') as replay:
            result = analyze_records(records)
        replay.assert_not_called()
        self.assertEqual(result['skipped'], 4)
        for item, dialect in zip(result['results'], ('json_patch', 'semantic', None, 'unknown')):
            self.assertEqual(item['source_dialect'], dialect)
            self.assertIn('Unsupported captured source dialect', item['reason'])

    def test_value_patch_delegates_only_text_state_schema_to_schema_host(self):
        saved = record('[{"op":"replace","path":"/items/\\"a\\"/count","value":2}]')
        saved['variant_definition']['result']['representation'] = 'value_patch'
        schema = {'type': 'object'}
        saved['test_definition']['state_schema'] = schema
        with patch('evaluation.intent_replay.replay_prepared') as generic, \
             patch('evaluation.value_intent.replay_value_intent') as host:
            host.return_value = {'accepted': False, 'error': 'synthetic'}
            result = analyze_records([saved])
        generic.assert_not_called()
        self.assertEqual(host.call_args.args, (saved['outputs']['patch'],
            saved['test_definition']['source']['initial_state'], schema, {}))
        self.assertNotIn('SECRET', json.dumps(host.call_args.args))
        self.assertEqual(result['analyzed'], 1)

    def test_explicit_compatible_dialects_reach_parser(self):
        records = []
        for dialect in ('intent',):
            saved = record('[]')
            saved['variant_definition']['result']['representation'] = dialect
            records.append(saved)
        result = analyze_records(records)
        self.assertEqual(result['accepted'], 1)
        self.assertEqual([r['source_dialect'] for r in result['results']], ['intent'])


    def test_actual_parser_runs_without_network_or_subprocess(self):
        saved = record('[]'); original = copy.deepcopy(saved)
        with patch('socket.socket', side_effect=AssertionError('Network prohibited')), \
             patch('subprocess.Popen', side_effect=AssertionError('Backend prohibited')):
            result = analyze_records([saved, record('not an intent')])
        self.assertEqual(result['analyzed'], 2)
        self.assertTrue(result['results'][0]['diagnostic']['accepted'])
        self.assertEqual(result['results'][0]['diagnostic']['finalState'],
                         saved['test_definition']['source']['initial_state'])
        self.assertFalse(result['results'][1]['diagnostic']['accepted'])
        self.assertEqual(saved, original)
        # Import in a clean interpreter proves this adapter does not load inference modules.
        code = ('import sys; from evaluation.intent_replay import analyze_records; '
                'assert "workbench.native" not in sys.modules; '
                'assert "rpgbench.backends" not in sys.modules')
        subprocess.run([sys.executable, '-c', code], check=True, cwd=Path(__file__).resolve().parents[1])

    def test_cli_preserves_evidence_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'evidence'; source.mkdir()
            # Match Workbench's model/case layout and checksum sealing.
            store = ResultStore(source)
            value = record('not an intent'); value.update(model_id='model', case_id='a'*64)
            evidence = store.save(value)
            before = hashlib.sha256(evidence.read_bytes()).hexdigest()
            output = root/'diagnostics.json'
            self.assertEqual(main(['--source', str(source), '--output', str(output)]), 0)
            self.assertEqual(json.loads(output.read_text())['analyzed'], 1)
            self.assertEqual(hashlib.sha256(evidence.read_bytes()).hexdigest(), before)
            with self.assertRaises(FileExistsError):
                main(['--source', str(source), '--output', str(output)])
            with self.assertRaises(SystemExit):
                main(['--source', str(source), '--output', str(source/'new.json')])
            self.assertFalse((source/'new.json').exists())


if __name__ == '__main__':
    unittest.main()
