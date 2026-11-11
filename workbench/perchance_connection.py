"""Normal browser/CDP lifecycle, separate from inference and observation identity."""
from __future__ import annotations
import json
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from . import perchance
from .domain import canonical, write_json
from .workflows import Cancelled

DEFAULT_PORT = 9223


def endpoint(port):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Perchance CDP port must be an integer from 1024 to 65535')
    return f'http://127.0.0.1:{port}'


def listening(port):
    with socket.socket() as probe:
        probe.settimeout(.2)
        return probe.connect_ex(('127.0.0.1', port)) == 0


def wait_for_browser(port, cancel, seconds=30):
    address = endpoint(port)
    opener = build_opener(ProxyHandler({}))
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if cancel():
            raise Cancelled('Stopped while opening the Perchance browser')
        try:
            with opener.open(address + '/json/version', timeout=.5) as response:
                version = json.load(response)
            if isinstance(version.get('webSocketDebuggerUrl'), str):
                return address
        except (OSError, ValueError):
            pass  #The independently launched browser may still be starting.
        time.sleep(.1)
    raise RuntimeError('Perchance browser did not expose its local CDP connection. Check the host browser and browser policies.')


def launch(executable, profile, port, url, headless=False):
    endpoint(port)
    if not executable:
        raise RuntimeError('Perchance needs an installed browser executable')
    Path(profile).mkdir(parents=True, exist_ok=True)
    args = [executable, f'--remote-debugging-port={port}', '--remote-debugging-address=127.0.0.1',
            f'--user-data-dir={Path(profile).resolve()}', '--new-window', '--no-first-run',
            '--no-default-browser-check', '--disable-session-crashed-bubble']
    if headless:
        args.append('--headless=new')
    args.append(url)
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))


def _stop_probe_browser(child):
    if child is None:
        return
    try:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f'Perchance probe shutdown warning: {exc}', file=sys.stderr)


def _cleanup_probe_profile(profile):
    #Delete only the temporary profile created by this dependency check.
    profile = Path(profile).resolve()
    if profile.parent != Path(tempfile.gettempdir()).resolve() or not profile.name.startswith('rpg-cdp-probe-'):
        print(f'Perchance probe cleanup warning: refusing unexpected profile path {profile}', file=sys.stderr)
        return
    for attempt in range(6):
        try:
            shutil.rmtree(profile)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            if attempt == 5:
                print(f'Perchance probe cleanup warning: temporary profile retained at {profile}: {exc}', file=sys.stderr)
            else:
                time.sleep(.1 * (attempt + 1))


def probe(executable):
    """Local dependency/CDP check only; no Perchance page or generation request."""
    from playwright.sync_api import sync_playwright
    profile = tempfile.mkdtemp(prefix='rpg-cdp-probe-')
    child = None
    try:
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0)); port = reservation.getsockname()[1]
        child = launch(executable, profile, port, 'about:blank', headless=True)
        address = wait_for_browser(port, lambda: False)
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(address, timeout=10000)
            try:
                #An attached Browser.close() disconnects Playwright. CDP closes
                #the owned probe browser, letting its children release files.
                browser.new_browser_cdp_session().send('Browser.close')
            except Exception as exc:
                print(f'Perchance probe shutdown warning: {exc}', file=sys.stderr)
    finally:
        _stop_probe_browser(child)
        _cleanup_probe_profile(profile)


