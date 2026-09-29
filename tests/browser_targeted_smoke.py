"""Real Chromium + authenticated HTTP + real scheduling, with simulated model inference."""
from __future__ import annotations
import os
import base64
import urllib.request
import urllib.error
from pathlib import Path
import shutil
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workbench.controller import Controller
from workbench.domain import load_tests as read_tests
from workbench.server import WorkbenchServer
from test_workbench_targeted import configure_demo


def main():
    from playwright.sync_api import sync_playwright, expect
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        shutil.copytree(root / 'test_specs', project / 'test_specs')
        shutil.copytree(root / 'examples', project / 'examples')
        app = Controller(project, True)
        models, inventory = configure_demo(app)
        def no_unit_tests(): raise AssertionError('Targeted model runs must not run harness unit tests')
        app.selftest = no_unit_tests
        expected = sum(t.get('repetitions', 1) * sum(v.get('enabled', True) for v in t['variants']) for t in read_tests(project / 'test_specs'))
        original_files = {p: p.read_bytes() for p in (project / 'test_specs').glob('*.json')}
        server = WorkbenchServer(('127.0.0.1', 0), app, 'targeted-browser-key')
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with sync_playwright() as p:
                executable = os.environ.get('CHROME_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
                browser = p.chromium.launch(headless=True, args=['--no-sandbox'], **({'executable_path': executable} if executable else {}))
                page = browser.new_page(viewport={'width': 1440, 'height': 1060})
                errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
                base=f'http://127.0.0.1:{server.server_port}'
                bridge=os.environ.get('WORKBENCH_BROWSER_BRIDGE')=='1'
                if bridge:
                    # Hosted browser policy blocks loopback. The unchanged UI calls the real
                    # authenticated Python HTTP server through this test-only transport bridge.
                    def transport(path,options):
                        body=options.get('body')
                        request=urllib.request.Request(base+path,data=body.encode() if body else None,headers=options.get('headers',{}))
                        try:response=urllib.request.urlopen(request,timeout=15)
                        except urllib.error.HTTPError as error:response=error
                        with response:return {'status':response.code,'type':response.headers.get('Content-Type',''),
                                               'body':base64.b64encode(response.read()).decode()}
                    page.expose_function('targetedBridge',transport)
                    html=(root/'workbench/web/index.html').read_text().replace('<link rel="stylesheet" href="/style.css">','').replace('<script src="/app.js"></script>','')
                    page.set_content(html);page.add_style_tag(content=(root/'workbench/web/style.css').read_text())
                    page.add_script_tag(content="""const testStore={'rpg-worker-key':'targeted-browser-key'};
Object.defineProperty(window,'sessionStorage',{value:{getItem:k=>testStore[k]||null,setItem:(k,v)=>testStore[k]=v}});
window.fetch=async(path,options={})=>{const r=await window.targetedBridge(path,options);return new Response(Uint8Array.from(atob(r.body),c=>c.charCodeAt(0)),{status:r.status,headers:{'Content-Type':r.type}})};""")
                    page.add_script_tag(content=(root/'workbench/web/app.js').read_text())
                else:page.goto(base+'/#key=targeted-browser-key')
                expect(page.locator('#connection')).to_contain_text('Connected')
                page.get_by_role('button', name='Run Individual Test', exact=True).click()
                expect(page.locator('#page-individual')).to_be_visible()
                expect(page.locator('#individual-model option')).to_have_count(4)
                expect(page.locator('#individual-model option').nth(1)).to_have_text('All')
                expect(page.locator('#individual-run')).to_be_disabled()
                page.locator('#individual-model').select_option('beta')
                page.locator('#individual-test').select_option('time_only')
                page.locator('#individual-variant').select_option('direct_json_patch')
                expect(page.locator('#individual-summary')).to_contain_text('1 configured case(s)')
                expect(page.locator('#individual-summary')).to_contain_text('60 s limit each')
                page.wait_for_timeout(1500)
                expect(page.locator('#individual-model')).to_have_value('beta')
                expect(page.locator('#individual-variant')).to_have_value('direct_json_patch')
                screenshot = os.environ.get('WORKBENCH_INDIVIDUAL_SCREENSHOT')
                if screenshot: page.screenshot(path=screenshot, full_page=True)
                page.locator('#individual-check').click()
                expect(page.locator('#page-overview')).to_be_visible()
                expect(page.locator('#readiness')).to_have_text('Ready')
                expect(page.locator('#pending')).to_have_text('1')
                expect(page.locator('#run-scope')).to_contain_text('beta · time_only · direct_json_patch')
                assert app.store.all() == [], 'Targeted preflight must not perform inference'
                page.get_by_role('button', name='Run Individual Test', exact=True).click()
                expect(page.locator('#individual-model')).to_have_value('beta')
                expect(page.locator('#individual-variant')).to_have_value('direct_json_patch')
                page.locator('#individual-run').click()
                expect(page.locator('#state-badge')).to_have_text('FINISHED', timeout=15000)
                records = app.store.all()
                assert len(records) == 1 and records[0]['model_id'] == 'beta' and records[0]['test_id'] == 'time_only'
                assert records[0]['variant_id'] == 'direct_json_patch'
                page.get_by_role('button', name='Run Individual Test', exact=True).click()
                page.locator('#individual-run').click()
                expect(page.locator('#state-badge')).to_have_text('FINISHED', timeout=15000)
                expect(page.locator('#session-complete')).to_have_text('0')
                assert len(app.store.all()) == 1, 'Repeated targeted Run must resume rather than overwrite'
                page.get_by_role('button', name='Run Individual Test', exact=True).click()
                page.locator('#individual-model').select_option('__all__')
                page.locator('#individual-test').select_option('clothing_append')
                page.locator('#individual-variant').select_option('direct_json_patch')
                expect(page.locator('#individual-summary')).to_contain_text('2 configured case(s) on all 2 model(s)')
                page.locator('#individual-run').click()
                expect(page.locator('#session-complete')).to_have_text('2',timeout=15000)
                expect(page.locator('#state-badge')).to_have_text('FINISHED',timeout=15000)
                clothing=[r for r in app.store.all() if r['test_id']=='clothing_append']
                assert len(clothing)==2 and {r['model_id'] for r in clothing}=={'alpha','beta'}
                assert all(r['provenance']['selection']=={'all_models':True,'test_id':'clothing_append','variant_id':'direct_json_patch'} for r in clothing)
                expect(page.locator('#run-scope')).to_contain_text('all eligible models · clothing_append · direct_json_patch')
                page.get_by_role('button', name='Test One Model', exact=True).click()
                expect(page.locator('#page-one-model')).to_be_visible()
                expect(page.locator('#one-model-model option')).to_have_count(3)
                page.locator('#one-model-model').select_option('alpha')
                boxes=page.locator('#one-model-tests input[type="checkbox"]')
                expect(boxes).to_have_count(len(read_tests(project / 'test_specs')))
                assert page.locator('#one-model-tests input[type="checkbox"]:checked').count()==boxes.count()
                expect(page.locator('#one-model-toggle-tests')).to_have_text('Deselect all')
                expect(page.locator('#one-model-summary')).to_contain_text(str(expected) + ' configured case(s)')
                expect(page.locator('#one-model-tests')).to_contain_text('60 s limit')
                page.locator('#one-model-toggle-tests').click()
                assert page.locator('#one-model-tests input[type="checkbox"]:checked').count()==0
                expect(page.locator('#one-model-toggle-tests')).to_have_text('Select all')
                expect(page.locator('#one-model-run')).to_be_disabled()
                time_box=page.locator('#one-model-tests input[data-test-id="time_only"]')
                time_box.check()
                expect(page.locator('#one-model-toggle-tests')).to_have_text('Deselect all')
                selected_expected=next(t for t in read_tests(project / 'test_specs') if t['id']=='time_only')
                selected_expected=selected_expected.get('repetitions',1)*sum(v.get('enabled',True) for v in selected_expected['variants'])
                expect(page.locator('#one-model-summary')).to_contain_text(str(selected_expected) + ' configured case(s)')
                screenshot = os.environ.get('WORKBENCH_ONE_MODEL_SCREENSHOT')
                if screenshot: page.screenshot(path=screenshot, full_page=True)
                # Disable competing operations without changing or clearing dropdown drafts.
                app.operation.acquire()
                try:
                    expect(page.locator('#one-model-run')).to_be_disabled(timeout=5000)
                    expect(page.locator('#one-model-model')).to_have_value('alpha')
                    expect(time_box).to_be_checked()
                finally: app.operation.release()
                expect(page.locator('#one-model-run')).to_be_enabled(timeout=5000)
                page.locator('#one-model-run').click()
                expect(page.locator('#session-complete')).to_have_text(str(selected_expected), timeout=20000)
                expect(page.locator('#state-badge')).to_have_text('FINISHED', timeout=20000)
                records = app.store.all()
                alpha=[r for r in records if r['model_id']=='alpha']
                alpha_time=[r for r in records if r['model_id']=='alpha' and r['test_id']=='time_only']
                assert len(alpha_time)==selected_expected
                assert len([r for r in records if r['model_id']=='beta'])==2
                expect(page.locator('#run-scope')).to_contain_text('1 selected test(s)')
                page.locator('#preflight').click()
                expect(page.locator('#pending')).to_have_text(str(2*expected-selected_expected-3), timeout=10000)
                expect(page.locator('#run-scope')).to_contain_text('all eligible models')
                assert all(path.read_bytes() == data for path, data in original_files.items())
                # The same choices survive navigation, refreshing, polling and narrow viewports.
                page.get_by_role('button', name='Test One Model', exact=True).click()
                expect(page.locator('#one-model-tests input[data-test-id="time_only"]')).to_be_checked()
                assert page.locator('#one-model-tests input[type="checkbox"]:checked').count()==1
                page.get_by_role('button', name='Run Individual Test', exact=True).click()
                expect(page.locator('#individual-variant')).to_have_value('direct_json_patch')
                for width in (800, 390):
                    page.set_viewport_size({'width': width, 'height': 900})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Page overflow'
                assert not errors, errors
                browser.close()
                print(('LOCAL HTTP BRIDGE (browser networking not exercised); ' if bridge else '')+'PASS: two targeted sidebar tabs, one model/test/variant, whole-model suite, actual scoped HTTP, preflight isolation, stable selectors, busy controls, global resume and responsive layouts. Inference is SIMULATED.')
        finally:
            app.control('stop')
            if app.thread: app.thread.join(5)
            server.shutdown(); server.server_close(); thread.join(5)


if __name__ == '__main__': main()
