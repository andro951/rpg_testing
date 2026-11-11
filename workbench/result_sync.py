"""Run-scoped result commits. No source edits, broad staging, merges or force pushes.

Only ResultStore.save calls made inside a Controller.run are enrolled. Receipts
are local, durable and contain exact content hashes, never credentials or logs.
"""
from __future__ import annotations
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from .domain import ResultStore, read_json, write_json
from .locking import HostLock

GIT_TIMEOUT = 45


def git(root, *args, check=True, binary=False):
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                            timeout=GIT_TIMEOUT, env=env, **flags)
    if check and result.returncode:
        # Remote/hook stderr can contain credential-bearing URLs. Keep it local
        # to Git rather than copying it into the receipt or public result JSON.
        raise RuntimeError('Git ' + args[0] + ' failed (exit ' + str(result.returncode) +
                           '). Check Git authentication, remote access and branch divergence.')
    return result.stdout if binary else result.stdout.decode('utf-8', 'replace').strip()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _files(root, *args):
    return set(git(root, *args, binary=True).decode('utf-8').rstrip('\0').split('\0')) - {''}


class ResultSync:
    def __init__(self, root, secrets=()):
        self.root = Path(root).resolve()
        self.directory = self.root / '.local/workbench/result-sync'
        self.secrets = tuple(s for s in secrets if isinstance(s, str) and s)

    def _path(self, name):
        if not re.fullmatch(r'results/[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}/[0-9a-f]{64}\.json', name):
            raise RuntimeError('Only exact benchmark result JSON paths may be synchronized.')
        path = self.root / name
        if path.resolve() != path.absolute() or any(p.is_symlink() for p in (path, *path.parents)):
            raise RuntimeError('Symlinked result paths cannot be synchronized.')
        return path

    def _validate(self, name, expected=None):
        path = self._path(name)
        data = path.read_bytes()
        if expected and sha(data) != expected:
            raise RuntimeError('A saved result changed after this run: ' + name)
        record = ResultStore(self.root / 'results').read(path)
        if record.get('simulated'):
            raise RuntimeError('Simulated results are not published automatically.')
        if any(secret.encode('utf-8') in data for secret in self.secrets):
            raise RuntimeError('A result contains a configured credential; publication blocked.')
        return sha(data)

    def begin(self):
        batch = {'version': 1, 'id': uuid.uuid4().hex, 'created_ns': time.time_ns(), 'status': 'recording',
                 'files': {}, 'blocked': {}, 'commit': None, 'error': None}
        try:
            top = Path(git(self.root, 'rev-parse', '--show-toplevel')).resolve()
            if top != self.root:
                raise RuntimeError('This run uses an isolated directory, not its own Git checkout.')
            batch['branch'] = git(self.root, 'symbolic-ref', '--quiet', '--short', 'HEAD')
            batch['base'] = git(self.root, 'rev-parse', 'HEAD')
            destination = git(self.root, 'remote', 'get-url', '--push', '--all', 'origin')
            source = git(self.root, 'remote', 'get-url', '--all', 'origin')
            if destination != source or len(destination.splitlines()) != 1:
                raise RuntimeError('Automatic result sync requires one matching origin fetch/push destination.')
            batch['origin_sha256'] = sha(destination.encode('utf-8'))
            batch['dirty'] = sorted(_files(self.root, 'diff', '--name-only', '-z') |
                                    _files(self.root, 'diff', '--cached', '--name-only', '-z') |
                                    _files(self.root, 'ls-files', '--others', '--exclude-standard', '-z'))
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            batch['setup_error'] = str(exc)
        return batch

    def save_receipt(self, batch):
        write_json(self.directory / (batch['id'] + '.json'), batch)

    def before_save(self, batch, path):
        name = Path(path).absolute().relative_to(self.root).as_posix()
        self._path(name)
        if name in batch.get('dirty', []):
            batch['blocked'][name] = 'The result path already had local or staged edits before this run.'
        # Write intent first. A crash between the atomic result write and the
        # hash receipt leaves this path explicitly uncertain, never swept in.
        batch['files'][name] = {'sha256': None}
        self.save_receipt(batch)
        return name

    def after_save(self, batch, name):
        batch['files'][name] = {'sha256': self._validate(name)}
        self.save_receipt(batch)

    def _recover_commit(self, batch):
        if batch.get('commit'):
            return batch['commit']
        if not batch.get('commit_base'):
            return None
        marker = 'Workbench-Run: ' + batch['id']
        commits = git(self.root, 'log', '--format=%H', '--fixed-strings', '--grep=' + marker,
                      'refs/heads/' + batch['branch']).splitlines()
        for commit in commits:
            if git(self.root, 'show', '-s', '--format=%P', commit) == batch['commit_base']:
                batch['commit'] = commit
                self.save_receipt(batch)
                return commit
        return None

    def _check_commit(self, batch, commit):
        changed = _files(self.root, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', commit)
        if changed != set(batch['commit_files']):
            raise RuntimeError('Result commit contains unexpected paths; automatic push blocked.')
        for name in changed:
            # Git may normalize line endings according to the repository policy.
            blob = git(self.root, 'rev-parse', commit + ':' + name)
            if blob != batch['files'][name]['git_oid']:
                raise RuntimeError('Result commit differs from its saved receipt; automatic push blocked.')

    def _flush(self, batch):
        if batch.get('setup_error'):
            raise RuntimeError(batch['setup_error'])
        destination = git(self.root, 'remote', 'get-url', '--push', '--all', 'origin')
        source = git(self.root, 'remote', 'get-url', '--all', 'origin')
        if destination != source or sha(destination.encode('utf-8')) != batch['origin_sha256']:
            raise RuntimeError('The origin push destination changed; review this receipt before publishing.')
        if batch.get('recording_error'):
            raise RuntimeError(batch['recording_error'])
        if git(self.root, 'symbolic-ref', '--quiet', '--short', 'HEAD') != batch['branch']:
            raise RuntimeError('The checkout branch changed. Return to ' + batch['branch'] + ' to retry.')
        if _files(self.root, 'diff', '--name-only', '--diff-filter=U', '-z'):
            raise RuntimeError('Resolve the existing Git conflicts before retrying result synchronization.')
        # Refuse commit operations during merge/rebase/cherry-pick, even if all
        # conflicts happen to have been staged already.
        for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply'):
            git_path = Path(git(self.root, 'rev-parse', '--git-path', name))
            if not git_path.is_absolute():git_path = self.root / git_path
            if git_path.exists():raise RuntimeError('A Git integration operation is active; retry after it finishes.')
        commit = self._recover_commit(batch)
        if not commit:
            if batch['blocked']:
                raise RuntimeError(next(iter(batch['blocked'].values())))
            staged = _files(self.root, 'diff', '--cached', '--name-only', '-z')
            changed = []
            for name, entry in batch['files'].items():
                if not entry.get('sha256'):
                    raise RuntimeError('Interrupted result save needs review or resume: ' + name)
                self._validate(name, entry['sha256'])
                data = self._path(name).read_bytes().replace(b'\r\n', b'\n')
                entry['git_sha256'] = sha(data)
                entry['git_oid'] = git(self.root, 'hash-object', '--path=' + name, str(self._path(name)))
                if name in staged:
                    if not entry.get('stage_intent') or git(self.root, 'rev-parse', ':' + name) != entry['git_oid']:
                        raise RuntimeError('A run result has other staged changes: ' + name)
                tracked = git(self.root, 'ls-files', '--error-unmatch', '--', name, check=False)
                previous = git(self.root, 'show', 'HEAD:' + name, check=False, binary=True) if tracked else None
                if previous is None or previous.replace(b'\r\n', b'\n') != data:
                    changed.append(name)
            if not changed:
                batch.update(status='noop', error=None)
                self.save_receipt(batch)
                return
            head = git(self.root, 'rev-parse', 'HEAD')
            remote = git(self.root, 'ls-remote', '--exit-code', 'origin', 'refs/heads/' + batch['branch']).split()[0]
            if remote != head:
                raise RuntimeError('The local and origin branch differ. Reconcile them before retrying; no automatic merge or unrelated push was attempted.')
            batch['commit_base'] = head
            batch['commit_files'] = changed
            for name in changed:batch['files'][name]['stage_intent'] = True
            self.save_receipt(batch)
            # NUL pathspec input avoids argument limits for full model batches.
            spec = self.directory / (batch['id'] + '.paths')
            spec.write_bytes(b''.join(name.encode('utf-8') + b'\0' for name in changed))
            try:
                git(self.root, '--literal-pathspecs', 'add', '--pathspec-from-file=' + str(spec), '--pathspec-file-nul')
                # Recheck content after staging, before committing, and check the
                # committed blobs again before sending anything to the remote.
                for name in changed:self._validate(name, batch['files'][name]['sha256'])
                git(self.root, '--literal-pathspecs', '-c', 'user.name=RPG Workbench', '-c',
                    'user.email=workbench@localhost', 'commit', '--only',
                    '--pathspec-from-file=' + str(spec), '--pathspec-file-nul',
                    '-m', 'results: save model run ' + batch['id'][:8],
                    '-m', 'Workbench-Run: ' + batch['id'])
            finally:
                spec.unlink(missing_ok=True)
            commit = self._recover_commit(batch)
            if not commit:raise RuntimeError('The result commit outcome is uncertain; retry to reconcile it.')
        self._check_commit(batch, commit)
        # If a previous push succeeded but its response was lost, an observed
        # remote descendant is also proof that this exact commit is published.
        remote = git(self.root, 'ls-remote', '--exit-code', 'origin', 'refs/heads/' + batch['branch']).split()[0]
        if remote != commit and git(self.root, 'cat-file', '-t', remote, check=False) != 'commit':
            # Fetch objects only; never integrate or alter the checked-out branch.
            git(self.root, 'fetch', '--no-tags', '--no-write-fetch-head', 'origin', 'refs/heads/' + batch['branch'])
        if remote == commit or git(self.root, 'merge-base', commit, remote, check=False) == commit:
            batch.update(status='synced', error=None)
            self.save_receipt(batch)
            return
        batch.update(status='push_pending', error=None)
        self.save_receipt(batch)
        git(self.root, 'push', 'origin', commit + ':refs/heads/' + batch['branch'])
        # A nonzero/timeout after a successful push is safely retried with the
        # same immutable commit. Never recommit or push unrelated newer HEAD.
        remote = git(self.root, 'ls-remote', '--exit-code', 'origin', 'refs/heads/' + batch['branch']).split()[0]
        if remote != commit:
            raise RuntimeError('Remote verification did not match the result commit; retry or inspect origin.')
        batch.update(status='synced', error=None)
        self.save_receipt(batch)

    def retry(self):
        summary = {'status': 'idle', 'pending': 0, 'synced': 0, 'message': 'No pending result synchronization.'}
        if not self.directory.exists():return summary
        try:
            with HostLock(self.directory / 'sync.lock'):
                batches = [read_json(p) for p in self.directory.glob('*.json')]
                for batch in sorted(batches, key=lambda b: b.get('created_ns', 0)):
                    if batch.get('status') in ('synced', 'noop') or not (batch.get('files') or batch.get('recording_error')):continue
                    try:self._flush(batch)
                    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                        batch.update(status='pending', error=str(exc))
                        self.save_receipt(batch)
                        summary.update(status='pending', message='Results are saved locally. Git sync pending: ' + str(exc))
                        # One failed batch per attempt, no polling or unbounded retries.
                        break
                    summary['synced'] += batch['status'] == 'synced'
                receipts = [read_json(p) for p in self.directory.glob('*.json')]
                summary['pending'] = sum(b.get('status') not in ('synced', 'noop') and bool(b.get('files') or b.get('recording_error')) for b in receipts)
                if not summary['pending']:
                    summary.update(status='synced' if summary['synced'] else 'idle',
                                   message='Result commits verified on origin.' if summary['synced'] else 'No pending result synchronization.')
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            summary.update(status='pending', pending=1, message='Result sync needs attention: ' + str(exc))
        return summary

    def status(self):
        if not self.directory.exists():return {'status': 'idle', 'pending': 0, 'message': 'Results sync automatically after each run.'}
        try:
            receipts = [read_json(p) for p in self.directory.glob('*.json')]
            pending = [b for b in receipts if b.get('status') not in ('synced', 'noop') and (b.get('files') or b.get('recording_error'))]
            return {'status': 'pending' if pending else 'idle', 'pending': len(pending),
                    'message': ('Saved results await Git sync. ' + (pending[0].get('error') or 'Retry when this run ends.')) if pending else 'No pending result synchronization.'}
        except (OSError, ValueError) as exc:
            return {'status': 'pending', 'pending': 1, 'message': 'Result sync receipt needs review: ' + str(exc)}


class RecordingStore:
    def __init__(self, store, sync, batch):
        self.store, self.sync, self.batch = store, sync, batch

    def __getattr__(self, name):
        return getattr(self.store, name)

    def save(self, record):
        name = self.store.path(record['model_id'], record['case_id']).absolute().relative_to(self.sync.root).as_posix()
        try:self.sync.before_save(self.batch, self.store.path(record['model_id'], record['case_id']))
        except (OSError, ValueError, RuntimeError):pass
        # Git/journal trouble must never discard a finished model response.
        path = self.store.save(record)
        try:self.sync.after_save(self.batch, name)
        except (OSError, ValueError, RuntimeError) as exc:
            self.batch['recording_error'] = 'Saved result could not be safely enrolled for Git sync: ' + str(exc)
            try:self.sync.save_receipt(self.batch)
            except OSError:pass
        return path


def sync_run(function):
    @functools.wraps(function)
    def wrapped(app, *args, **kwargs):
        if app.demo:return function(app, *args, **kwargs)
        sync = app.result_sync
        app.retry_result_sync()
        batch = sync.begin()
        original = app.store
        app.store = RecordingStore(original, sync, batch)
        app.result_sync_active = True
        try:
            return function(app, *args, **kwargs)
        finally:
            app.store = original
            app.result_sync_active = False
            if batch['files'] or batch.get('recording_error'):
                batch['status'] = 'pending'
                try:sync.save_receipt(batch)
                except OSError as exc:batch['recording_error'] = 'Results are saved locally, but the Git retry receipt could not be written: ' + str(exc)
            app.retry_result_sync()
            if batch.get('recording_error'):
                app.result_sync_status = {'status':'pending', 'pending':1, 'message':batch['recording_error']}
                app.log('result_sync_pending',batch['recording_error'])
                print('RESULT SYNC PENDING: '+batch['recording_error'],flush=True)
    return wrapped


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Retry exact run-result commits without running models.')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    settings_path = args.root / '.local/workbench/settings.json'
    settings = read_json(settings_path) if settings_path.exists() else {}
    result = ResultSync(args.root, (settings.get('hf_token'), settings.get('model_api_token'))).retry()
    print(json.dumps(result, indent=2))
    return 2 if result['status'] == 'pending' else 0


if __name__ == '__main__':
    sys.exit(main())
