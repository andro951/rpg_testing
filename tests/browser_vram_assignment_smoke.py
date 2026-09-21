"""Regression for multiple locally discovered unassigned models and VRAM card controls."""
from __future__ import annotations
import base64
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workbench.controller import Controller
from workbench.domain import write_json
from workbench.server import WorkbenchServer

DATA=b'GGUF'+struct.pack('<IQQ',3,0,0)

def main():
    from playwright.sync_api import sync_playwright,expect
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as temp:
        project=Path(temp)/'repository';project.mkdir()
        models=Path(temp)/'models';models.mkdir()
        shutil.copytree(root/'test_specs',project/'test_specs');shutil.copytree(root/'examples',project/'examples')
        write_json(project/'models.json',[])
        for name in ('Alpha-Q4_K_M.gguf','Beta-Q4_K_M.gguf','Gamma-Q4_K_M.gguf'):
            (models/name).write_bytes(DATA)
        app=Controller(project);app.selftest=lambda:None;app.configure({'sync_source':False,'model_root':str(models)});app.scan_folder()
        # If VRAM assignment accidentally tries to fingerprint weights, fail immediately.
        app.fingerprint=lambda item: (_ for _ in ()).throw(AssertionError('VRAM assignment hashed model weights'))
        server=WorkbenchServer(('127.0.0.1',0),app,'vram-key')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                exe=os.environ.get('CHROME_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
                browser=p.chromium.launch(headless=True,args=['--no-sandbox'],**({'executable_path':exe} if exe else {}))
                page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda err:errors.append(str(err)))
                base=f'http://127.0.0.1:{server.server_port}'
                if os.environ.get('WORKBENCH_BROWSER_BRIDGE')=='1':
                    def bridge(path,options):
                        body=options.get('body')
                        req=urllib.request.Request(base+path,data=body.encode() if body else None,headers=options.get('headers',{}))
                        try:response=urllib.request.urlopen(req,timeout=15)
                        except urllib.error.HTTPError as error:response=error
                        with response:return {'status':response.code,'type':response.headers.get('Content-Type',''),
                                               'body':base64.b64encode(response.read()).decode()}
                    page.expose_function('workerBridge',bridge)
                    html=(root/'workbench/web/index.html').read_text().replace('<link rel="stylesheet" href="/style.css">','').replace('<script src="/app.js"></script>','')
                    page.set_content(html);page.add_style_tag(content=(root/'workbench/web/style.css').read_text())
                    page.add_script_tag(content="""const store={'rpg-worker-key':'vram-key'};
Object.defineProperty(window,'sessionStorage',{value:{getItem:k=>store[k]||null,setItem:(k,v)=>store[k]=v}});
window.fetch=async(path,options={})=>{const r=await window.workerBridge(path,options);return new Response(Uint8Array.from(atob(r.body),c=>c.charCodeAt(0)),{status:r.status,headers:{'Content-Type':r.type}})};""")
                    page.add_script_tag(content=(root/'workbench/web/app.js').read_text())
                else:
                    page.goto(base+'/#key=vram-key')
                page.locator('nav button[data-page="models"]').click()
                cards=page.locator('.model-card');expect(cards).to_have_count(3)
                for i in range(3):
                    card=cards.nth(i)
                    expect(card).to_contain_text('VRAM: Unassigned')
                    expect(card.locator('select')).to_have_value('')
                    expect(card.get_by_role('button',name='Save VRAM',exact=True)).to_be_disabled()
                    expect(card.get_by_role('button',name='Accept recommended 8 GB',exact=True)).to_be_enabled()
                before=os.environ.get('WORKBENCH_VRAM_BEFORE_SCREENSHOT')
                if before:page.screenshot(path=before,full_page=True)

                cards.nth(0).get_by_role('button',name='Accept recommended 8 GB',exact=True).click()
                expect(cards.nth(0)).to_contain_text('VRAM: 8 GB assigned',timeout=5000)
                expect(cards.nth(0).locator('select')).to_have_value('8')
                expect(cards.nth(0).get_by_role('button',name='Recommended 8 GB applied',exact=True)).to_be_disabled()
                # Other cards must remain independent and editable.
                for i in (1,2):
                    expect(cards.nth(i)).to_contain_text('VRAM: Unassigned')
                    expect(cards.nth(i).locater('select') if False else cards.nth(i).locator('select')).to_be_enabled()
                    expect(cards.nth(i).get_by_role('button',name='Accept recommended 8 GB',exact=True)).to_be_enabled()

                second=cards.nth(1);second_select=second.locator('select')
                second_select.select_option('12')
                expect(second_select).to_have_value('12')
                expect(second.get_by_role('button',name='Save VRAM',exact=True)).to_be_enabled()
                # Polling must not wipe the unsaved draft.
                page.wait_for_timeout(1500)
                expect(second_select).to_have_value('12')
                expect(second.get_by_role('button',name='Save VRAM',exact=True)).to_be_enabled()
                second.get_by_role('button',name='Save VRAM',exact=True).click()
                expect(second).to_contain_text('VRAM: 12 GB assigned',timeout=5000)
                expect(second_select).to_have_value('12')
                expect(cards.nth(2)).to_contain_text('VRAM: Unassigned')
                expect(cards.nth(2).get_by_role('button',name='Accept recommended 8 GB',exact=True)).to_be_enabled()
                expect(page.locator('#state-badge')).to_have_text('IDLE')
                expect(page.locator('#alert')).not_to_be_visible()

                after=os.environ.get('WORKBENCH_VRAM_AFTER_SCREENSHOT')
                if after:page.screenshot(path=after,full_page=True)
                assert not errors,errors
                browser.close()
                print('PASS: three unassigned local models; recommendation and manual VRAM saves stay card-local, visible, editable, and do not hash weights.')
        finally:
            app.control('stop')
            if app.thread:app.thread.join(5)
            server.shutdown();server.server_close();thread.join(5)

if __name__=='__main__':main()
