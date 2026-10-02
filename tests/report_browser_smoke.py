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
            assert page.locator('details[id^=judgement-]').evaluate_all('(items) => items.map(item => item.id)') == ['judgement-rejected', 'judgement-needs_review', 'judgement-accepted']
            assert not page.locator('#judgement-rejected').evaluate('(item) => item.open')
            assert page.locator('#judgement-needs_review').evaluate('(item) => item.open')
            assert page.locator('#judgement-accepted').evaluate('(item) => item.open')
            assert page.locator('details[id^=judgement-] > details').evaluate_all('(items) => items.every(item => !item.open)')
            assert page.locator('#matrix-key').count() == 1
            assert 'Objective results — tests' not in page.locator('body').inner_text()
            assert 'reference cells' not in page.locator('body').inner_text()
            review = page.locator('#judgement-needs_review')
            review.locator(':scope > details > summary').click()
            assert page.locator('#results-matrix-rejected tbody tr[data-kind=case]').count() == 0
            assert page.locator('#results-matrix-accepted tbody tr[data-kind=case]').count() == 0
            assert page.get_by_label('Rows', exact=True).input_value() == 'cases'
            assert page.locator('#results-matrix').count() == 1
            layout = page.locator('#results-matrix').evaluate(
                '(table) => { const wrap = table.parentElement; const style = getComputedStyle(wrap); return {overflow: style.overflow, maxHeight: style.maxHeight, height: wrap.clientHeight, scrollHeight: wrap.scrollHeight}; }')
            assert layout['overflow'] == 'visible' and layout['maxHeight'] == 'none', layout
            assert layout['height'] == layout['scrollHeight'], layout
            assert '35 unique observations' in page.locator('#matrix-summary').inner_text()
            grand = page.locator('#matrix-totals td').last
            assert grand.inner_text() == '97%'
            assert '34 PASS' in grand.get_attribute('title')
            assert '1 timeout' in grand.get_attribute('title')
            assert '1 not recorded' in grand.get_attribute('title')
            assert review.get_by_label('Grouping preset').input_value() == '0'
            assert review.get_by_label('Grouping preset').locator('option[value=custom]').evaluate('(option) => option.disabled')
            assert review.get_by_role('button', name='Save as new').is_disabled()
            assert review.get_by_role('button', name='Delete', exact=False).is_enabled()
            assert page.locator('#matrix-groupings-needs_review button').filter(has_text='Save').count() == 1
            heading = page.locator('tr[data-kind=group-heading]').first
            key = heading.get_attribute('data-group-key')
            total_before = page.locator('#matrix-totals').inner_text()
            heading.locator('button').first.click()
            collapsed = page.locator('tr[data-kind=group-heading]').first
            assert collapsed.locator('button').first.get_attribute('aria-expanded') == 'false'
            assert collapsed.evaluate('(row) => row.nextElementSibling.dataset.kind') == 'group-total'
            assert collapsed.evaluate('(row) => row.nextElementSibling.dataset.groupKey') == key
            assert page.locator('#matrix-totals').inner_text() == total_before
            collapsed.locator('button').first.click()
            ordering = page.locator('#results-matrix tbody').evaluate('''(body) => {
                const rows = [...body.children];
                return rows.filter(row => row.dataset.kind === 'group-heading').every(heading => {
                    const start = rows.indexOf(heading);
                    const end = rows.findIndex(row => row.dataset.kind === 'group-total' && row.dataset.groupKey === heading.dataset.groupKey);
                    return end > start && rows.slice(start + 1, end).every(row => Number(row.dataset.level ?? 99) > Number(heading.dataset.level));
                });
            }''')
            assert ordering
            page.get_by_label('Rows', exact=True).select_option('tests')
            assert page.locator('tr[data-kind=case]').count() == 0
            assert page.locator('tr[data-kind=group-total]').count() > 0
            assert page.locator('#matrix-totals').inner_text() == total_before
            page.get_by_label('Rows', exact=True).select_option('cases')
            assert page.locator('#results-matrix td[data-outcome=pass]').count() > 0
            assert page.locator('#results-matrix td[data-outcome=timeout]').count() == 1
            assert page.locator('tr[data-kind=case] td[data-outcome=timeout] [data-timeout-marker]').count() == 1
            assert page.locator('tr[data-kind=case] td[data-outcome=pass] [data-timeout-marker]').count() == 0
            assert page.locator('#matrix-totals td').last.locator('[data-timeout-marker]').count() == 1
            assert 'Red corner' in page.locator('td[data-outcome=timeout]').get_attribute('title')
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
            aggregation = page.evaluate('''() => {
                const records = StatisticsReport.Data.matrix.records;
                const values = [['group-pass-1', 'pass'], ['group-pass-2', 'pass'], ['group-fail', 'fail'], ['group-error', 'error']];
                for (const [id, outcome] of values) records[id] = {outcome};
                const primary = id => ({ids: [id], primary_ids: [id], reference_ids: []});
                const reference = id => ({ids: [id], primary_ids: [], reference_ids: [id]});
                const cells = [primary('group-pass-1'), primary('group-pass-2'), primary('group-fail'), primary('group-error'), primary('group-pass-1'), reference('group-pass-1'), reference('group-pass-1'), ResultsMatrix.Empty];
                const row = document.createElement('tr');
                const counts = ResultsMatrix.Counts(cells);
                ResultsMatrix.Cell(row, cells, 'Unequal child totals');
                const percent = row.lastChild.textContent;
                ResultsMatrix.Cell(row, [reference('group-pass-1')], 'Reference-only total');
                const referenceText = row.lastChild.textContent;
                ResultsMatrix.Cell(row, [primary('group-error')], 'Unscored total');
                const unscored = row.lastChild.textContent;
                for (const [id] of values) delete records[id];
                return {counts, percent, referenceText, unscored};
            }''')
            marker_checks = page.evaluate('''() => {
                const records = StatisticsReport.Data.matrix.records;
                records['confirmed-timeout-failure'] = {outcome: 'fail', metadata: {timed_out: true}};
                const row = document.createElement('tr');
                const cell = {ids: ['confirmed-timeout-failure'], primary_ids: ['confirmed-timeout-failure'], reference_ids: []};
                ResultsMatrix.Cell(row, [cell], 'Confirmed failure', true);
                const primary = row.lastChild.querySelectorAll('[data-timeout-marker]').length;
                ResultsMatrix.Cell(row, [{...cell, primary_ids: [], reference_ids: cell.ids}], 'Shared reference', true);
                const reference = row.lastChild.querySelectorAll('[data-timeout-marker]').length;
                delete records['confirmed-timeout-failure'];
                return {primary, reference};
            }''')
            assert marker_checks == {'primary': 1, 'reference': 1}, marker_checks
            assert aggregation['percent'] == '67%', aggregation
            assert aggregation['counts']['observations'] == 4, aggregation
            assert aggregation['counts']['pass'] == 2, aggregation
            assert aggregation['counts']['error'] == 1, aggregation
            assert aggregation['counts']['not_run'] == 1, aggregation
            assert aggregation['referenceText'] != '100%' and aggregation['unscored'] != '0%', aggregation
            square=page.locator('#results-matrix tbody tr[data-kind=case] td[data-outcome=pass]').first.bounding_box()
            assert abs(square['width']-square['height']) <= 1, square
            assert square['width'] <= 26, square
            total_square = page.locator('#matrix-totals td').last.bounding_box()
            assert abs(total_square['width'] - total_square['height']) <= 1, total_square
            page.locator('#results-matrix tbody tr[data-kind=case] td[data-outcome=pass] button').first.click()
            assert 'expected_answers' in page.locator('#drilldown').inner_text()
            page.get_by_label('Find test').fill('array_index_replace_010')
            assert page.locator('#results-matrix tbody tr[data-kind=case]').count() == 3
            page.get_by_label('Find test').fill('')
            review.get_by_label('Grouping preset').select_option('1')
            assert page.locator('tr[data-kind=group-heading]').first.get_attribute('data-axis') == 'input_presentation'
            review.get_by_role('button', name='Move Input presentation down', exact=True).click()
            assert review.get_by_label('Grouping preset').input_value() == '2'
            assert review.get_by_role('button', name='Save as new').is_disabled()
            review.get_by_role('button', name='Remove Task type', exact=True).click()
            assert review.get_by_label('Grouping preset').input_value() == 'custom'
            assert review.get_by_role('button', name='Save as new').is_enabled()
            assert review.get_by_role('button', name='Delete', exact=False).is_disabled()
            review.get_by_role('button', name='Save as new').click()
            page.get_by_label('Preset name', exact=True).fill('Individual tests')
            page.get_by_role('button', name='Create preset', exact=True).click()
            assert page.get_by_role('dialog', name='Save grouping preset').count() == 1
            page.get_by_label('Preset name', exact=True).fill('My compact grouping')
            page.get_by_role('button', name='Create preset', exact=True).click()
            assert page.get_by_role('dialog').count() == 0
            assert review.get_by_label('Grouping preset').input_value() == '5'
            page.reload()
            review.locator(':scope > details > summary').click()
            assert review.get_by_label('Grouping preset').input_value() == '5'
            assert review.get_by_role('button', name='Save as new').is_disabled()
            review.get_by_label('Grouping preset').select_option('0')
            review.get_by_role('button', name='Delete', exact=False).click()
            page.get_by_role('button', name='Delete preset', exact=True).click()
            assert review.get_by_label('Grouping preset').input_value() == 'custom'
            assert review.get_by_role('button', name='Save as new').is_enabled()
            # Regeneration at the same location must not resurrect a deleted built-in preset.
            write_report(build_report(records, specs), path)
            page.reload()
            review.locator(':scope > details > summary').click()
            assert review.get_by_label('Grouping preset').locator('option').filter(has_text='Individual tests').count() == 0
            assert review.get_by_label('Grouping preset').input_value() == 'custom'
            review.get_by_role('button', name='Remove Ability category', exact=True).click()
            review.get_by_label('Add grouping level').select_option('ability_category')
            review.get_by_role('button', name='Add', exact=True).click()
            assert page.evaluate('ResultsMatrix.Sections.needs_review.groupings.Order.at(-1)') == 'ability_category'
            assert page.locator('#matrix-totals').inner_text() == total_before
            page.evaluate('ResultsMatrix.Sections.needs_review.groupings.Change([])')
            assert page.locator('tr[data-kind=group-heading]').count() == 0
            assert page.locator('tr[data-kind=case]').count() == 36
            assert page.locator('#matrix-totals').inner_text() == total_before
            # Each table owns its own grouping state.
            assert page.evaluate('ResultsMatrix.Sections.accepted.groupings.Order.length') == 4
            assert page.evaluate('ResultsMatrix.Sections.rejected.groupings.Order.length') == 4
            page.locator('#results-matrix tbody tr[data-kind=case] th').first.click()
            assert 'read-only snapshot' in page.get_by_role('dialog', name='Judge tests').inner_text()
            page.get_by_role('button', name='Close', exact=True).click()
            remaining = review.get_by_label('Grouping preset').locator('option').count() - 1
            for unused in range(remaining):
                review.get_by_label('Grouping preset').select_option('0')
                review.get_by_role('button', name='Delete', exact=False).click()
                page.get_by_role('button', name='Delete preset', exact=True).click()
            page.reload()
            review.locator(':scope > details > summary').click()
            assert review.get_by_label('Grouping preset').locator('option').count() == 1
            assert review.get_by_role('button', name='Save as new').is_enabled()
            assert review.get_by_role('button', name='Delete', exact=False).is_disabled()
            page.evaluate('localStorage.setItem(ResultsMatrix.Sections.needs_review.groupings.StorageKey, "corrupt")')
            page.reload()
            review.locator(':scope > details > summary').click()
            assert 'Saved presets could not be loaded' in page.locator('#matrix-groupings-needs_review').inner_text()
            assert review.get_by_label('Grouping preset').locator('option').count() == 6
            assert not errors, errors
            assert not network, network
            browser.close()
    print('Offline report browser smoke passed')


if __name__ == '__main__':
    main()
