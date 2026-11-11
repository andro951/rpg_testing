"""Retired Ember decoder cannot run; captured source and results remain viewable."""
import copy
import hashlib
import json
import shutil
import subprocess
import unittest
from unittest.mock import patch
from evaluation.core import assess, assess_record
from reporting.feedback import summarize
from reporting.matrix import build_matrix
from tests.helpers.frozen_prompts import REPO, definition
from workbench.domain import read_json, validate_test
from workbench.scoring import apply, score_state
from workbench.workflows import evaluate, execute, messages

VALID=[
 'none',' \ufeffnone\n','set: /a\ntext:', 'set: /a\ntext: hello: world',
 'set: /a\ntext: {"literal":true}', 'set: /a\ntext: "literal quotes"',
 'set: /a\ntext: leading  and  trailing  \n\nset: /b\ntext: last',
 'set: /a\ntext:  two leading spaces', 'set: /a\ntext: false',
 'set: /a\nnumber: +2','set: /a\nnumber: -0','set: /a\nnumber: -12.25',
 'set: /a\nnumber: 9007199254740993','set: /a\nboolean: false','set: /a\nboolean: true',
 'set: /a\nnull:', 'set: /a\nlist: \t\n\nset: /b\nobject:\t',
 'append: /a\ntext: one\nappend: /a\ntext: two','remove: /a',
 'change: /a\nnumber: 1\n\nset: /a\nnumber: 4',
 'set: /key~1ring~0mark\ntext: x','set: /a.b/with spaces/雪\ntext: snow ☃',
 'set: /a\r\ntext: CRLF\r\n\r\nremove: /b',
 'set: /a\ntext: final spaces are trimmed   ',
 'set: /a~01b\ntext: exact escape order',
]
INVALID=[
 '', ' ', '{}','[]','```\nnone\n```','None','none\nset: /a\ntext: x',
 'set: a\ntext: x','set: /\ntext: x','set: /a//b\ntext: x','set: /a/~2\ntext: x',
 'set: /constructor/x\ntext: x','set: /a/__proto__/x\ntext: x','set: /prototype\ntext: x',
 'set: /a','set: /a\n\ntext: x','set: /a\nnumber: 01','set: /a\nnumber: 1e2',
 'set: /a\nnumber: .2','set: /a\nnumber: Infinity','set: /a\nnumber: NaN',
 'set: /a\nnumber: ١','set: /a\nnumber: '+('9'*400),
 'set: /a\nboolean: yes','set: /a\nnull: value','set: /a\nobject: {}','set: /a\nlist: []',
 'change: /a\ntext: 1','remove: /a\ntext: x','move: /a\ntext: /b','copy: /a\ntext: /b',
 'set: /a\ntext: x\nset: /a\ntext: y','set: /a\ntext: x\n  set: /b\ntext: y',
 'set: /a\ntext: first\nsecond','set: /a\ntext: x\u2028y',
]

class EmberTextTests(unittest.TestCase):
    def test_vendored_source_is_immutable_test_artifact(self):
        source = REPO / 'tests/fixtures/ember_source/ember_ai_response_text_v1.js'
        original = source.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        self.assertEqual(hashlib.sha256(original).hexdigest(), read_json(source.with_suffix('.provenance.json'))['sha256'])
        node = shutil.which('node')
        if not node:
            self.skipTest('Node unavailable: retained source fixture hash was checked')
        code = "const fs=require('fs'),c=require(process.argv[1]);process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(s=>{try{c.operations(s);return true}catch(e){return false}})));"
        result = subprocess.run([node, '-e', code, str(source)], input=json.dumps(VALID + INVALID),
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), [True] * len(VALID) + [False] * len(INVALID))
        for name in ('ember_text.py', 'field_values.py'):
            self.assertFalse((REPO / 'workbench' / name).exists())

    def test_retired_contracts_fail_before_generation_and_do_not_guess_semantics(self):
        for representation in ('ember_text_v1', 'field_value_v2'):
            test = definition('db_v3_update_field', 'ember_text_v1')
            variant = test['variants'][0]
            variant['result']['representation'] = representation
            raw = 'set: /profile/hair\ntext: black'
            with self.subTest(representation=representation):
                with self.assertRaisesRegex(ValueError, 'Retired response contract'):
                    validate_test(test)
                backend = unittest.mock.Mock()
                with self.assertRaisesRegex(ValueError, 'Retired response contract'):
                    execute(test, variant, backend)
                backend.generate.assert_not_called()
                with self.assertRaisesRegex(ValueError, 'Retired response contract'):
                    apply(test['source']['initial_state'], raw, representation, test['state_schema'])
                for score in (evaluate(test, variant, {'patch': raw}), score_state(test, raw, representation)):
                    self.assertEqual(score['status'], 'configuration_error')
                    self.assertEqual(score['contract_status'], 'retired')
                    self.assertIsNone(score['exact_match'])
                self.assertEqual(assess(test, variant, {'patch': raw})['objective_outcome'], 'UNSCORED')

    def test_saved_historical_scores_and_raw_evidence_never_regrade(self):
        files = sorted((REPO / 'experiments/ember-text-v1/runs/unity-revised-20261103/typed_line/results').glob('*/*.json'))
        self.assertTrue(files)
        checked = set()
        for path in files:
            record = read_json(path)
            exact = record.get('score', {}).get('exact_match')
            if type(exact) is not bool or exact in checked:
                continue
            checked.add(exact)
            before = path.read_bytes()
            snapshot = copy.deepcopy(record)
            with patch('evaluation.core.patch_checks', side_effect=AssertionError('No retired regrading')):
                assessment = assess_record(record)
                feedback = summarize(record)
                matrix = build_matrix([record], [], 'different-current-code')
            expected = 'PASS' if exact else 'FAIL'
            self.assertEqual(assessment['objective_outcome'], expected)
            self.assertEqual(feedback['objective_outcome'], expected)
            self.assertEqual(assessment['score_comparison'], 'preserved')
            self.assertEqual(assessment['original_score'], snapshot['score'])
            self.assertEqual(assessment['raw_outputs'], snapshot['outputs'])
            self.assertEqual(assessment['raw_calls'], snapshot['calls'])
            self.assertEqual(matrix['records'][record['case_id']]['outcome'], expected.lower())
            self.assertIn('no regrading', feedback['reason'])
            self.assertEqual(record, snapshot)
            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(checked, {True, False})

    def test_saved_prompts_can_still_be_viewed_without_decoder(self):
        frozen = REPO / 'experiments/ember-text-v1/runs/unity-revised-20261103'
        files = sorted((frozen / 'test_specs').glob('*.json'))
        before = {p: p.read_bytes() for p in files}
        count = 0
        for path in files:
            saved = read_json(path)
            for variant in saved['variants']:
                expected = read_json(frozen / 'prompts' / saved['id'] / (variant['id'] + '.messages.json'))
                self.assertEqual(messages(saved, variant['steps'][0], {}, variant), expected)
                count += 1
        self.assertEqual((len(files), count), (4, 11))
        self.assertEqual(before, {p: p.read_bytes() for p in files})


if __name__ == '__main__':
    unittest.main()
