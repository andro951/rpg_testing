"""Real browser/model-manager wiring; external Hub/assets are small verified fixtures."""
from __future__ import annotations
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workbench.controller import Controller
from workbench.domain import write_json
from workbench.downloads import download_model
from workbench.hub import group_variants
from workbench.server import WorkbenchServer


def main():
    from playwright.sync_api import sync_playwright,expect
    root=Path(__file__).resolve().parents[1]
    data=b'GGUF'+struct.pack('<IQQ',3,0,0)
    h=hashlib.sha256(data).hexdigest()
    detail=group_variants({'id':'fixture/model','sha':'a'*40,'cardData':{'license':'apache-2.0'},
        'siblings':[{'rfilename':f'Model-{q}.gguf','size':len(data),'lfs':{'sha256':h,'size':len(data)}} for q in ('Q5_K_M','Q4_K_M')]},8)
    release={'id':'runtime-fixture','tag':'test-build','name':'SIMULATED-native-runtime.zip','size_bytes':20,
             'note':'Fake runtime fixture for browser wiring; no binary is executed.','assets':[]}
    with tempfile.TemporaryDirectory() as temp:
        project=Path(temp)/'repository';project.mkdir();models=Path(temp)/'chosen-models';models.mkdir()
        shutil.copytree(root/'test_specs',project/'test_specs');shutil.copytree(root/'examples',project/'examples')
        write_json(project/'models.json',[])
        app=Controller(project);app.selftest=lambda:None;app.configure({'sync_source':False})
        real_scan=app.scan_folder
        def slow_scan():
            time.sleep(.75)
            return real_scan()
        app.scan_folder=slow_scan
        server=WorkbenchServer(('127.0.0.1',0),app,'model-browser-key')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def opener(*args,**kwargs):
            response=io.BytesIO(data);response.headers={'Content-Length':str(len(data))};return response
        def fixture_download(model,folder,cancel,log,**kwargs):
            assert Path(folder)==models
            return download_model(model,folder,cancel,log,opener=opener,**kwargs)
        def fixture_runtime(bundle,repo,*args,**kwargs):
            assert Path(repo)==project
            exe=project/'.local/runtime/test-build/llama-server';exe.parent.mkdir(parents=True);exe.write_bytes(b'NOT EXECUTABLE TEST FIXTURE')
            return str(exe)
        try:
            with patch('workbench.hub.HubClient.search',return_value=[{'id':'fixture/model','downloads':1,'likes':0,'license':'apache-2.0'}]), \
                 patch('workbench.hub.HubClient.variants',return_value=detail), \
                 patch('workbench.downloads.download_model',side_effect=fixture_download), \
                 patch('workbench.runtimes.RuntimeClient.releases',return_value=[release]), \
                 patch('workbench.runtimes.install',side_effect=fixture_runtime), \
                 patch('workbench.native.capabilities',return_value={'version':'TEST FIXTURE'}), \
                 patch('workbench.server.select_directory',return_value=str(models)),sync_playwright() as p:
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
                    page.add_script_tag(content="""const store={'rpg-worker-key':'model-browser-key'};
Object.defineProperty(window,'sessionStorage',{value:{getItem:k=>store[k]||null,setItem:(k,v)=>store[k]=v}});
window.fetch=async(path,options={})=>{const r=await window.workerBridge(path,options);return new Response(Uint8Array.from(atob(r.body),c=>c.charCodeAt(0)),{status:r.status,headers:{'Content-Type':r.type}})};""")
                    page.add_script_tag(content=(root/'workbench/web/app.js').read_text())
                else:page.goto(base+'/#key=model-browser-key')
                expect(page.locator('#folder-onboarding')).to_be_visible()
                assert app.settings['model_root']==''
                page.locator('#onboarding-choose').click()
                expect(page.locator('#page-models')).to_be_visible(timeout=5000)
                expect(page.locator('#state-badge')).to_have_text('SCANNING',timeout=3000)
                expect(page.locator('#alert')).not_to_be_visible()
                expect(page.locator('#empty-folder')).to_be_visible(timeout=10000)
                expect(page.locator('#model-root')).to_have_value(str(models.resolve()))
                assert list(models.iterdir())==[], 'Selecting a folder must not trigger any download'
                page.locator('#accept-empty').click();expect(page.locator('#empty-folder')).not_to_be_visible()
                page.locator('#hub-query').fill('Example model');page.locator('#hub-search').click()
                expect(page.locator('#hub-results article')).to_have_count(1,timeout=10000)
                page.get_by_role('button',name='View quantizations',exact=True).click()
                expect(page.locator('#hub-variants input[type="checkbox"]')).to_have_count(2,timeout=10000)
                page.locator('#hub-variants input[type="checkbox"]').first.check()
                page.wait_for_timeout(1100)
                assert page.locator('#hub-variants input[type="checkbox"]').first.is_checked(), 'Polling reset a selection'
                page.locator('#hub-variants input[type="checkbox"]').last.check()
                page.once('dialog',lambda d:d.accept());page.locator('#hub-download').click()
                expect(page.locator('#state-badge')).to_have_text('IDLE',timeout=10000)
                expect(page.locator('#message')).to_contain_text('Models installed',timeout=10000)
                assert len(list(models.rglob('*.gguf')))==2
                assert list(project.rglob('*.gguf'))==[], 'Model downloads leaked into the repository'
                page.locator('nav button[data-page="models"]').click()
                expect(page.locator('.model-card')).to_have_count(2)
                page.locator('nav button[data-page="runtime"]').click();page.locator('#runtime-list').click()
                expect(page.locator('#runtime-select option')).to_have_count(1,timeout=10000)
                assert app.settings['llama_path']=='', 'Listing runtimes must not install one'
                page.once('dialog',lambda d:d.accept());page.locator('#runtime-install').click()
                expect(page.locator('#runtime-installed')).to_contain_text('llama-server',timeout=10000)
                assert Path(app.settings['llama_path']).is_relative_to(project)
                screenshot=os.environ.get('WORKBENCH_MODEL_SCREENSHOT')
                page.locator('nav button[data-page="find"]').click()
                if screenshot:page.screenshot(path=screenshot,full_page=True)
                page.set_viewport_size({'width':800,'height':1000})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                assert not errors,errors
                browser.close()
                print('PASS: real browser + authenticated controller: native folder picker, nonblocking scan, empty confirmation, Hub search, quant selection, verified fixture download to chosen folder, installed models, explicit runtime installation. External services are fixture-backed, not live downloads.')
        finally:
            app.control('stop')
            if app.thread:app.thread.join(5)
            server.shutdown();server.server_close();thread.join(5)

if __name__=='__main__':main()
