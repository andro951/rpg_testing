"""Optional real Chromium smoke: no model or GPU and no public network requests."""
from __future__ import annotations
import json
import base64
import urllib.request
import urllib.error
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workbench.controller import Controller
from workbench.server import WorkbenchServer


def main():
    from playwright.sync_api import sync_playwright,expect
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as temp:
        project=Path(temp)
        shutil.copytree(root/'test_specs',project/'test_specs')
        shutil.copytree(root/'examples',project/'examples')
        app=Controller(project,True);app.selftest=lambda:None
        base_tests=[json.loads(p.read_text()) for p in sorted((project/'test_specs').glob('*.json'))]
        base_tests=[t for t in base_tests if t.get('enabled',True)]
        base_test_count=len(base_tests)
        base_case_count=sum(t.get('repetitions',1)*sum(v.get('enabled',True) for v in t['variants']) for t in base_tests)
        server=WorkbenchServer(('127.0.0.1',0),app,'browser-test-key')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                executable=os.environ.get('CHROME_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
                kwargs={'executable_path':executable} if executable else {}
                browser=p.chromium.launch(headless=True,args=['--no-sandbox'],**kwargs)
                page=browser.new_page(viewport={'width':1440,'height':1060});errors=[]
                page.on('pageerror',lambda err:errors.append(str(err)))
                base=f'http://127.0.0.1:{server.server_port}'
                bridge=os.environ.get('WORKBENCH_BROWSER_BRIDGE')=='1'
                if bridge:
                    # For hosted browsers with network policy restrictions. This tests the
                    # unchanged UI JavaScript through real Python loopback HTTP, not browser networking.
                    def transport(path,options):
                        data=options.get('body')
                        request=urllib.request.Request(base+path,data=data.encode() if data else None,headers=options.get('headers',{}))
                        try:response=urllib.request.urlopen(request,timeout=15)
                        except urllib.error.HTTPError as e:response=e
                        with response:return {'status':response.code,'type':response.headers.get('Content-Type',''),'body':base64.b64encode(response.read()).decode()}
                    page.expose_function('localHttpTestBridge',transport)
                    html=(root/'workbench/web/index.html').read_text().replace('<link rel="stylesheet" href="/style.css">','').replace('<script src="/app.js"></script>','')
                    page.set_content(html)
                    page.add_style_tag(content=(root/'workbench/web/style.css').read_text())
                    page.add_script_tag(content='''const store={'rpg-worker-key':'browser-test-key'};
Object.defineProperty(window,'sessionStorage',{value:{getItem:k=>store[k]||null,setItem:(k,v)=>store[k]=v}});
window.fetch=async(path,options={})=>{const r=await window.localHttpTestBridge(path,options);return new Response(Uint8Array.from(atob(r.body),c=>c.charCodeAt(0)),{status:r.status,headers:{'Content-Type':r.type}})};''')
                    page.add_script_tag(content=(root/'workbench/web/app.js').read_text())
                else:page.goto(base+'/#key=browser-test-key')
                expect(page.locator('#connection')).to_contain_text('Connected')
                page.locator('#preflight').click();expect(page.locator('#readiness')).to_have_text('Ready',timeout=15000)
                expect(page.locator('#pending')).to_have_text(str(base_case_count))
                assert not app.store.all(),'Preflight must not run inference'
                page.locator('#run').click();expect(page.locator('#state-badge')).to_have_text('FINISHED',timeout=15000)
                expect(page.locator('#pending')).to_have_text('0');expect(page.locator('#complete')).to_have_text(str(base_case_count))
                screenshot=os.environ.get('WORKBENCH_SCREENSHOT')
                if screenshot:page.screenshot(path=screenshot,full_page=True)
                page.locator('nav button[data-page="results"]').click();expect(page.locator('.result-row')).to_have_count(base_case_count)
                page.get_by_role('button',name='Inspect',exact=True).first.click();expect(page.locator('#inspect')).to_be_visible()
                expect(page.locator('#result-json')).to_contain_text('"simulated": true')
                page.locator('#inspect .close-dialog').click()
                page.once('dialog',lambda d:d.accept())
                page.get_by_role('button',name='Delete / rerun',exact=True).first.click();expect(page.locator('.result-row')).to_have_count(base_case_count-1)
                page.locator('nav button[data-page="overview"]').click();page.locator('#run').click()
                expect(page.locator('#session-complete')).to_have_text('1',timeout=15000)
                expect(page.locator('#state-badge')).to_have_text('FINISHED',timeout=15000)
                page.locator('#run').click();page.wait_for_timeout(1700)
                expect(page.locator('#session-complete')).to_have_text('0')
                page.locator('nav button[data-page="models"]').click();expect(page.locator('.model-card')).to_have_count(1)
                select=page.locator('.model-card select');select.select_option('12');page.wait_for_timeout(1600)
                expect(select).to_have_value('12')
                page.locator('nav button[data-page="tests"]').click();expect(page.locator('#test-list article')).to_have_count(base_test_count)
                page.locator('#example-select').select_option('cached_questions');page.locator('#import-example').click()
                expect(page.locator('#test-list article')).to_have_count(base_test_count+1)
                page.locator('nav button[data-page="overview"]').click();page.locator('#run').click()
                expect(page.locator('#session-complete')).to_have_text('2',timeout=15000)
                expect(page.locator('#state-badge')).to_have_text('FINISHED',timeout=15000)
                with page.expect_download() as info:page.locator('#export').click()
                assert info.value.suggested_filename.endswith('.zip')
                page.locator('nav button[data-page="setup"]').click();page.locator('#browse-models').click()
                expect(page.locator('#browser')).to_be_visible();page.locator('#browser .close-dialog').click()
                page.locator('#model-root').fill('/example/unsaved-model-folder')
                page.locator('nav button[data-page="overview"]').click();page.wait_for_timeout(1500)
                page.locator('nav button[data-page="setup"]').click()
                expect(page.locator('#model-root')).to_have_value('/example/unsaved-model-folder')
                page.locator('#pairing').click();expect(page.locator('#pairing-value')).to_have_text('browser-test-key')
                page.set_viewport_size({'width':800,'height':1000})
                page.locator('nav button[data-page="overview"]').click()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Horizontal overflow'
                assert not errors,errors
                browser.close()
                print(('LOCAL HTTP BRIDGE; browser networking not exercised. ' if bridge else '')+'PASS: browser pairing, preflight, run, resume, deletion/rerun, models, stable dropdown, cached workflow import, export, host browsing, pairing display and responsive layout.')
        finally:
            app.control('stop')
            if app.thread:app.thread.join(5)
            server.shutdown();server.server_close();thread.join(5)

if __name__=='__main__':main()