class ControlledBrowserBackend(perchance.BrowserBackend):
    """Own only the browser process or new tabs created by this session."""
    def __init__(self, settings):
        settings = dict(settings)
        profile = Path(settings['perchance_profile'])
        if profile.name == 'perchance-profile':
            settings['perchance_profile'] = str(profile.with_name('perchance-controlled-profile'))
        super().__init__(settings)
        self.browser = self.child = None
        self._owns_browser = False
        self._owned_pages = []
        self._owner_marker = None

    def open(self):
        try:
            self._open()
        except BaseException:
            # Startup can fail before CDP attaches or before reset finishes.
            # Still reap our captured child, without touching an existing browser.
            self.close()
            raise

    def _open(self):
        from playwright.sync_api import sync_playwright
        self.profile = Path(self.settings['perchance_profile']).resolve()
        self.profile.mkdir(parents=True, exist_ok=True)
        port = self.settings.get('perchance_cdp_port', DEFAULT_PORT)
        address = endpoint(port)
        marker = self.profile / 'rpg-cdp-owner.json'
        owner = json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else None
        if listening(port):
            if not isinstance(owner, dict) or owner.get('port') != port or owner.get('profile') != str(self.profile):
                raise RuntimeError(f'Perchance CDP port {port} is already in use by another browser. Close that browser or choose another Perchance CDP port; RPG will not attach to it.')
        else:
            self.child = launch(perchance.browser_executable(self.settings), self.profile, port,
                                perchance.validate_url(self.settings.get('perchance_url', perchance.DEFAULT_URL)))
        wait_for_browser(port, lambda: self.cancel_requested)
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.connect_over_cdp(address, timeout=10000)
        if self.child is not None:
            # A port/profile marker alone is not ownership: it can be stale, and
            # Chrome may hand off a launch to an already-running profile. Never
            # send Browser.close unless CDP identifies our live Popen child.
            session = self.browser.new_browser_cdp_session()
            try:
                processes = session.send('SystemInfo.getProcessInfo')['processInfo']
            finally:
                session.detach()
            if self.child.poll() is not None or not any(
                    item.get('type') == 'browser' and item.get('id') == self.child.pid for item in processes):
                raise RuntimeError('Cannot verify ownership of the Perchance browser; existing windows were left untouched.')
            self._owns_browser = True
            self._owner_marker = {'port': port, 'profile': str(self.profile),
                                  'pid': self.child.pid, 'session': uuid.uuid4().hex}
            write_json(marker, self._owner_marker)
        if not self.browser.contexts:
            raise RuntimeError('Perchance controlled browser has no default context')
        self.context = self.browser.contexts[0]
        self.reset()

    def reset(self):
        url = perchance.validate_url(self.settings.get('perchance_url', perchance.DEFAULT_URL))
        if self.page is None or self.page.is_closed():
            # Reuse the launch page only in our own browser. When attaching to
            # an existing browser, a private tab makes timeout/cancel safe too.
            self.page = next((page for page in self.context.pages
                              if self._owns_browser and not page.is_closed()
                              and page.url.rstrip('/') == url.rstrip('/')), None)
            if self.page is None:
                self.page = self.context.new_page()
                self._owned_pages.append(self.page)
                self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            else:
                self._owned_pages.append(self.page)
        self.frame = None
        until = time.monotonic() + self.settings.get('perchance_ready_seconds', 90)
        while time.monotonic() < until:
            if self.cancel_requested:
                raise Cancelled('Stopped during Perchance startup')
            for frame in self.page.frames:
                try:
                    ready = frame.evaluate("() => typeof (globalThis.root?.aiTextPlugin || globalThis.root?.$moduleSpace?.['ai-text-plugin'] || globalThis.aiTextPlugin) === 'function'")
                    if not ready:
                        continue
                    frame.evaluate(perchance.WORKER.read_text(encoding='utf-8'))
                    self.frame = frame
                    self.environment = frame.evaluate('() => RpgPerchanceText.Environment()')
                    self.environment.update(browser_connection='normal-browser-cdp-v1',
                                            browser_visible=True, readiness_scope='plugin_availability_only',
                                            connection_code_hash=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest())
                    return
                except Exception as exc:
                    self.last_frame_error = str(exc)
            self.page.wait_for_timeout(100)
        if 'verification' in self.page.title().lower() or 'just a moment' in self.page.title().lower():
            raise RuntimeError('Perchance security verification blocked startup. Use Verify Perchance connection to reopen the host window and complete verification, then explicitly resume. No generation ran.')
        raise RuntimeError('Perchance page did not expose its text plugin in the controlled browser; check the host browser. Plugin availability does not verify generation.')

    def close(self):
        errors = []
        if self._owns_browser and self.browser is not None:
            try:
                # Playwright Browser.close on a CDP connection just detaches.
                # The protocol command closes this session's verified browser.
                self.browser.new_browser_cdp_session().send('Browser.close')
            except Exception:
                pass  # The captured child below is the bounded fallback.
        else:
            for page in self._owned_pages:
                try:
                    if not page.is_closed():
                        page.close()
                except Exception as exc:
                    errors.append(f'could not close a run-owned tab: {exc}')
        if self.child is not None:
            try:
                try:
                    self.child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.child.terminate()
                    try:
                        self.child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.child.kill()
                        self.child.wait(timeout=5)
                if self._owner_marker is not None:
                    marker = self.profile / 'rpg-cdp-owner.json'
                    if marker.exists() and json.loads(marker.read_text(encoding='utf-8')) == self._owner_marker:
                        marker.unlink()
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                errors.append(f'could not finish owned browser cleanup: {exc}')
        try:
            if self.playwright is not None:
                self.playwright.stop()
        except Exception as exc:
            errors.append(f'could not disconnect browser transport: {exc}')
        finally:
            self.context = self.page = self.frame = self.playwright = None
            self.browser = self.child = None
            self._owns_browser = False
            self._owned_pages = []
            self._owner_marker = None
        if errors:
            message = 'Perchance browser cleanup failed: ' + '; '.join(errors)
            if sys.exc_info()[0] is not None:
                print(message, file=sys.stderr)  # Preserve the original run/startup failure.
            else:
                raise RuntimeError(message)


def run(app, report, pending, **kwargs):
    try:
        return perchance.run(app, report, pending, backend_factory=ControlledBrowserBackend, **kwargs)
    finally:
        app.backend = None


def verify_connection(app):
    backend = ControlledBrowserBackend({**app.settings, 'perchance_profile': str(app.data / 'perchance-controlled-profile'),
                                        'perchance_ready_seconds': 180})
    app.backend = backend
    try:
        app.message = 'Opening normal Perchance browser on the host. Complete any site verification there.'
        backend.open()
        app.log('perchance_connection', canonical(backend.environment))
        app.message = 'Perchance text plugin is available in the controlled browser. No generation request was made; generation has not been verified.'
    finally:
        try:
            backend.close()
        finally:
            app.backend = None
