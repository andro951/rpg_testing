"""Real browser/HTTP consent flow; installer and inference are simulated."""
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_perchance import fixture, FakeBackend
from workbench.controller import Controller
from workbench.domain import write_json
from workbench.server import WorkbenchServer
from workbench import perchance, perchance_setup


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp); write_json(root / 'test_specs/fixture.json', fixture())
        app = Controller(root); app.settings.update(sync_source=False, perchance_only=True)
        server = WorkbenchServer(('127.0.0.1', 0), app)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        real_run = perchance.run
        FakeBackend.created = []; FakeBackend.response = 'READY'; FakeBackend.failure = None
        status = {'ready': False, 'reason': 'Fixture: Playwright dependency missing.'}
        def installed(owner):
            status.update(ready=True, reason='')
            return dict(status)
        try:
            with patch('workbench.inventory.detect_gpus', return_value=[{'name': 'TEST GPU', 'total_gib': 8}]), \
                 patch.object(perchance, 'browser_executable', return_value=__file__), \
                 patch.object(perchance_setup, 'health', side_effect=lambda owner: dict(status)), \
                 patch.object(perchance_setup, 'install', side_effect=installed) as install, \
                 patch.object(perchance, 'run', side_effect=lambda a, r, p, **kw: real_run(a, r, p, FakeBackend, **kw)), \
                 sync_playwright() as playwright:
                executable = os.environ.get('REPORT_BROWSER_EXECUTABLE') or os.environ.get('CHROME_PATH')
                browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
                page = browser.new_page(viewport={'width': 1500, 'height': 1000}); errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                page.wait_for_function('() => state !== null && !state.busy')
                page.locator('#preflight').click()
                expect(page.locator('#perchance-install')).to_be_visible()
                expect(page.locator('#perchance-install-reason')).to_contain_text('dependency missing')
                assert app.report is None, 'Install offer must precede normal preflight'
                assert not FakeBackend.created
                screenshot = os.environ.get('WORKBENCH_SCREENSHOT')
                if screenshot:page.screenshot(path=screenshot, full_page=True)
                page.locator('#perchance-install-no').click()
                page.wait_for_function('() => state?.report?.ready && !state.busy')
                assert app.report['perchance_setup']['status'] == 'declined'
                page.locator('#run').click()
                page.wait_for_function('() => state?.state === "finished" && !state.busy')
                assert not FakeBackend.created
                install.assert_not_called()
                page.locator('#run').click()
                expect(page.locator('#perchance-install')).to_be_visible()
                page.locator('#perchance-install-yes').click()
                page.wait_for_function('() => state?.state === "finished" && !state.busy && state.completed_now===1')
                install.assert_called_once()
                assert len(FakeBackend.created) == 1
                assert app.report['perchance_setup']['status'] == 'installed'
                page.locator('#run').click()
                page.wait_for_function('() => state?.state === "finished" && !state.busy && state.completed_now===0')
                assert len(FakeBackend.created) == 1, 'Resume must preserve the single observation'
                record = app.store.all()[0]; app.delete_result(record['model_id'], record['case_id'])
                status.update(ready=False, reason='Fixture: broken browser launch.')
                page.locator('#run').click()
                expect(page.locator('#perchance-install')).to_be_visible()
                page.locator('#perchance-install-no').click()
                page.wait_for_function('() => state?.state === "finished" && !state.busy')
                page.locator('#run').click()
                expect(page.locator('#perchance-install')).to_be_visible()
                #Reload and a second tab see the same server-owned prompt.
                prompt_id = app.snapshot()['perchance_setup_prompt']['id']
                page.reload(); expect(page.locator('#perchance-install')).to_be_visible()
                assert app.snapshot()['perchance_setup_prompt']['id'] == prompt_id
                page.evaluate('async () => {await api("/api/control",{action:"stop"});}')
                page.wait_for_function('() => state?.state === "stopped" && !state.busy')
                expect(page.locator('#perchance-install')).not_to_be_visible()
                assert not errors, errors
                browser.close()
        finally:
            app.control('stop')
            if app.thread:app.thread.join(5)
            server.shutdown(); server.server_close(); thread.join(5)
    print('PASS: first preflight install popup, decline reused for one run, next-run prompt, approved setup, resume, broken browser, reload and cancellation. Installer and inference SIMULATED; real local HTTP/browser.')


if __name__ == '__main__':main()
