"""Portable sessions and immutable checksummed evidence, separate from study rows."""
import copy
import json
import os
import threading
import uuid
import io
import zipfile
from pathlib import Path
from workbench.domain import digest, read_json, safe_id

LOCK = threading.RLock()


class Store:
    def __init__(self, root):
        self.root = Path(root) / 'optimization_results'

    def directory(self, session):
        return self.root / safe_id(session)

    def write(self, path, value):
        data = copy.deepcopy(value)
        data.pop('checksum', None)
        data['checksum'] = digest(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(temporary, path)

    def read(self, path):
        value = read_json(path)
        checksum = value.pop('checksum', None)
        if checksum != digest(value):
            raise ValueError('Optimization evidence checksum mismatch: ' + path.name)
        return value

    def save(self, session):
        with LOCK:
            self.write(self.directory(session['id']) / 'session.json', session)

    def load(self, session):
        with LOCK:
            return self.read(self.directory(session) / 'session.json')

    def list(self):
        with LOCK:
            return [self.read(p) for p in sorted(self.root.glob('*/session.json'))]

    def evidence(self, session, value):
        key = digest(value)
        path = self.directory(session) / 'evidence' / (key + '.json')
        with LOCK:
            if not path.exists():
                self.write(path, value)
            elif self.read(path) != value:
                raise ValueError('Conflicting immutable evidence')
        return key

    def get_evidence(self, session, key):
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('Invalid evidence identity')
        return self.read(self.directory(session) / 'evidence' / (key + '.json'))

    def observations(self, session):
        return [self.get_evidence(session['id'], key) for key in session.get('observations', [])]

    def export(self, session_id):
        session = self.load(session_id)
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('session.json', (self.directory(session_id) / 'session.json').read_bytes())
            for path in sorted((self.directory(session_id) / 'evidence').glob('*.json')):
                self.read(path)
                archive.writestr('evidence/' + path.name, path.read_bytes())
        return output.getvalue()

    def import_archive(self, data):
        """Validate completely before touching storage; merge evidence, never overwrite."""
        files = {}
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if len(archive.infolist()) > 10000 or sum(p.file_size for p in archive.infolist()) > 512 * 1024**2:
                raise ValueError('Session archive is too large.')
            for item in archive.infolist():
                name = item.filename
                allowed = name == 'session.json' or (name.startswith('evidence/') and len(name) == len('evidence/') + 69
                          and name.endswith('.json') and all(c in '0123456789abcdef' for c in name[9:-5]))
                if not allowed or name in files:
                    raise ValueError('Invalid or duplicate archive member')
                value = json.loads(archive.read(item))
                checksum = value.pop('checksum', None)
                if checksum != digest(value) or (name != 'session.json' and name[9:-5] != digest(value)):
                    raise ValueError('Invalid archive evidence checksum')
                files[name] = value
        session = files.get('session.json')
        if not session or session.get('schema_version') != 1:
            raise ValueError('Missing or unsupported session manifest')
        directory = self.directory(session['id'])
        for key in session.get('observations', []) + [a[field] for a in session.get('attempts', [])
                                                     for field in ('request_evidence', 'response_evidence', 'error_evidence') if field in a]:
            if 'evidence/' + key + '.json' not in files:
                raise ValueError('Archive is missing referenced evidence')
        with LOCK:
            if (directory / 'session.json').exists():
                existing = self.load(session['id'])
                # Independent hosts may add observations. The same proposal must
                # retain its number and generation provenance on both machines.
                fixed = ('scope', 'definition', 'settings', 'generator_id', 'origin_model_id', 'optimizer_system', 'optimizer_user')
                if any(existing[k] != session[k] for k in fixed):
                    raise ValueError('Session contracts conflict; nothing was overwritten.')
                attempts = {a['number']: a for a in existing['attempts']}
                for attempt in session['attempts']:
                    previous = attempts.get(attempt['number'])
                    if previous and any(previous.get(k) != attempt.get(k) for k in ('request_evidence', 'candidate', 'response_evidence')):
                        raise ValueError('Conflicting generation attempt')
                    if not previous:
                        attempts[attempt['number']] = attempt
                existing['attempts'] = sorted(attempts.values(), key=lambda a: a['number'])
                existing['observations'] = list(dict.fromkeys(existing['observations'] + session['observations']))
                session = existing
            for name, value in files.items():
                if name != 'session.json':
                    path = directory / name
                    if path.exists() and self.read(path) != value:
                        raise ValueError('Conflicting immutable evidence')
            for name, value in files.items():
                if name != 'session.json' and not (directory / name).exists():
                    self.write(directory / name, value)
            self.save(session)
        return session['id']
