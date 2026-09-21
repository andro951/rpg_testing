"""Browser integration for explicit storage + Hub discovery; network metadata is stubbed."""
import base64,hashlib,json,os,shutil,struct,sys,tempfile,threading,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workbench.controller import Controller
from workbench.server import WorkbenchServer
from workbench.hub import group_variants

ROOT=Path(__file__).resolve().parents[1]

def main():
 from playwright.sync_api import sync_playwright,expect
 with tempfile.TemporaryDirectory() as d:
  root=Path(d)/'repository';root.mkdir();models=Path(d)/'MY MODELS DRIVE';models.mkdir()
  shutil.copytree(ROOT/'test_specs',root/'test_specs');shutil.copytree(ROOT/'examples',root/'examples')
  (root/'models.json').write_text('[]')
  app=Controller(root);app.selftest=lambda:None;app.settings['sync_source']=False
  server=WorkbenchServer(('127.0.0.1',0),app,'setup-test');threading.Thread(target=server.serve_forever,daemon=True).start()
  metadata=group_variants({'id':'publisher/test-model','sha':'a'*40,'siblings':[{'rfilename':'Model-Q5_K_M.gguf','size':6470000000},{'rfilename':'Model-Q4_K_M.gguf','size':5630000000}]},8)
  def download(model,folder,*args,**kwargs):
   f=Path(folder)/model['files'][0];f.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,0));return [str(f)]
  try:
   with patch('workbench.hub.HubClient.search',return_value=[{'id':'publisher/test-model','downloads':42,'likes':1,'license':'apache-2.0'}]),patch('workbench.hub.HubClient.variants',return_value=metadata),patch('workbench.downloads.download_model',side_effect=download),patch('workbench.runtimes.RuntimeClient.releases',return_value=[{'id':'demo-runtime','tag':'test-build','name':'Official build fixture','note':'Simulated release metadata; not installed','size_bytes':100,'assets':[{}]}]):
    with sync_playwright() as pw:
     exe=os.environ.get('CHROME_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
     browser=pw.chromium.launch(headless=True,args=['--no-sandbox'],**({'executable_path':exe} if exe else {}))
     page=browser.new_page(viewport={'width':1440,'height':1060});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
     base=f'http://127.0.0.1:{server.server_port}'
     if os.environ.get('WORKBENCH_BROWSER_BRIDGE')=='1':
      def transport(path,options):
       data=options.get('body');req=urllib.request.Request(base+path,data=data.encode() if data else None,headers=options.get('headers',{}))
       try:res=urllib.request.urlopen(req,timeout=15)
       except urllib.error.HTTPError as e:res=e
       with res:return {'status':res.code,'type':res.headers.get('Content-Type',''),'body':base64.b64encode(res.read()).decode()}
      page.expose_function('localHttpTestBridge',transport)
      html=(ROOT/'workbench/web/index.html').read_text().replace('<link rel="stylesheet" href="/style.css">','').replace('<script src="/app.js"></script>','')
      page.set_content(html);page.add_style_tag(content=(ROOT/'workbench/web/style.css').read_text())
      page.add_script_tag(content="""const store={'rpg-worker-key':'setup-test'};Object.defineProperty(window,'sessionStorage',{value:{getItem:k=>store[k]||null,setItem:(k,v)=>store[k]=v}});window.fetch=async(path,options={})=>{const r=await window.localHttpTestBridge(path,options);return new Response(Uint8Array.from(atob(r.body),c=>c.charCodeAt(0)),{status:r.status,headers:{'Content-Type':r.type}})};""")
      page.add_script_tag(content=(ROOT/'workbench/web/app.js').read_text())
     else:page.goto(base+'/#key=setup-test')
     expect(page.locator('#model-onboarding')).to_be_visible()
     assert app.settings['model_root']==''
     page.locator('#choose-initial-models').click();expect(page.locator('#browser')).to_be_visible()
     page.locator('#browse-path').fill(str(models));page.locator('#browse-go').click()
     expect(page.locator('#browse-path')).to_have_value(str(models))
     page.wait_for_function("document.getElementById('browse-items').children.length===0")
     page.locator('#choose-folder').click();expect(page.locator('#empty-model-folder')).to_be_visible(timeout=10000)
     expect(page.locator('#empty-folder-path')).to_have_text(str(models))
     page.locator('#confirm-empty-models').click();expect(page.locator('#empty-model-folder')).not_to_be_visible()
     expect(page.locator('#hub-query')).to_be_visible()
     page.locator('#hub-query').fill('Test model');page.locator('#hub-search').click()
     expect(page.locator('#hub-list')).to_contain_text('publisher/test-model',timeout=10000)
     page.get_by_role('button',name='View quantizations',exact=True).click()
     expect(page.locator('#variant-panel')).to_be_visible();expect(page.locator('#variant-list input')).to_have_count(2)
     page.get_by_role('checkbox',name='Download Q4_K_M',exact=True).check()
     page.once('dialog',lambda dlg:dlg.accept());page.locator('#download-variants').click()
     expect(page.locator('#message')).to_contain_text('Downloads verified',timeout=10000)
     assert (models/'Model-Q4_K_M.gguf').exists()
     assert not (models/'Model-Q5_K_M.gguf').exists()
     assert not list(root.rglob('*.gguf'))
     assert app.catalog()[0]['required_vram_gb']==8
     page.locator('nav button[data-page="setup"]').click();page.locator('#runtime-list').click()
     expect(page.locator('#runtime-options')).to_contain_text('Official build fixture',timeout=10000)
     assert not app.settings['llama_path'],'Browsing runtimes must not install one'
     if os.environ.get('WORKBENCH_MODELS_SCREENSHOT'):
      page.locator('nav button[data-page="hub"]').click();page.screenshot(path=os.environ['WORKBENCH_MODELS_SCREENSHOT'],full_page=True)
     assert not errors,errors
     browser.close()
     print('PASS: explicit folder onboarding, empty confirmation, Hub search/variants, selected-only model download, VRAM registration, runtime browsing without installation. Metadata/downloads are fixture-controlled, not live service checks.')
  finally:
   app.control('stop')
   if app.thread:app.thread.join(5)
   server.shutdown();server.server_close()

if __name__=='__main__':main()
