"""Persistent review UI smoke on synthetic results, without model inference."""
import os
from pathlib import Path
import tempfile
import threading
from playwright.sync_api import sync_playwright, expect
from reporting.report import build_report
from reporting.server import ReviewServer
from tests.test_reporting import fixture
from workbench.judgements import JudgementStore


def main():
    records, specs = fixture()
    report = build_report(records, specs)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        with ReviewServer(('127.0.0.1', 0), root, report) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                with sync_playwright() as playwright:
                    executable = os.environ.get('REPORT_BROWSER_EXECUTABLE')
                    browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
                    page = browser.new_page(); errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{server.server_port}/')
                    expect(page.locator('#results-matrix tbody tr[data-kind=case]')).to_have_count(36)
                    first_id = page.locator('#results-matrix tbody tr[data-kind=case]').first.get_attribute('data-row-id')
                    page.locator('#results-matrix tbody tr[data-kind=case] th').first.click()
                    page.get_by_label('Judgement', exact=True).select_option('accepted')
                    assert page.get_by_label('Reason', exact=True).input_value() == 'Reviewed and accepted'
                    page.get_by_role('button', name='Apply judgement').click()
                    expect(page.get_by_role('dialog', name='Judge tests')).to_have_count(0)
                    expect(page.locator('#results-matrix tbody tr[data-kind=case]')).to_have_count(35)
                    expect(page.locator('#results-matrix-accepted tbody tr[data-kind=case]')).to_have_count(1)
                    assert page.locator('#results-matrix-accepted tbody tr[data-kind=case]').first.get_attribute('data-row-id') == first_id
                    assert '1 unique observations' in page.locator('#matrix-summary-accepted').inner_text()
                    assert page.locator('#matrix-totals-accepted td').last.inner_text() == '100%'
                    page.locator('#results-matrix-accepted tbody tr[data-kind=case] th').first.click()
                    page.get_by_label('Judgement', exact=True).select_option('rejected')
                    page.get_by_label('Reason', exact=True).select_option('Ambiguous instructions')
                    page.get_by_label('Note', exact=True).fill('Synthetic review only.')
                    page.get_by_role('button', name='Apply judgement').click()
                    expect(page.get_by_role('dialog', name='Judge tests')).to_have_count(0)
                    expect(page.locator('#results-matrix-rejected tbody tr[data-kind=case]')).to_have_count(1)
                    expect(page.locator('#results-matrix-accepted tbody tr[data-kind=case]')).to_have_count(0)
                    saved = JudgementStore(root).read()['entries']
                    assert len(saved) == 1 and next(iter(saved.values()))['blocked']
                    assert len(next(iter(saved.values()))['history']) == 2
                    page.reload()
                    assert not page.locator('#judgement-rejected').evaluate('(item) => item.open')
                    page.locator('#judgement-rejected > summary').click()
                    page.locator('#results-matrix-rejected tbody tr[data-kind=case] th').first.click()
                    assert page.get_by_label('Judgement', exact=True).locator('option[value=accepted]').evaluate('(option) => option.disabled')
                    assert page.get_by_label('Note', exact=True).input_value() == 'Synthetic review only.'
                    page.get_by_role('button', name='Cancel', exact=True).click()
                    # Collapsing one judgement's tree cannot collapse another's tree.
                    page.locator('#results-matrix-rejected tr[data-kind=group-heading] button').first.click()
                    assert page.locator('#results-matrix tr[data-kind=group-heading] button').first.get_attribute('aria-expanded') == 'true'
                    assert not errors, errors
                    browser.close()
            finally:
                server.shutdown(); thread.join(5)
    print('Persistent judgement browser smoke passed (synthetic evidence only)')


if __name__ == '__main__':
    main()
