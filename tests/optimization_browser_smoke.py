"""Real browser/HTTP/UI with simulated model generation and objective trials."""
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_prompt_optimization import ROOT, MockRuntime, native
from workbench.controller import Controller
from workbench.server import WorkbenchServer
from optimization.storage import Store


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for folder in ('test_specs', 'examples', 'docs/prompt-optimization', 'optimization/definitions'):
            shutil.copytree(ROOT / folder, root / folder)
        app = Controller(root, demo=True)
        cohort = {'models': [native()], 'gpu': {'name': 'Mock GPU', 'total_gib': 8},
                  'default_generator': 'local-a', 'excluded': [], 'simulated': False}
        server = WorkbenchServer(('127.0.0.1', 0), app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        created = []
        def factory(owner, options):
            runtime = MockRuntime(owner, options)
            created.append(runtime)
            return runtime
        try:
            with patch('optimization.runtime.discover', return_value=cohort), \
                 patch('optimization.engine.discover', return_value=cohort), \
                 patch('optimization.engine.Runtime', side_effect=factory), sync_playwright() as playwright:
                executable = os.environ.get('REPORT_BROWSER_EXECUTABLE')
                browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
                page = browser.new_page(viewport={'width': 1440, 'height': 1080})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                page.get_by_role('button', name='Prompt Optimization', exact=True).click()
                page.get_by_role('button', name='Refresh host models', exact=True).click()
                expect(page.locator('#optimization-generator')).to_have_value('local-a')
                expect(page.locator('#optimization-max_attempts')).to_have_value('20')
                expect(page.locator('#optimization-reasoning')).not_to_be_checked()
                page.get_by_role('button', name='Start new session', exact=True).click()
                expect(page.locator('#optimization-status')).to_contain_text('perfect', timeout=30000)
                expect(page.locator('#optimization-ranking')).to_contain_text('100.0%')
                assert len(created[0].trials) == 6
                page.locator('#optimization-history details').first.locator('summary').click()
                page.get_by_role('button', name='Exact generation request', exact=True).click()
                expect(page.locator('#optimization-evidence')).to_be_visible()
                expect(page.locator('#optimization-evidence-content')).to_contain_text('SYSTEM_MESSAGE:')
                page.locator('#optimization-evidence').get_by_role('button', name='Close', exact=True).click()
                page.locator('#optimization-context_tokens').fill('65536')
                page.locator('#optimization-max_attempts').fill('30')
                with page.expect_response('**/api/optimization/settings') as response:
                    page.get_by_role('button', name='Apply settings to selected session', exact=True).click()
                assert response.value.status == 200
                expect(page.locator('#optimization-status')).to_contain_text('1/30 generation attempts')
                saved = Store(root).list()[0]
                assert saved['settings']['context_tokens'] == 65536
                assert len(saved['configuration_history']) == 1
                page.get_by_role('button', name='Continue session', exact=True).click()
                page.wait_for_function('() => state && !state.busy')
                assert len(created) == 2 and created[1].trials == [] and created[1].requests == []
                with page.expect_download() as download:
                    page.get_by_role('button', name='Export session', exact=True).click()
                archive = root / 'session.zip'
                download.value.save_as(archive)
                assert archive.stat().st_size > 0
                with page.expect_response('**/api/optimization/import') as response:
                    page.locator('#page-optimization input[type=file]').set_input_files(str(archive))
                assert response.value.status == 200
                page.wait_for_function('() => !PromptOptimization.Loading && !polling')
                expect(page.locator('#optimization-status')).to_contain_text('perfect')
                screenshot = os.environ.get('WORKBENCH_SCREENSHOT')
                if screenshot:
                    page.screenshot(path=screenshot, full_page=True)
                assert not errors, errors
                assert app.store.all() == []
                browser.close()
        finally:
            app.control('stop')
            if app.thread:
                app.thread.join(10)
            server.shutdown()
            server.server_close()
            thread.join(5)
    print('PASS: optimizer browser controls, complete rankings, readable evidence, resume and portable session export/import (simulated inference).')


if __name__ == '__main__':
    main()
