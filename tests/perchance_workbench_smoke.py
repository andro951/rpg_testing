"""Workbench UI + HTTP + real planner/scoring; simulated remote transport only."""
import json
import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright

from tests.test_perchance import fixture, FakeBackend
from workbench.controller import Controller
from workbench.domain import write_json
from workbench.server import WorkbenchServer
from workbench import perchance


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);write_json(root/'test_specs/fixture.json',fixture())
        app=Controller(root);app.settings.update(sync_source=False,perchance_only=True)
        server=WorkbenchServer(('127.0.0.1',0),app,'smoke-key')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        real_run=perchance.run
        FakeBackend.created=[];FakeBackend.response='READY';FakeBackend.failure=None
        try:
            with patch('workbench.inventory.detect_gpus',return_value=[{'name':'TEST GPU','total_gib':8}]), patch.object(perchance,'browser_executable',return_value=__file__), patch.object(perchance,'run',side_effect=lambda a,r,p:real_run(a,r,p,FakeBackend)), sync_playwright() as playwright:
                executable=os.environ.get('REPORT_BROWSER_EXECUTABLE')
                browser=playwright.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
                page=browser.new_page(viewport={'width':1500,'height':1000});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/#key=smoke-key')
                page.wait_for_function('() => state !== null && !state.busy')
                page.evaluate('() => setPage("one-model")')
                page.wait_for_function('() => runOptionsValid && !runOptionsLoading')
                page.locator('#one-model-model').select_option(perchance.MODEL_ID)
                page.wait_for_function('() => document.querySelectorAll("#one-model-tests input:checked").length===1')
                assert 'Unsupported settings/repetitions collapse' in page.locator('#one-model-summary').inner_text()
                page.locator('#one-model-check').click()
                page.wait_for_function('() => state?.report?.remote_provider && !state.busy')
                assert '3 requested cases' in page.locator('#plan').inner_text()
                assert app.report['plan']['independent_observations']==1
                page.evaluate('() => setPage("one-model")')
                page.wait_for_function('() => runOptionsValid && !runOptionsLoading')
                page.locator('#one-model-run').click()
                page.wait_for_function('() => state?.state==="finished" && !state.busy')
                assert len(app.store.all())==1
                assert len(FakeBackend.created[0].calls)==1
                page.evaluate('() => setPage("one-model")')
                page.wait_for_function('() => runOptionsValid && !runOptionsLoading')
                page.locator('#one-model-run').click()
                page.wait_for_function('() => state?.state==="finished" && !state.busy && state.completed_now===0')
                assert len(FakeBackend.created)==1
                page.evaluate('() => {setPage("results");return loadResults();}')
                page.get_by_role('button',name='Inspect',exact=True).first.click()
                text=page.locator('#result-json').inner_text()
                assert 'aliases' in text and 'remote_service' in text and 'applied_sampling' in text
                page.locator('#inspect').evaluate('(dialog)=>dialog.close()')
                page.evaluate('() => setPage("setup")')
                page.get_by_role('button',name='Load Perchance setup',exact=True).click()
                assert page.get_by_label('Skip local model-folder onboarding',exact=True).is_checked()
                assert not errors,errors
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(5)
    print('Perchance Workbench browser smoke passed (simulated transport; one run plus resume)')


if __name__=='__main__':main()