"""Real HTTP/browser reproduction of empty provider error followed by blocked reset."""
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from tests.test_perchance import fixture, FakeBackend
from workbench.controller import Controller
from workbench.domain import write_json
from workbench.server import WorkbenchServer
from workbench import perchance, perchance_setup, perchance_connection


BLOCKED='Perchance security verification blocked startup. Complete verification in the worker window.'


class BlockedAfterProviderError(FakeBackend):
    def generate(self,messages,requested,schema,cancel):
        self.calls.append(messages)
        error=RuntimeError('Perchance returned stopReason=error')
        error.partial_response={'text':'','raw_chunks':[],
                                'provider_result':{'state':'error','stopReason':'error','rawResult':''}}
        raise error
    def reset(self):raise RuntimeError(BLOCKED)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);test=fixture();write_json(root/'test_specs/fixture.json',test)
        other=fixture();other['id']='second';other['variants'][0]['steps'][0]['prompt']+=' Different.'
        write_json(root/'test_specs/second.json',other)
        app=Controller(root);app.settings.update(sync_source=False,perchance_only=True)
        server=WorkbenchServer(('127.0.0.1',0),app)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        real_run=perchance.run;FakeBackend.created=[]
        def verified(owner):owner.message='Perchance connection fixture verified; no generation requests.'
        try:
            with patch('workbench.inventory.detect_gpus',return_value=[{'name':'TEST GPU','total_gib':8}]), \
                 patch.object(perchance,'browser_executable',return_value=__file__), \
                 patch.object(perchance_setup,'health',return_value={'ready':True,'reason':''}), \
                 patch.object(perchance,'run',side_effect=lambda a,r,p,**kw:real_run(a,r,p,BlockedAfterProviderError,**{k:v for k,v in kw.items() if k!='backend_factory'})) as remote_run, \
                 patch.object(perchance_connection,'verify_connection',side_effect=verified) as verify, \
                 sync_playwright() as playwright:
                executable=os.environ.get('REPORT_BROWSER_EXECUTABLE') or os.environ.get('CHROME_PATH')
                browser=playwright.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
                page=browser.new_page(viewport={'width':1500,'height':1000});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                page.wait_for_function('() => state !== null && !state.busy')
                page.locator('#run').click()
                expect(page.locator('#state-badge')).to_have_text('ERROR',timeout=15000)
                dialog=page.get_by_role('dialog',name='Perchance needs attention')
                expect(dialog).to_be_visible()
                expect(page.locator('#worker-failure-reason')).to_have_text(BLOCKED)
                expect(page.locator('#worker-failure-host')).to_contain_text('PC hosting the worker')
                expect(page.locator('#worker-failure-host')).to_contain_text('Tailscale control page does not display')
                expect(page.locator('#current')).to_have_text('Operation stopped by an error')
                assert not app.snapshot()['progress']['active']
                record=app.store.all()[0]
                assert record['status']=='error' and record['calls'][0]['text']==''
                assert len(app.store.all())==1 and len(FakeBackend.created[0].calls)==1
                failure_id=app.snapshot()['failure']['id']
                screenshot=os.environ.get('WORKBENCH_SCREENSHOT')
                if screenshot:page.screenshot(path=screenshot,full_page=True)
                dialog.get_by_role('button',name='Close',exact=True).click()
                page.wait_for_timeout(1600)
                expect(dialog).not_to_be_visible()
                expect(page.locator('#worker-failure')).to_be_visible()
                assert app.snapshot()['failure']['id']==failure_id
                page.reload();expect(dialog).to_be_visible()
                assert len(FakeBackend.created)==1,'Reload/polling must never retry generation'
                dialog.get_by_role('button',name='Verify Perchance on host',exact=True).click()
                page.wait_for_function('() => !state.busy && state.state==="idle" && !state.failure')
                verify.assert_called_once()
                expect(page.locator('#worker-failure')).not_to_be_visible()
                expect(page.locator('#current')).to_have_text('Perchance browser connected')
                assert len(FakeBackend.created[0].calls)==1
                assert len(app.store.all())==1
                #An explicitly requested run can also finish with saved errors rather than throwing.
                FakeBackend.failure=RuntimeError
                remote_run.side_effect=lambda a,r,p,**kw:real_run(a,r,p,FakeBackend,**{k:v for k,v in kw.items() if k!='backend_factory'})
                page.locator('#run').click()
                expect(page.locator('#state-badge')).to_have_text('FINISHED WITH ERRORS',timeout=15000)
                finished=page.get_by_role('dialog',name='Run finished with errors',exact=True)
                expect(finished).to_be_visible()
                expect(page.locator('#worker-failure-reason')).to_contain_text('2 infrastructure error')
                expect(page.locator('#worker-failure-host')).not_to_be_visible()
                assert len(app.store.all())==2
                assert any(record.get('attempts') for record in app.store.all()),'Original failed attempt is retained'
                FakeBackend.failure=None
                assert not errors,errors
                browser.close()
        finally:
            app.control('stop')
            if app.thread:app.thread.join(5)
            server.shutdown();server.server_close();thread.join(5)
    print('PASS: empty provider error + security-blocked reset surfaced in controller browser, stopped progress, retained evidence, reload, one popup, explicit host verification and no automatic retry. Inference/verification SIMULATED; real HTTP/browser.')


if __name__=='__main__':main()
