"""Real Logs-page download and copy UI; clipboard writes are captured in-browser."""
import os
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workbench.controller import Controller
from workbench.server import WorkbenchServer


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        app = Controller(root, demo=True)
        app.settings['hf_token'] = 'synthetic-private-token'
        app.log('fixture', 'First line\nSecond line — café')
        app.log('http_error', 'Operational watchdog expired; synthetic-private-token')
        server = WorkbenchServer(('127.0.0.1', 0), app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                executable = os.environ.get('REPORT_BROWSER_EXECUTABLE')
                browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
                page = browser.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                page.locator('nav button[data-page="logs"]').click()
                expect(page.locator('#log-view')).to_contain_text('Operational watchdog expired')
                text = page.locator('#log-view').inner_text()
                assert 'café' in text and '[REDACTED]' in text and 'synthetic-private-token' not in text
                download_button = page.get_by_role('button', name='Download logs', exact=True)
                copy_button = page.get_by_role('button', name='Copy logs', exact=True)
                expect(download_button).to_be_enabled()
                expect(copy_button).to_be_enabled()
                expect(page.locator('#export')).to_be_visible()
                with page.expect_download() as event:
                    download_button.click()
                download = event.value
                assert download.suggested_filename == 'rpg-testing-logs.txt'
                file = root / download.suggested_filename
                download.save_as(str(file))
                assert file.read_text(encoding='utf-8') == text

                page.evaluate('''() => {
                    Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {
                        writeText: async text => { window.copiedLogs = text; }
                    }});
                }''')
                copy_button.click()
                expect(page.locator('#toast')).to_have_text('Logs copied.')
                assert page.evaluate('window.copiedLogs') == text

                # Plain HTTP/Tailscale may have no clipboard API: verify selected-text fallback.
                page.evaluate('''() => {
                    Object.defineProperty(navigator, 'clipboard', {configurable: true, value: undefined});
                    document.execCommand = command => {
                        window.copyCommand = command;
                        const input = document.activeElement;
                        window.fallbackLogs = input.value.slice(input.selectionStart, input.selectionEnd);
                        return true;
                    };
                }''')
                copy_button.click()
                assert page.evaluate('window.copyCommand') == 'copy'
                assert page.evaluate('window.fallbackLogs') == text
                expect(page.locator('#copy-logs-dialog')).to_have_count(0)

                # Permission rejection also tries the fallback, rather than reporting false success.
                page.evaluate('''() => {
                    window.fallbackLogs = null;
                    Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {
                        writeText: async () => { throw new Error('Fixture clipboard denied'); }
                    }});
                }''')
                copy_button.click()
                page.wait_for_function('() => window.fallbackLogs !== null')
                assert page.evaluate('window.fallbackLogs') == text

                # If both automatic paths fail, keep a readable, selected manual-copy dialog.
                page.evaluate('''() => {
                    document.execCommand = () => false;
                    document.getElementById('toast').textContent = '';
                }''')
                copy_button.click()
                expect(page.locator('#copy-logs-dialog')).to_be_visible()
                expect(page.locator('#copy-logs-dialog')).to_contain_text('Press Ctrl+C')
                input = page.get_by_role('textbox', name='Logs to copy', exact=True)
                expect(input).to_have_value(text)
                assert input.evaluate('(input) => input.readOnly && input.selectionStart === 0 && input.selectionEnd === input.value.length')
                expect(page.locator('#toast')).not_to_have_text('Logs copied.')
                page.locator('#copy-logs-dialog').get_by_role('button', name='Close', exact=True).click()
                expect(page.locator('#copy-logs-dialog')).to_have_count(0)

                with app.lock:
                    app.logs.clear()
                expect(download_button).to_be_disabled()
                expect(copy_button).to_be_disabled()
                app.log('fixture', 'New live event')
                expect(download_button).to_be_enabled()
                expect(copy_button).to_be_enabled()
                with page.expect_download() as event:
                    download_button.click()
                event.value.save_as(str(file))
                assert file.read_text(encoding='utf-8') == page.locator('#log-view').inner_text()
                assert 'New live event' in file.read_text(encoding='utf-8')
                assert not errors, errors
                assert app.store.all() == []
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)
    print('PASS: UTF-8 logs-only download, displayed-text copy, missing/rejected clipboard fallback, manual-copy recovery, redaction, empty/live logs, and no benchmark runs (clipboard writes captured).')


if __name__ == '__main__':
    main()