"""Normal browser -> CDP -> hosted iframe, with a simulated text service only."""
import errno
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from workbench import perchance, perchance_connection as connection


def launch_with_stderr(launch, executable, profile, port, url, stderr):
    """Keep the production launch arguments; capture only this fixture's child."""
    original_popen = connection.subprocess.Popen
    def capture(*args, **kwargs):
        kwargs['stderr'] = stderr
        return original_popen(*args, **kwargs)
    with patch.object(connection.subprocess, 'Popen', side_effect=capture):
        return launch(executable, profile, port, url, headless=True)


def report_browser_failure(executable, children, stderr_path):
    print(f'Fixture browser executable: {executable}', file=sys.stderr)
    if not children:
        print('Fixture browser did not return a child process.', file=sys.stderr)
    for index, process in enumerate(children, 1):
        code = process.poll()
        status = 'still running' if code is None else f'exit status {code}'
        print(f'Fixture browser child {index}: {status}', file=sys.stderr)
    captured = Path(stderr_path).read_text(encoding='utf-8', errors='replace')
    print('Fixture browser stderr:\n' + (captured or '(empty)'), file=sys.stderr)


class FixtureDirectory(tempfile.TemporaryDirectory):
    """Retry only transient final profile writes after owned-browser shutdown."""
    def cleanup(self):
        for attempt in range(6):
            try:
                return super().cleanup()
            except OSError as exc:
                if exc.errno not in (errno.ENOTEMPTY, errno.EBUSY) or attempt == 5:
                    raise
                time.sleep(0.1 * (attempt + 1))


def shutdown_fixture_browser(backend, children):
    """Close only fixture-owned Chromium before its temporary profile is removed."""
    try:
        try:
            if getattr(backend, 'browser', None):
                # Browser.close() on a CDP-attached Playwright browser only
                # disconnects. The protocol command asks Chromium itself to
                # shut down gracefully and finish writing its profile.
                backend.browser.new_browser_cdp_session().send('Browser.close')
        finally:
            for process in children:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
    finally:
        # Keep the CDP transport alive until browser exit has been observed.
        # Any command/wait error propagates; cleanup failures are not ignored.
        backend.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):pass
    def do_GET(self):
        if self.path == '/frame':
            body = '''<script>
            globalThis.calls=0;
            globalThis.aiTextPlugin=async options=>{
              globalThis.calls++;
              globalThis.lastSeed=options.seed;
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
        result = launch_with_stderr(original_launch, executable, profile, port, url, browser_stderr)
        child.append(result); return result
    executable = os.environ.get('REPORT_BROWSER_EXECUTABLE') or os.environ.get('CHROME_PATH')
    if not executable:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:executable = playwright.chromium.executable_path
    try:
        with FixtureDirectory() as tmp, \
             (Path(tmp) / 'browser-stderr.log').open('wb') as browser_stderr, \
             patch.object(perchance, 'validate_url', side_effect=lambda value: value), \
             patch.object(connection, 'launch', side_effect=fixture_launch) as launch:
            settings = {'perchance_url': url, 'perchance_browser': executable,
                        'perchance_profile': str(Path(tmp) / 'profile'), 'perchance_cdp_port': port}
            backend = connection.ControlledBrowserBackend(settings)
            try:
                backend.open(); page_url = backend.page.url
                backend.deadline = time.monotonic() + 300
                first = backend.generate([{'role': 'user', 'content': 'First fixture prompt'}], {'seed': 42}, None, threading.Event())
                assert first['text'] == ' RAW\n' and first['raw_chunks'][0]['text'] == ' RAW\n'
                assert first['effective_instruction'] == 'USER:\nFirst fixture prompt'
                assert backend.frame.evaluate('() => calls') == 1
                assert backend.frame.evaluate('() => lastSeed') == 42
                assert first['forwarded_sampling'] == {'seed': 42}
                assert first['applied_sampling'] is None and first['seed_reproducibility'] == 'unverified'
                backend.context.add_cookies([{'name': 'fixture', 'value': 'retained', 'url': url}])
                backend.close()
                assert child[-1].poll() is not None, 'Owned browser must exit before cleanup returns'
                assert not connection.listening(port), 'A finished run must not leave a browser window'
                assert (Path(settings['perchance_profile'])).is_dir(), 'Keep authentication profile'
                backend = connection.ControlledBrowserBackend(settings); backend.open()
                assert backend.page.url == page_url
                assert backend.frame.evaluate('() => calls') == 0, 'New run must not retain a stale hosted page'
                assert any(c['name'] == 'fixture' and c['value'] == 'retained' for c in backend.context.cookies())
                second = backend.generate([{'role': 'user', 'content': 'Second fixture prompt'}], {'seed': 104771}, None, threading.Event())
                assert second['text'] == ' RAW\n' and backend.frame.evaluate('() => calls') == 1
                assert backend.frame.evaluate('() => lastSeed') == 104771
                assert second['forwarded_sampling'] == {'seed': 104771}
                assert launch.call_count == 2
                assert backend.environment['browser_connection'] == 'normal-browser-cdp-v1'
                backend.close()
                assert not connection.listening(port)
                # Startup exceptions exercise production cleanup before open()
                # returns, with no request and no browser left for the next run.
                backend = connection.ControlledBrowserBackend({**settings, 'perchance_ready_seconds': 0})
                try:
                    backend.open()
                except RuntimeError as exc:
                    assert 'text plugin' in str(exc)
                else:
                    raise AssertionError('Expected a simulated plugin-readiness failure')
                assert child[-1].poll() is not None
                assert not connection.listening(port)
                # Independently launch a fixture-owned stand-in for an existing
                # user's browser. The production backend must not claim it.
                fixture_launch(executable, settings['perchance_profile'], port, url)
                connection.wait_for_browser(port, lambda: False)
                marker = Path(settings['perchance_profile']) / 'rpg-cdp-owner.json'
                marker.write_text(json.dumps({'port': port, 'profile': str(Path(settings['perchance_profile']).resolve())}))
                backend = connection.ControlledBrowserBackend(settings); backend.open()
                own_page = backend.page
                old_pages = [page for page in backend.context.pages if page != own_page]
                assert old_pages, 'Expected the pre-existing launch page'
                backend.close()
                assert own_page.is_closed()
                assert all(not page.is_closed() for page in old_pages)
                assert connection.listening(port), 'Leave the existing browser open'
                assert child[-1].poll() is None
            except Exception:
                browser_stderr.flush()
                report_browser_failure(executable, child, browser_stderr.name)
                raise
            finally:
                shutdown_fixture_browser(backend, child)
    finally:
        server.shutdown(); server.server_close(); thread.join(5)
    print('PASS: owned browser exits, attached session closes only its own tab, repeated runs retain cookies without accumulating windows, and startup failure cleans up. Text service SIMULATED; real browser/CDP/HTTP.')


if __name__ == '__main__':main()
