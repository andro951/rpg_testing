"""Normal browser -> CDP -> hosted iframe, with a simulated text service only."""
import os
import socket
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from workbench import perchance, perchance_connection as connection


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):pass
    def do_GET(self):
        if self.path == '/frame':
            body = '''<script>
            globalThis.calls=0;
            globalThis.aiTextPlugin=async options=>{
              globalThis.calls++;
              options.onChunk({textChunk:" RAW\\n",isFromStartWith:false});
              return {generatedText:" RAW\\n",stopReason:"natural"};
            };
            </script><p>Simulated hosted text plugin</p>'''
        else:
            body = '<iframe src="/frame"></iframe>'
        self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers()
        self.wfile.write(body.encode())


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    url = f'http://127.0.0.1:{server.server_port}/'
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0)); port = reservation.getsockname()[1]
    child = []; original_launch = connection.launch
    def fixture_launch(executable, profile, port, url):
        result = original_launch(executable, profile, port, url, headless=True)
        child.append(result); return result
    executable = os.environ.get('REPORT_BROWSER_EXECUTABLE') or os.environ.get('CHROME_PATH')
    if not executable:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:executable = playwright.chromium.executable_path
    try:
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(perchance, 'validate_url', side_effect=lambda value: value), \
             patch.object(connection, 'launch', side_effect=fixture_launch) as launch:
            settings = {'perchance_url': url, 'perchance_browser': executable,
                        'perchance_profile': str(Path(tmp) / 'profile'), 'perchance_cdp_port': port}
            backend = connection.ControlledBrowserBackend(settings)
            try:
                backend.open(); page_url = backend.page.url
                backend.deadline = time.monotonic() + 300
                first = backend.generate([{'role': 'user', 'content': 'First fixture prompt'}], {}, None, threading.Event())
                assert first['text'] == ' RAW\n' and first['raw_chunks'][0]['text'] == ' RAW\n'
                assert first['effective_instruction'] == 'USER:\nFirst fixture prompt'
                assert backend.frame.evaluate('() => calls') == 1
                backend.close()
                assert connection.listening(port), 'Disconnect must leave the normal browser running'
                backend = connection.ControlledBrowserBackend(settings); backend.open()
                assert backend.page.url == page_url
                assert backend.frame.evaluate('() => calls') == 1, 'Hosted page must survive reconnect'
                second = backend.generate([{'role': 'user', 'content': 'Second fixture prompt'}], {}, None, threading.Event())
                assert second['text'] == ' RAW\n' and backend.frame.evaluate('() => calls') == 2
                launch.assert_called_once()
                assert backend.environment['browser_connection'] == 'normal-browser-cdp-v1'
            finally:
                #Only this fixture-owned browser is shut down by the test.
                if getattr(backend, 'browser', None):backend.browser.close()
                backend.close()
                for process in child:
                    if process.poll() is None:process.terminate()
                    process.wait(timeout=10)
    finally:
        server.shutdown(); server.server_close(); thread.join(5)
    print('PASS: separately launched normal browser, CDP attachment, iframe worker, raw text/chunks, disconnect, preserved page and reconnect without relaunch. Text service SIMULATED; real browser/CDP/HTTP.')


if __name__ == '__main__':main()
