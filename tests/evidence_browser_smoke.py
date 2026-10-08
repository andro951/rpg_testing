"""Readable evidence display and loading failures, using synthetic records only."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
from playwright.sync_api import sync_playwright, expect
from reporting.report import build_report
from reporting.server import ReviewServer
from tests.test_reporting import fixture
from workbench.domain import write_json


def main():
    records, specs = fixture()
    text = 'Current State:\n{\n  "tickets": [\n    {"ticket_id": "SR-22345"}\n  ]\n}\n\nReply exactly. <script>window.injected = true</script>'
    records[0]['calls'] = [{'step': 'answer', 'messages': [{'role': 'user', 'content': text}],
                           'text': '[{"op":"replace","path":"/tickets/0","value":"updated"}]',
                           'reasoning_text': 'First line\nSecond line'}]
    report = build_report(records, specs)
    report['evidence'] = {}
    first_id = records[0]['case_id']
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for record in records:
            write_json(root / 'results' / record['model_id'] / (record['case_id'] + '.json'), record)
        original = copy.deepcopy(records[0])
        with ReviewServer(('127.0.0.1', 0), root, report) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                with sync_playwright() as playwright:
                    executable = os.environ.get('REPORT_BROWSER_EXECUTABLE')
                    browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
                    page = browser.new_page(); errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{server.server_port}/')
                    partial = '[{"op":"replace","value":"unfinished'
                    displayed = page.evaluate('''(text) => {
                        const parent = document.createElement("div");
                        return StatisticsReport.EvidenceText(parent, text).textContent;
                    }''', partial)
                    assert displayed == partial
                    # Most objective records are summaries: fetch the complete saved file.
                    page.evaluate('(id) => StatisticsReport.Inspect(id)', first_id)
                    expect(page.locator('#drilldown')).to_contain_text('Requests and responses (1)')
                    expect(page.locator('#drilldown [data-evaluator-feedback]')).to_contain_text('Evaluator INCONCLUSIVE')
                    expect(page.locator('#drilldown [data-evaluator-feedback]')).to_contain_text('Detailed checks')
                    assert page.locator('td[title*="Evaluator INCONCLUSIVE"]').count() > 0
                    prompt = page.locator('#drilldown pre').filter(has_text='Current State:').first
                    assert prompt.text_content() == text
                    assert '\\n' not in prompt.text_content()
                    assert '\\"' not in prompt.text_content()
                    output = page.locator('#drilldown pre').filter(has_text='"op": "replace"').first.text_content()
                    assert '\n' in output and '  {' in output and '"path": "/tickets/0"' in output
                    assert page.evaluate('globalThis.injected') is None
                    assert prompt.evaluate('(item) => getComputedStyle(item).maxHeight') == 'none'
                    assert page.locator('#drilldown details').filter(has=page.locator('summary', has_text='Complete raw record')).first.evaluate('(item) => item.open') is False
                    # Requests failing to load must identify the preview as incomplete.
                    page.route('**/evidence/*', lambda route: route.fulfill(status=404, body='{}'))
                    page.evaluate('(id) => StatisticsReport.Inspect(id)', records[1]['case_id'])
                    expect(page.get_by_role('status')).to_contain_text('Could not load complete evidence')
                    expect(page.locator('#drilldown')).to_contain_text('Limited saved preview')
                    assert not errors, errors
                    browser.close()
            finally:
                server.shutdown(); thread.join(5)
        assert json.loads((root / 'results' / original['model_id'] / (first_id + '.json')).read_text(encoding='utf-8')) == original
    print('Readable evidence browser smoke passed (synthetic evidence only)')


if __name__ == '__main__':
    main()
