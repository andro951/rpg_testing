"""Loopback results viewer with persistent, manual test judgements."""
import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from urllib.request import urlopen
import webbrowser
from workbench.domain import canonical, ResultStore
from workbench.judgements import JudgementStore, annotate
from .report import write_report

MARKER = '<script type="application/json" id="evidence-data">'


class ReviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, root, snapshot):
        super().__init__(address, ReviewHandler)
        self.root = Path(root).resolve()
        self.snapshot = copy.deepcopy(snapshot)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.snapshot_path = self.root / '.local' / 'reports' / 'statistics.html'
        self.snapshot_stamp = self.snapshot_path.stat().st_mtime_ns if self.snapshot_path.exists() else None

    def refresh(self):
        """Pick up a newly generated report when the BAT reuses this viewer."""
        with self.lock:
            if self.snapshot_path.exists():
                stamp = self.snapshot_path.stat().st_mtime_ns
                if stamp != self.snapshot_stamp:
                    html = self.snapshot_path.read_text(encoding='utf-8')
                    snapshot = json.loads(html.split(MARKER, 1)[1].split('</script>', 1)[0])
                    self.snapshot = snapshot
                    self.snapshot_stamp = stamp

    def rendered(self):
        with self.lock:
            self.refresh()
            annotate(self.snapshot['matrix'], JudgementStore(self.root).read())
            report = copy.deepcopy(self.snapshot)
            report['judgement_api'] = {'url': '/api/judgements', 'token': self.token}
            for cid, summary in report['matrix']['records'].items():
                summary['source_uri'] = '/evidence/' + cid
            scripts = '\n'.join(Path(__file__).with_name(name).read_text(encoding='utf-8') for name in
                                ('groupings.js', 'judgements.js', 'matrix.js', 'report.js'))
            data = canonical(report).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
            return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RPG testing results</title><body>' +
                    MARKER + data + '</script><script>' + scripts + '</script></body></html>').encode('utf-8')


class ReviewHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def reply(self, status, data, content_type='application/json; charset=utf-8'):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        port = self.server.server_port
        return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

    def do_GET(self):
        if not self.valid_host():
            self.reply(403, {'error': 'Invalid local host'})
            return
        try:
            if self.path == '/':
                self.reply(200, self.server.rendered(), 'text/html; charset=utf-8')
            elif self.path == '/identity':
                self.reply(200, {'application': 'rpg-test-review-v1', 'root': str(self.server.root)})
            elif self.path.startswith('/evidence/'):
                self.server.refresh()
                cid = self.path.removeprefix('/evidence/')
                summary = self.server.snapshot['matrix']['records'].get(cid)
                if summary is None:
                    self.reply(404, {'error': 'Unknown result'})
                    return
                path = ResultStore(self.server.root / 'results').path(summary['metadata']['model_id'], cid)
                self.reply(200, path.read_bytes())
            else:
                self.reply(404, {'error': 'Not found'})
        except (ValueError, OSError) as exc:
            self.reply(500, {'error': str(exc)})

    def do_POST(self):
        origin = self.headers.get('Origin')
        expected = f'http://{self.headers.get("Host")}'
        if not self.valid_host() or self.headers.get('X-Judgement-Token') != self.server.token or (origin and origin != expected):
            self.reply(403, {'error': 'Invalid review authorization'})
            return
        if self.path != '/api/judgements':
            self.reply(404, {'error': 'Not found'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 100000:
                raise ValueError('Invalid request size')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or set(payload) != {'ids', 'status', 'reason', 'reviewer', 'note'}:
                raise ValueError('Invalid judgement request')
            with self.server.lock:
                self.server.refresh()
                known = {row['definition_id'] for row in self.server.snapshot['matrix']['rows']}
                if not isinstance(payload['ids'], list) or any(not isinstance(key, str) or key not in known for key in payload['ids']):
                    raise ValueError('Unknown test definition')
                data = JudgementStore(self.server.root).update(**payload)
                annotate(self.server.snapshot['matrix'], data)
                write_report(self.server.snapshot, self.server.root / '.local' / 'reports' / 'statistics.html')
                self.server.snapshot_stamp = self.server.snapshot_path.stat().st_mtime_ns
                response = {key: data['entries'][key] for key in payload['ids']}
            self.reply(200, {'entries': response})
        except (ValueError, TypeError) as exc:
            self.reply(409, {'error': str(exc)})
        except OSError as exc:
            self.reply(500, {'error': str(exc)})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8876)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    root = Path.cwd().resolve()
    url = f'http://127.0.0.1:{args.port}/'
    try:
        with urlopen(url + 'identity', timeout=2) as response:
            identity = json.load(response)
        if identity != {'application': 'rpg-test-review-v1', 'root': str(root)}:
            raise ValueError('The results-viewer port belongs to another application')
    except OSError:
        identity = None
    if identity:
        if not args.no_browser:
            webbrowser.open(url)
        return
    html = (root / '.local' / 'reports' / 'statistics.html').read_text(encoding='utf-8')
    snapshot = json.loads(html.split(MARKER, 1)[1].split('</script>', 1)[0])
    with ReviewServer(('127.0.0.1', args.port), root, snapshot) as server:
        print(f'Results viewer: {url}\nKeep this window open while reviewing tests.', flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
