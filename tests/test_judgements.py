"""Manual review persistence and run gates; no real inference."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from reporting.report import build_report, write_report
from reporting.server import ReviewServer
from tests.test_perchance import fixture, FakeBackend
from tests.test_reporting import fixture as report_fixture
from workbench.controller import Controller
from workbench.domain import write_json
from workbench.judgements import JudgementStore, definition_id, load_tests as runnable_tests, review_lock, annotate
from workbench import perchance


class JudgementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.test = fixture()
        self.path = self.root / 'test_specs' / 'fixture.json'
        write_json(self.path, self.test)
        self.store = JudgementStore(self.root)
        self.key = definition_id(self.test, self.test['variants'][0])

    def update(self, status, ids=None):
        return self.store.update(ids or [self.key], status, 'Review reason', 'Test reviewer', 'Evidence note')

    def test_default_and_acceptance_are_runnable_without_result_changes(self):
        self.assertEqual(self.store.read()['entries'], {})
        self.assertEqual(len(runnable_tests(self.path.parent)), 1)
        self.update('accepted')
        self.assertEqual(len(runnable_tests(self.path.parent)), 1)
        self.update('needs_review')
        self.assertEqual(len(self.store.read()['entries'][self.key]['history']), 2)
        self.assertFalse((self.root / 'results').exists())

    def test_reject_persists_and_blocks_options_and_targeted_run(self):
        self.update('rejected')
        self.assertEqual(runnable_tests(self.path.parent), [])
        self.assertTrue(JudgementStore(self.root).read()['entries'][self.key]['blocked'])
        app = Controller(self.root)
        self.assertEqual(app.run_options()['tests'], [])
        with self.assertRaises(ValueError):
            app.start('run', {'selection': {'model_id': perchance.MODEL_ID, 'test_id': self.test['id']}})
        with self.assertRaisesRegex(ValueError, 'permanently blocked'):
            self.update('accepted')
        self.assertEqual(self.store.read()['entries'][self.key]['status'], 'rejected')

    def test_timeout_and_cosmetic_changes_do_not_bypass_but_edited_prompt_does(self):
        self.update('rejected')
        modified = copy.deepcopy(self.test)
        modified.update(timeout_seconds=999, name='Renamed', repetitions=50, enabled=True)
        modified['variants'][0].update(name='Renamed variant', enabled=True)
        self.assertEqual(definition_id(modified, modified['variants'][0]), self.key)
        write_json(self.path, modified)
        self.assertEqual(runnable_tests(self.path.parent), [])
        modified['instructions'] += ' Return only the answer.'
        write_json(self.path, modified)
        new_key = definition_id(modified, modified['variants'][0])
        self.assertNotEqual(new_key, self.key)
        self.assertEqual(len(runnable_tests(self.path.parent)), 1)
        self.assertNotIn(new_key, self.store.read()['entries'])
        self.assertTrue(self.store.read()['entries'][self.key]['blocked'])

    def test_batch_reinstatement_is_atomic(self):
        self.update('rejected')
        other = 'a' * 64
        with self.assertRaises(ValueError):
            self.update('accepted', [other, self.key])
        self.assertNotIn(other, self.store.read()['entries'])

    def test_invalid_catalog_fails_closed(self):
        for payload in ([], {'version': 9, 'entries': {}}, {'version': 1, 'entries': {self.key: []}},
                        {'version': 1, 'entries': {self.key: {'status': 'rejected', 'blocked': False}}},
                        {'version': 1, 'entries': {self.key: {'status': 'accepted', 'blocked': True}}}):
            with self.subTest(payload=payload):
                write_json(self.store.path, payload)
                with self.assertRaises(ValueError): runnable_tests(self.path.parent)

    def test_lock_blocks_cross_thread_review_and_releases_after_exception(self):
        errors = []
        def change():
            try: self.update('rejected')
            except ValueError as error: errors.append(str(error))
        with self.assertRaises(RuntimeError):
            with review_lock(self.root):
                thread = threading.Thread(target=change); thread.start(); thread.join(5)
                self.assertEqual(len(errors), 1)
                self.assertEqual(self.store.read()['entries'], {})
                raise RuntimeError('simulated interrupted run')
        self.update('rejected')

    def test_stale_perchance_plan_rechecks_before_opening_browser(self):
        app = Controller(self.root)
        plan = perchance.plan([self.test], app.settings, {'backend': 'perchance', 'vram_gb': 8},
                             app.store, {'model_id': perchance.MODEL_ID})
        self.assertGreater(plan['pending'], 0)
        self.update('rejected')
        with patch.object(FakeBackend, '__init__', side_effect=AssertionError('Browser must not open')):
            perchance.run(app, {}, plan, FakeBackend)
        self.assertEqual(app.run_total, 0)
        self.assertEqual(app.store.all(), [])


class ReviewServerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        records, specs = report_fixture()
        self.report = build_report(records, specs)
        self.server = ReviewServer(('127.0.0.1', 0), self.root, self.report)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True); thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.key = self.report['matrix']['rows'][0]['definition_id']

    def request(self, payload, token=None, origin=None):
        headers = {'Content-Type': 'application/json', 'X-Judgement-Token': token or self.server.token}
        if origin: headers['Origin'] = origin
        request = Request(self.url + '/api/judgements', json.dumps(payload).encode(), headers, method='POST')
        with urlopen(request) as response: return json.load(response)

    def payload(self, status):
        return {'ids': [self.key], 'status': status, 'reason': 'Reason', 'reviewer': 'Test', 'note': ''}

    def test_defaults_save_reload_and_immutable_rejection(self):
        self.assertTrue(all(row['judgement']['status'] == 'needs_review' for row in self.report['matrix']['rows']))
        self.request(self.payload('accepted'))
        self.assertEqual(JudgementStore(self.root).read()['entries'][self.key]['status'], 'accepted')
        self.request(self.payload('rejected'))
        with self.assertRaises(HTTPError) as error: self.request(self.payload('accepted'))
        self.assertEqual(error.exception.code, 409)
        with urlopen(self.url) as response: html = response.read().decode()
        self.assertIn('"blocked":true', html)
        offline = (self.root / '.local/reports/statistics.html').read_text(encoding='utf-8')
        self.assertNotIn(self.server.token, offline)
        self.assertNotIn('judgement_api', json.loads(offline.split('<script type="application/json" id="evidence-data">', 1)[1].split('</script>', 1)[0]))

    def test_authorization_unknown_ids_and_rebinding(self):
        for kwargs in ({'token': 'wrong'}, {'origin': 'https://example.com'}):
            with self.assertRaises(HTTPError) as error: self.request(self.payload('accepted'), **kwargs)
            self.assertEqual(error.exception.code, 403)
        payload = self.payload('accepted'); payload['ids'] = ['b' * 64]
        with self.assertRaises(HTTPError) as error: self.request(payload)
        self.assertEqual(error.exception.code, 409)
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.url, headers={'Host': 'evil.example'}))
        self.assertEqual(error.exception.code, 403)
        self.assertFalse((self.root / 'test_judgements.json').exists())

    def test_regeneration_refreshes_live_server(self):
        changed = copy.deepcopy(self.report)
        changed['matrix']['rows'].pop()
        write_report(changed, self.root / '.local/reports/statistics.html')
        self.server.refresh()
        self.assertEqual(len(self.server.snapshot['matrix']['rows']), len(changed['matrix']['rows']))
        self.assertEqual(len(self.report['matrix']['rows']), len(changed['matrix']['rows']) + 1)

    def test_complete_evidence_endpoint_preserves_multiline_text(self):
        cid, summary = next(iter(self.report['matrix']['records'].items()))
        original = {'case_id': cid, 'calls': [{'messages': [{'role': 'user', 'content':
                    'Current State:\n{\n  "tickets": ["first", "second"]\n}\nReturn only the answer.'}],
                    'text': '[{"op":"replace","path":"/tickets/0","value":"updated"}]'}]}
        path = self.root / 'results' / summary['metadata']['model_id'] / (cid + '.json')
        write_json(path, original)
        before = path.read_bytes()
        with urlopen(self.url + '/evidence/' + cid) as response:
            self.assertEqual(json.load(response), original)
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + '/evidence/' + '0' * 64)
        self.assertEqual(error.exception.code, 404)
