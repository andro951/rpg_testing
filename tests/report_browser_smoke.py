"""Offline report smoke; uses a synthetic fixture, never real inference."""
import os
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from reporting.report import build_report, write_report
from tests.test_reporting import fixture


def main():
    records, specs = fixture()
    records.pop()
    records[0]['timed_out'] = True
    with tempfile.TemporaryDirectory() as tmp:
        path = write_report(build_report(records, specs), Path(tmp) / 'statistics.html')
        with sync_playwright() as playwright:
            executable = os.environ.get('REPORT_BROWSER_EXECUTABLE')
            browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
            page = browser.new_page()
            errors, network = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: network.append(request.url) if request.url.startswith(('http:', 'https:')) else None)
            page.goto(path.as_uri())
            page.get_by_role('heading', name='RPG testing statistics', exact=True).wait_for()
            assert page.get_by_label('View').input_value() == 'matrix'
            assert page.get_by_label('Rows', exact=True).input_value() == 'cases'
            assert page.locator('#results-matrix').count() == 1
            layout = page.locator('#results-matrix').evaluate(
                '(table) => { const wrap = table.parentElement; const style = getComputedStyle(wrap); return {overflow: style.overflow, maxHeight: style.maxHeight, height: wrap.clientHeight, scrollHeight: wrap.scrollHeight}; }')
            assert layout['overflow'] == 'visible' and layout['maxHeight'] == 'none', layout
            assert layout['height'] == layout['scrollHeight'], layout
            assert '35 unique observations' in page.locator('#matrix-summary').inner_text()
            assert '34 PASS' in page.locator('#matrix-totals').inner_text()
            assert '1 timeout' in page.locator('#matrix-totals').inner_text()
            assert '1 not recorded' in page.locator('#matrix-totals').inner_text()
            page.get_by_label('Rows', exact=True).select_option('cases')
            assert page.locator('#results-matrix td[data-outcome=pass]').count() > 0
            assert page.locator('#results-matrix td[data-outcome=timeout]').count() == 1
            assert page.locator('#results-matrix td[data-outcome=missing]').count() > 0
            colors = page.evaluate("""() => {
                const records = StatisticsReport.Data.matrix.records;
                const pass = Object.keys(records).find(id => records[id].outcome === 'pass');
                const timeout = Object.keys(records).find(id => records[id].outcome === 'timeout');
                const make = id => ({ids: [id], primary_ids: [id], reference_ids: []});
                const row = document.createElement('tr');
                document.body.appendChild(row);
                const samples = [[make(timeout)], [make(pass), make(timeout)], [make(pass)], [ResultsMatrix.Empty]];
                const colors = samples.map(cells => {
                    ResultsMatrix.Cell(row, cells, 'Gradient smoke');
                    return getComputedStyle(row.lastChild).backgroundColor;
                });
                row.remove();
                return colors;
            }""")
            assert colors == ['rgb(242, 166, 166)', 'rgb(242, 242, 166)', 'rgb(166, 242, 166)', 'rgb(241, 245, 249)'], colors
            square=page.locator('#results-matrix tbody tr[data-kind=case] td[data-outcome=pass]').first.bounding_box()
            assert abs(square['width']-square['height']) <= 1, square
            assert square['width'] <= 26, square
            page.locator('#results-matrix tbody tr[data-kind=case] td[data-outcome=pass] button').first.click()
            assert 'expected_answers' in page.locator('#drilldown').inner_text()
            page.get_by_label('Find test').fill('array_index_replace_010')
            assert page.locator('#results-matrix tbody tr[data-kind=case]').count() == 3
            page.get_by_label('Find test').fill('')
            page.get_by_label('View').select_option('comparison')
            assert '5 matched' in page.locator('main').inner_text()
            page.get_by_label('View').select_option('grid')
            assert 'missing' in page.locator('main').inner_text()
            page.get_by_role('button', name='correct', exact=True).first.click()
            assert 'expected_answers' in page.locator('#drilldown').inner_text()
            assert '</script><script>alert(1)</script>' in page.locator('#drilldown').inner_text()
            page.get_by_label('Task').select_option('patch')
            assert 'timeout' in page.locator('main').inner_text()
            for view in ('comparison', 'failures', 'latency', 'history'):
                page.get_by_label('View').select_option(view)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.get_by_label('View').select_option('comparison')
            assert page.locator('svg').count() == 3
            assert not errors, errors
            assert not network, network
            browser.close()
    print('Offline report browser smoke passed')


if __name__ == '__main__':
    main()
