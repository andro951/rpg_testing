"""Integrated tab and changing-format coverage; deterministic, no inference."""
import os
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from reporting.report import build_report, write_report
from tests.test_reporting import fixture


def main():
    records, specs = fixture()
    report = build_report(records, specs)
    original = report['matrix']
    observations = [dict(id=f'{i}-{o}-{n}', model='m', input=i, output=o, outcome=state) for i in ['normal_json','id_keyed_arrays','full_paths'] for o in ['json_dot','json_slash','path_list','literal_line','typed_lines','end_marked_line'] for n,state in enumerate(['pass','fail','timeout','parser_gap'])]
    report['format_comparison'] = dict(models=[dict(id='m',label='Model A'),dict(id='missing',label='Missing model')], observations=observations, note='Synthetic test comparison')
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as playwright:
        path = write_report(report, Path(tmp)/'statistics.html')
        executable = os.environ.get('REPORT_BROWSER_EXECUTABLE')
        browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width':1280,'height':900})
        errors=[]
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(path.as_uri())
        before = page.locator('#matrix-totals').inner_text()
        assert page.get_by_label('Cell display').is_hidden()
        page.get_by_role('tab',name='Input × output formats').click()
        assert page.locator('#format-comparison-table tbody tr').count()==18
        assert page.locator('#format-comparison-table thead th').count()==3
        assert page.locator('#format-comparison-table tbody td').first.inner_text()=='33.3%'
        assert page.locator('#format-comparison-table tbody td').nth(1).inner_text()=='—'
        assert 'parser gap' in page.locator('#format-comparison-table tbody td').first.get_attribute('title')
        page.get_by_label('Cell display').select_option('fraction')
        assert page.locator('#format-comparison-table tbody td').first.inner_text()=='1/3'
        page.get_by_label('Cell display').select_option('percent')
        assert page.locator('#format-comparison-table tbody td').first.inner_text()=='33.3%'
        page.evaluate("StatisticsReport.Data.format_comparison.observations.push({id:'new',model:'m',input:'future_input',output:'future_output',outcome:'pass'}); StatisticsReport.Render()")
        assert page.locator('#format-comparison-table tbody tr').count()==19
        assert page.get_by_text('future input → future output',exact=True).count()==1
        page.evaluate("StatisticsReport.Data.format_comparison.observations=StatisticsReport.Data.format_comparison.observations.filter(x=>x.output!=='json_dot'); StatisticsReport.Render()")
        assert page.locator('#format-comparison-table tbody tr').count()==16
        page.get_by_role('tab',name='Results',exact=True).click()
        assert page.locator('#matrix-totals').inner_text()==before
        assert page.get_by_label('Cell display').is_hidden()
        for _ in range(3):
            page.get_by_role('tab',name='Input × output formats').click()
            page.get_by_role('tab',name='Results',exact=True).click()
        page.get_by_role('tab',name='Input × output formats').click()
        page.get_by_label('Comparison data').select_option('saved')
        assert page.get_by_label('Evidence scope').is_visible()
        page.get_by_label('Find test').fill('no-such-test')
        assert page.locator('#format-comparison-table tbody tr').count()==0
        page.get_by_label('Find test').fill('')
        page.get_by_label('Comparison data').select_option('comparison')
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.locator('#format-comparison-table').evaluate('(el)=>el.parentElement.scrollWidth>el.parentElement.clientWidth')
        assert not errors,errors
        browser.close()
    assert report['matrix']==original
    print('Integrated format comparison smoke passed: toggles, 18 to 19 to 16 dynamic rows, missing/timeout/parser-gap semantics, filters, repeated tab switches, narrow screen, original totals preserved.')

if __name__=='__main__': main()
