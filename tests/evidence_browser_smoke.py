"""Result tabs: complete readable evidence, exact message order and honest load errors."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
from playwright.sync_api import sync_playwright, expect
from reporting.report import build_report
from reporting.server import ReviewServer, ReviewHandler
from tests.test_result_feedback import record
from tests.suite_fixtures import LEGACY_ROOT
from workbench.domain import digest, read_json, write_json


class ExistingViewerHandler(ReviewHandler):
    def do_GET(self):
        if self.path == '/result/':
            self.reply(404, {'error': 'Not found'})
        else:
            super().do_GET()


class ExistingViewerServer(ReviewServer):
    """Pre-update route/payload contract, serving today's JavaScript from disk."""
    def __init__(self, *args):
        super().__init__(*args)
        self.RequestHandlerClass = ExistingViewerHandler

    def rendered(self, evidence_view=False):
        html = super().rendered(evidence_view)
        return html.replace(b'"result_tab_url":"/result/",', b'')


def main():
    value = record()
    value['score']['exact_match'] = False
    text = 'Current State:\n{\n  "tickets": [\n    {"ticket_id": "SR-22345"}\n  ]\n}\n\nReply exactly. <script>window.injected = true</script>'
    result = '[{"op":"move","from":"tickets.1","path":"tickets.2"}]'
    value['outputs'][value['variant_definition']['result']['step']] = result
    value['calls'] = [
        {'step': 'prepare', 'messages': [{'role': 'user', 'content': 'ORIGINAL NOT SENT'}],
         'request_messages': [{'role': 'system', 'content': 'System instructions\nSecond line'},
                              {'role': 'user', 'content': text}],
         'text': 'First response\n' + 'Full saved text.\n' * 450, 'finish_reason': 'stop'},
        {'step': value['variant_definition']['result']['step'],
         'messages': [{'role': 'user', 'content': '{"literal":true}'}],
         'text': result, 'finish_reason': 'stop', 'reasoning_text': 'First line\nSecond line'}]
    interrupted = copy.deepcopy(value)
    interrupted.update(case_id=digest('partial-tab'), timed_out=True, outputs={}, repetition=1)
    partial = '[{"op":"move","value":"unfinished'
    interrupted['calls'] = [{'messages': [{'role': 'user', 'content': 'Return the patch'}],
                             'text': partial, 'incomplete': True, 'finish_reason': None}]
    answer_test = read_json(LEGACY_ROOT / 'test_specs/array_index_replace_010.json')
    answer_variant = answer_test['variants'][0]
    answer_variant['expected_answers'] = {'index': '62'}
    answer = {'case_id': digest('plain-answer-tab'), 'model_id': 'mock', 'status': 'completed',
              'test_id': answer_test['id'], 'variant_id': answer_variant['id'], 'test_definition': answer_test,
              'variant_definition': answer_variant, 'outputs': {'index': '62'}, 'score': {'exact_match': True},
              'calls': [{'step': 'index', 'messages': [{'role': 'user', 'content': 'Choose the index.'}],
                         'text': '62', 'finish_reason': 'stop'}]}
    records = [value, interrupted, answer]
    report = build_report(records, [value['test_definition'], answer_test])
    report['evidence'] = {}
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for item in records:
            write_json(root / 'results' / item['model_id'] / (item['case_id'] + '.json'), item)
        original = {path: path.read_bytes() for path in (root / 'results').rglob('*.json')}
        with ReviewServer(('127.0.0.1', 0), root, report) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with sync_playwright() as playwright:
                    executable = os.environ.get('REPORT_BROWSER_EXECUTABLE')
                    browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
                    context = browser.new_context()
                    errors = []
                    context.on('page', lambda tab: tab.on('pageerror', lambda error: errors.append(str(error))))
                    page = context.new_page()
                    page.goto(f'http://127.0.0.1:{server.server_port}/')
                    assert page.locator('#drilldown').count() == 0
                    page.locator('tr[data-kind=case] td[data-outcome=fail] button').first.scroll_into_view_if_needed()
                    before_scroll = page.evaluate('scrollY')
                    with page.expect_popup() as opened:
                        page.locator('tr[data-kind=case] td[data-outcome=fail] button').first.click()
                    evidence = opened.value
                    expect(evidence.get_by_role('heading', level=1)).to_have_text('FAIL')
                    assert '/result/#results=' in evidence.url
                    assert evidence.evaluate('window.opener') is None
                    assert page.evaluate('scrollY') == before_scroll
                    blocks = evidence.locator('main > section')
                    assert blocks.evaluate_all('(items) => items.map(item => item.dataset.evidenceBlock)') == [
                        'Full prompt sent to the AI', 'Full text result', 'Expected result', 'Failure reason', 'Additional information']
                    prompt = blocks.nth(0)
                    assert json.loads(prompt.locator('pre').nth(2).text_content()) == {'literal': True}
                    assert '\n' in prompt.locator('pre').nth(2).text_content()
                    while prompt.get_by_role('button', name='Show exact sent text', exact=True).count():
                        prompt.get_by_role('button', name='Show exact sent text', exact=True).first.click()
                    assert prompt.locator('pre').all_text_contents() == ['System instructions\nSecond line', text, '{"literal":true}']
                    assert 'ORIGINAL NOT SENT' not in prompt.inner_text()
                    output = blocks.nth(1)
                    assert output.locator('pre').first.text_content() == value['calls'][0]['text']
                    displayed = output.locator('pre').nth(1).text_content()
                    assert json.loads(displayed) == json.loads(result)
                    assert '\n' in displayed
                    assert json.loads(blocks.nth(2).locator('pre').text_content()) == value['test_definition']['expected_state']
                    assert blocks.nth(3).inner_text().strip() != 'Failure reason'
                    assert report['matrix']['records'][value['case_id']]['evaluation']['reason'] in blocks.nth(3).inner_text()
                    assert 'Evaluator INCONCLUSIVE' in blocks.nth(4).inner_text()
                    assert evidence.evaluate('globalThis.injected') is None
                    assert prompt.locator('pre').first.evaluate('(item) => getComputedStyle(item).maxHeight') == 'none'
                    assert evidence.get_by_text('Complete raw record (JSON)', exact=True).evaluate('(item) => item.parentElement.open') is False
                    evidence.set_viewport_size({'width': 420, 'height': 1000})
                    assert evidence.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    evidence.reload()
                    expect(evidence.get_by_role('heading', level=1)).to_have_text('FAIL')
                    evidence.close()
                    with page.expect_popup() as opened:
                        page.evaluate('(id) => StatisticsReport.Inspect(id)', interrupted['case_id'])
                    evidence = opened.value
                    expect(evidence.locator('[data-evidence-block="Full text result"]')).to_contain_text('Partial response saved')
                    assert evidence.locator('[data-evidence-block="Full text result"] pre').text_content() == partial
                    evidence.close()
                    with page.expect_popup() as opened:
                        page.evaluate('(ids) => ResultsMatrix.Inspect(ids)', [item['case_id'] for item in records])
                    selected = opened.value
                    expect(selected.get_by_role('heading', level=1)).to_have_text('Selected test results')
                    assert selected.locator('main li a').count() == len(records)
                    selected.locator('main li a').first.click()
                    expect(selected.get_by_role('heading', level=1)).to_have_text('FAIL')
                    selected.close()
                    with page.expect_popup() as opened:
                        page.evaluate('(id) => StatisticsReport.Inspect(id)', answer['case_id'])
                    answer_page = opened.value
                    expect(answer_page.locator('[data-evidence-block="Expected result"] pre')).to_have_text('62')
                    assert answer_page.locator('[data-evidence-block="Expected result"] h3').count() == 0
                    answer_page.reload()
                    expect(answer_page.locator('[data-evidence-block="Expected result"] pre')).to_have_text('62')
                    assert 'expected_answers' in answer_page.locator('main > section').last.text_content()
                    answer_page.close()
                    context.route('**/evidence/*', lambda route: route.fulfill(status=404, body='{}'))
                    with page.expect_popup() as opened:
                        page.evaluate('(id) => StatisticsReport.Inspect(id)', value['case_id'])
                    evidence = opened.value
                    expect(evidence.get_by_role('status')).to_contain_text('Could not load complete evidence')
                    expect(evidence.locator('[data-evidence-block="Full prompt sent to the AI"]')).to_contain_text('Complete prompt unavailable')
                    evidence.close()
                    unknown = context.new_page()
                    unknown.goto(f'http://127.0.0.1:{server.server_port}/result/#results=' + '0' * 64)
                    expect(unknown.get_by_role('heading', level=1)).to_have_text('Result unavailable')
                    with ExistingViewerServer(('127.0.0.1', 0), root, report) as existing:
                        old_thread = threading.Thread(target=existing.serve_forever, daemon=True)
                        old_thread.start()
                        try:
                            old_context = browser.new_context()
                            old_page = old_context.new_page()
                            old_page.on('pageerror', lambda error: errors.append(str(error)))
                            old_page.goto(f'http://127.0.0.1:{existing.server_port}/')
                            assert old_page.evaluate('StatisticsReport.Data.result_tab_url') is None
                            assert old_context.request.get(f'http://127.0.0.1:{existing.server_port}/result/').status == 404
                            square = old_page.locator('tr[data-kind=case] td[data-outcome=fail] button').first
                            square.scroll_into_view_if_needed()
                            old_scroll = old_page.evaluate('scrollY')
                            with old_page.expect_popup() as opened:
                                square.click()
                            old_evidence = opened.value
                            expect(old_evidence.get_by_role('heading', level=1)).to_have_text('FAIL')
                            assert '/#results=' in old_evidence.url and '/result/' not in old_evidence.url
                            assert old_page.evaluate('scrollY') == old_scroll
                            assert old_evidence.locator('[data-evidence-block="Full text result"] pre').first.text_content() == value['calls'][0]['text']
                            assert json.loads(old_evidence.locator('[data-evidence-block="Expected result"] pre').text_content()) == value['test_definition']['expected_state']
                            old_evidence.reload()
                            expect(old_evidence.get_by_role('heading', level=1)).to_have_text('FAIL')
                            with old_page.expect_popup() as opened:
                                old_page.evaluate('(ids) => ResultsMatrix.Inspect(ids)', [item['case_id'] for item in records])
                            old_selection = opened.value
                            expect(old_selection.get_by_role('heading', level=1)).to_have_text('Selected test results')
                            old_selection.locator('main li a').first.click()
                            expect(old_selection.get_by_role('heading', level=1)).to_have_text('FAIL')
                            old_context.close()
                        finally:
                            existing.shutdown()
                            old_thread.join(5)
                    assert not errors, errors
                    browser.close()
            finally:
                server.shutdown()
                thread.join(5)
        assert all(path.read_bytes() == content for path, content in original.items())
    print('Result-tab browser smoke passed (synthetic evidence only)')


if __name__ == '__main__':
    main()
