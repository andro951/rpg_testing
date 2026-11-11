"""Readiness UI coverage smoke with Chromium; no model inference or GPU use."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import tempfile
import threading

from workbench.controller import Controller
from workbench.server import WorkbenchServer


def main():
    from playwright.sync_api import sync_playwright, expect
    source = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for name in ('prompt_builder/templates', 'test_specs', 'prompts/current-suite'):
            shutil.copytree(source / name, root / name)
        app = Controller(root, True)
        server = WorkbenchServer(('127.0.0.1', 0), app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                executable = os.environ.get('REPORT_BROWSER_EXECUTABLE') or shutil.which('chromium') or shutil.which('google-chrome')
                browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                expect(page.locator('#connection')).to_contain_text('Connected')
                page.locator('#preflight').click()
                expect(page.locator('#readiness')).to_have_text('Ready', timeout=20000)
                expect(page.locator('#issues')).to_contain_text('Full current suite: 21 cases')
                expect(page.locator('#issues')).to_contain_text('6 output formats')
                expect(page.locator('#issues')).to_contain_text('372 distinct prompts × 1 repetition(s) = 372 observations/model')
                expect(page.locator('#issues')).to_contain_text('Omitted current prompts: 0')
                expect(page.locator('#pending')).to_have_text('372')
                screenshot = os.environ.get('WORKBENCH_COVERAGE_SCREENSHOT')
                if screenshot:
                    page.screenshot(path=screenshot, full_page=True)
                page.reload()
                expect(page.locator('#issues')).to_contain_text('Full current suite: 21 cases')
                page.set_viewport_size({'width': 390, 'height': 844})
                expect(page.locator('#issues')).to_contain_text('372 observations/model')
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.get_by_role('button', name='Run Individual Test', exact=True).click()
                page.locator('#individual-model').select_option(app.catalog()[0]['id'])
                page.locator('#individual-test').select_option('copy_value__json_dot')
                page.locator('#individual-variant').select_option('normal_json')
                page.locator('#individual-check').click()
                expect(page.locator('#readiness')).to_have_text('Ready', timeout=20000)
                expect(page.locator('#issues')).to_contain_text('Explicit subset: 1 cases')
                expect(page.locator('#issues')).to_contain_text('1 distinct prompts × 1 repetition(s) = 1 observations/model')
                expect(page.locator('#issues')).to_contain_text('Omitted current prompts: 371')
                # A missing required definition must turn readiness red, not reduce the count.
                missing = root / 'test_specs/copy_value__json_dot.json'
                saved = missing.read_bytes()
                missing.unlink()
                page.locator('#preflight').click()
                expect(page.locator('#readiness')).to_have_text('Needs attention', timeout=20000)
                expect(page.locator('#issues')).to_contain_text('Build test inventory does not match manifest')
                missing.write_bytes(saved)
                page.locator('#preflight').click()
                expect(page.locator('#readiness')).to_have_text('Ready', timeout=20000)
                assert app.store.all() == [], 'Preflight must not run inference, even simulated inference'
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    print('Suite coverage browser smoke passed: full/targeted counts, reload, mobile, fail-closed recovery; no inference')


if __name__ == '__main__':
    main()
