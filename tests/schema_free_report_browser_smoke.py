"""Offline schema-free patch mismatch UI smoke, using synthetic mock outputs."""
import json
import os
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from reporting.report import build_report, write_report
from tests.test_schema_free_intent import fixture, record_for


def main():
    test = fixture()
    raw = json.dumps([{'op': 'replace', 'path': 'note', 'value': 'old'}, *test['variants'][0]['expected_patch']])
    record = record_for(test, raw)
    report = build_report([record], [test], fingerprint='test-fingerprint')
    report['evidence'][record['case_id']] = record
    with tempfile.TemporaryDirectory() as folder:
        path = write_report(report, Path(folder) / 'report.html')
        with sync_playwright() as playwright:
            executable = os.environ.get('REPORT_BROWSER_EXECUTABLE')
            browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
            page = browser.new_page()
            errors, network = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: network.append(request.url) if request.url.startswith(('http:', 'https:')) else None)
            page.goto(path.as_uri())
            cell = page.locator('tr[data-kind=case] td[data-patch-mismatch=true]').first
            cell.wait_for()
            assert '1 PASS / 0 FAIL' in cell.get_attribute('title')
            assert 'Diagnostic only' in cell.get_attribute('title')
            assert cell.locator('[data-patch-mismatch-marker=true]').inner_text() == '≠'
            assert cell.locator('button').inner_text() == '100%'
            assert 'Reference patch mismatch (diagnostic only)' in page.locator('#matrix-key').inner_text()
            totals = page.locator('#matrix-totals').inner_text()
            for unused in range(2):
                with page.expect_popup() as popup_info:
                    cell.locator('button').click()
                popup = popup_info.value
                popup.on('pageerror', lambda error: errors.append(str(error)))
                popup.get_by_role('heading', name='PASS', exact=True).wait_for()
                assert 'Reference patch comparison (diagnostic only)' in popup.locator('body').inner_text()
                assert 'Normalized patch differs' in popup.locator('body').inner_text()
                assert 'This comparison does not change the saved pass/fail result.' in popup.locator('body').inner_text()
                assert 'None — this result passed.' in popup.locator('body').inner_text()
                popup.reload()
                popup.get_by_role('heading', name='PASS', exact=True).wait_for()
                popup.close()
                assert page.locator('#matrix-totals').inner_text() == totals
            page.set_viewport_size({'width': 390, 'height': 844})
            assert cell.locator('[data-patch-mismatch-marker=true]').is_visible()
            assert not errors, errors
            assert not network, network
            browser.close()
    print('Schema-free reference-patch browser smoke passed (synthetic outputs only)')


if __name__ == '__main__':
    main()
