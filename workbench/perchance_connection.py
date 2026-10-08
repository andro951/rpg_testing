"""Normal browser/CDP lifecycle, separate from inference and observation identity."""
from __future__ import annotations
import json
import hashlib
import os
import socket
import subprocess
import tempfile
import time
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


def probe(executable):
    """Local dependency/CDP check only; no Perchance page or generation request."""
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory(prefix='rpg-cdp-probe-') as profile:
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0)); port = reservation.getsockname()[1]
        child = launch(executable, profile, port, 'about:blank', headless=True)
        try:
            address = wait_for_browser(port, lambda: False)
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(address, timeout=10000)
                browser.close()
        finally:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=10)


class ControlledBrowserBackend(perchance.BrowserBackend):
    """Inherited request serializer/worker; normal visible browser kept between runs."""
    def __init__(self, settings):
        settings = dict(settings)
        profile = Path(settings['perchance_profile'])
        if profile.name == 'perchance-profile':
            settings['perchance_profile'] = str(profile.with_name('perchance-controlled-profile'))
        super().__init__(settings)

    def open(self):
        from playwright.sync_api import sync_playwright
        self.profile = Path(self.settings['perchance_profile']).resolve()
        self.profile.mkdir(parents=True, exist_ok=True)
        port = self.settings.get('perchance_cdp_port', DEFAULT_PORT)
        address = endpoint(port)
        marker = self.profile / 'rpg-cdp-owner.json'
        owner = json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else None
        if listening(port):
            if owner != {'port': port, 'profile': str(self.profile)}:
                raise RuntimeError(f'Perchance CDP port {port} is already in use by another browser. Close that browser or choose another Perchance CDP port; RPG will not attach to it.')
        else:
            launch(perchance.browser_executable(self.settings), self.profile, port,
                   perchance.validate_url(self.settings.get('perchance_url', perchance.DEFAULT_URL)))
            write_json(marker, {'port': port, 'profile': str(self.profile)})
        wait_for_browser(port, lambda: self.cancel_requested)
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.connect_over_cdp(address, timeout=10000)
        if not self.browser.contexts:
            raise RuntimeError('Perchance controlled browser has no default context')
        self.context = self.browser.contexts[0]
        self.reset()

    def reset(self):
        url = perchance.validate_url(self.settings.get('perchance_url', perchance.DEFAULT_URL))
        self.page = next((page for page in self.context.pages if not page.is_closed() and page.url.rstrip('/') == url.rstrip('/')), None)
        if self.page is None:
            self.page = self.context.new_page()
            self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
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
            raise RuntimeError('Perchance security verification blocked startup. Complete verification in the browser on the host PC, then explicitly resume. No generation ran.')
        raise RuntimeError('Perchance page did not expose its text plugin in the controlled browser; check the host browser. Plugin availability does not verify generation.')

    def close(self):
        #Disconnect only. Cookies, the normal browser and its hosted page remain available.
        if self.playwright:
            self.playwright.stop()
        self.context = self.page = self.frame = self.playwright = None
        self.browser = None


def run(app, report, pending, **kwargs):
    return perchance.run(app, report, pending, backend_factory=ControlledBrowserBackend, **kwargs)


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
        backend.close(); app.backend = None
