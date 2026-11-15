"""Read-only audit of the intentional template/evaluator migration.

This audit does not claim source or scoring equivalence. The pinned baseline
object must already exist locally. It never fetches, runs inference, changes
files, or rewrites historical evidence. Checkout CRLF differences are normalized.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

# Importing the current compiler must not create repository bytecode files.
sys.dont_write_bytecode = True

BASELINE = 'a64cc029837a33d4b67a6a8e4b5d686497ef943c'
PRESERVED = ('test_specs/', 'prompts/patch-suite/', 'prompt-review/')
EVIDENCE = ('results/', 'coverage_results/', 'optimization_results/')
EXPERIMENT_DATA = {'.json', '.txt', '.jsonl', '.csv'}
# Only this reviewed relocation is recognized; never search arbitrary archives.
RESULT_ARCHIVE = 'archives/desktop-results-before-2026-11-11'
RESULT_ARCHIVE_SOURCE = 'fd73a328fb89e0398d6d9c940f05ee8f44f648ec'
SUITE_ARCHIVE = 'archives/suite-before-240-2026-11-15'
SUITE_ARCHIVE_SOURCE = 'f78bdf518398b9f75091194d258bc7c5cc5d38fa'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def checkout_content(raw):
    return raw if b'\0' in raw else raw.replace(b'\r\n', b'\n')


def blob_id(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def git_tree(root, baseline):
    paths = [p.rstrip('/') for p in (*PRESERVED, *EVIDENCE, 'experiments/')]
    result = subprocess.run(['git', '-C', str(root), 'ls-tree', '-r', '-z', baseline, '--', *paths],
                            capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf8', 'replace').strip())
    entries = {}
    for row in result.stdout.split(b'\0'):
        if not row:
            continue
        metadata, name = row.split(b'\t', 1)
        mode, kind, oid = metadata.decode('ascii').split()
        name = name.decode('utf8')
        require(kind == 'blob' and mode in ('100644', '100755'), 'Unexpected baseline file type: ' + name)
        entries[name] = oid
    return entries


class GitObjects:
    """Read many baseline blobs using one local Git process, never one per file."""
    def __init__(self, root):
        self.root = root

    def __enter__(self):
        self.process = subprocess.Popen(['git', '-C', str(self.root), 'cat-file', '--batch'],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return self

    def read(self, oid):
        self.process.stdin.write(oid.encode('ascii') + b'\n')
        self.process.stdin.flush()
        header = self.process.stdout.readline().decode('ascii').strip().split()
        require(len(header) == 3 and header[1] == 'blob', 'Baseline blob unavailable: ' + oid)
        size = int(header[2])
        raw = self.process.stdout.read(size)
        require(len(raw) == size and self.process.stdout.read(1) == b'\n', 'Truncated baseline blob: ' + oid)
        return raw

    def __exit__(self, kind, value, traceback):
        self.process.stdin.close()
        self.process.stdout.close()
        error = self.process.stderr.read()
        self.process.stderr.close()
        code = self.process.wait(timeout=30)
        if code and kind is None:
            raise RuntimeError(error.decode('utf8', 'replace').strip())


def regular_file(root, name):
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe file path: ' + name)
    path = root.joinpath(*relative.parts)
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
            'Missing or unsafe file: ' + name)
    return path


def immutable(name):
    return name.startswith(EVIDENCE) or (name.startswith('experiments/') and PurePosixPath(name).suffix in EXPERIMENT_DATA)


def result_relocations(root, entries):
    """Read the reviewed relocation manifest without trusting it as evidence."""
    directory = root / RESULT_ARCHIVE
    if not directory.exists() and not directory.is_symlink():
        return {}
    manifest = json.loads(regular_file(root, RESULT_ARCHIVE + '/manifest.json').read_text(encoding='utf8'))
    require(isinstance(manifest, dict) and manifest.get('source_commit') == RESULT_ARCHIVE_SOURCE,
            'Unexpected result archive source commit')
    files = manifest.get('files')
    require(isinstance(files, list) and bool(files), 'Result archive manifest has no files')
    relocations = {}
    for entry in files:
        require(isinstance(entry, dict) and set(entry) == {'original_path', 'git_blob', 'sha256', 'bytes'},
                'Invalid result archive manifest entry')
        name = entry['original_path']
        require(isinstance(name, str) and name.startswith('results/') and name in entries,
                'Result archive path is not pinned baseline evidence: ' + str(name))
        require(name not in relocations, 'Duplicate result archive path: ' + name)
        require(entry['git_blob'] == entries[name], 'Result archive blob differs from pinned baseline: ' + name)
        require(isinstance(entry['sha256'], str) and bool(re.fullmatch('[0-9a-f]{64}', entry['sha256'])),
                'Invalid result archive SHA-256: ' + name)
        require(type(entry['bytes']) is int and entry['bytes'] >= 0, 'Invalid result archive byte count: ' + name)
        relocations[name] = entry
    return relocations


def verify_result_relocation(root, name, entry):
    # Archives have -text attributes: not even CRLF normalization is permitted.
    raw = regular_file(root, RESULT_ARCHIVE + '/' + name).read_bytes()
    require(len(raw) == entry['bytes'], 'Archived result byte count changed: ' + name)
    require(hashlib.sha256(raw).hexdigest() == entry['sha256'], 'Archived result SHA-256 changed: ' + name)
    require(blob_id(raw) == entry['git_blob'], 'Archived result differs from pinned baseline bytes: ' + name)


def suite_relocations(root, entries):
    """Recognize only the reviewed 21-to-240 archive, never arbitrary snapshots.

    Its full manifest also lists templates/configuration and newer evidence.
    Those entries are validated for shape/path/duplicates but cannot authorize
    relocating anything outside pinned-baseline EVIDENCE paths.
    """
    directory = root / SUITE_ARCHIVE
    if not directory.exists() and not directory.is_symlink():
        return {}
    manifest_path = strict_archive_file(root, SUITE_ARCHIVE + '/manifest.json')
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    require(isinstance(manifest, dict) and manifest.get('source_commit') == SUITE_ARCHIVE_SOURCE,
            'Unexpected suite archive source commit')
    files = manifest.get('files')
    require(isinstance(files, list) and bool(files), 'Suite archive manifest has no files')
    seen = set()
    relocations = {}
    for entry in files:
        require(isinstance(entry, dict) and set(entry) == {'path', 'sha256', 'bytes'},
                'Invalid suite archive manifest entry')
        name = entry['path']
        require(isinstance(name, str) and bool(name) and '\\' not in name and ':' not in name,
                'Unsafe suite archive path: ' + str(name))
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and '..' not in relative.parts
                and relative.as_posix() == name and name != '.',
                'Unsafe suite archive path: ' + name)
        require(name not in seen, 'Duplicate suite archive path: ' + name)
        seen.add(name)
        require(isinstance(entry['sha256'], str) and bool(re.fullmatch('[0-9a-f]{64}', entry['sha256'])),
                'Invalid suite archive SHA-256: ' + name)
        require(type(entry['bytes']) is int and entry['bytes'] >= 0,
                'Invalid suite archive byte count: ' + name)
        if name.startswith(EVIDENCE) and name in entries:
            relocations[name] = {**entry, 'git_blob': entries[name]}
    return relocations


def strict_archive_file(root, name):
    path = regular_file(root, name)
    current = root
    for part in PurePosixPath(name).parts:
        current = current / part
        require(not current.is_symlink(), 'Missing or unsafe file: ' + name)
    return path


def verify_suite_relocation(root, name, entry):
    raw = strict_archive_file(root, SUITE_ARCHIVE + '/' + name).read_bytes()
    require(len(raw) == entry['bytes'], 'Archived suite evidence byte count changed: ' + name)
    require(hashlib.sha256(raw).hexdigest() == entry['sha256'], 'Archived suite evidence SHA-256 changed: ' + name)
    # Manifest metadata cannot certify changed data or normalize line endings.
    require(blob_id(raw) == entry['git_blob'], 'Archived suite evidence differs from pinned baseline bytes: ' + name)


def expected_definitions(root):
    # Compilation is pure and checks reference data without executing a model.
    sys.path.insert(0, str(root))
    from prompt_builder.builder import applicable, compile_test, load_case
    templates = root / 'prompt_builder/templates'
    from prompt_builder.coverage import resolve
    selection, _ = resolve(templates)
    expected = {}
    for name in selection['test_cases']:
        case = load_case(name, templates)
        for output_format in selection['output_formats']:
            reason = applicable(case, output_format, templates)
            require(not reason, 'Unsupported required case/output: ' + name + '/' + output_format + ': ' + str(reason))
            test = compile_test(case, output_format, input_formats=selection['input_formats'],
                                root=templates, promotion_root=root)
            require(test['id'] not in expected, 'Duplicate compiled ID: ' + test['id'])
            expected[test['id']] = test
    require(bool(expected), 'No current definitions selected')
    return expected


def verify_current(root, old_ids):
    require(not (root / 'test_builder').exists(), 'Obsolete test_builder package still exists')
    cases = root / 'prompt_builder/templates/test_cases'
    require(cases.is_dir(), 'Current template cases are missing')
    for path in cases.rglob('*'):
        require(not (path.is_file() and 'schema' in path.name.lower()),
                'Per-case schema file exists: ' + path.relative_to(root).as_posix())
    expected = expected_definitions(root)
    current = {}
    for path in sorted((root / 'test_specs').glob('*.json')):
        test = json.loads(regular_file(root, path.relative_to(root).as_posix()).read_text(encoding='utf8'))
        require(test['id'] not in current, 'Duplicate active ID: ' + test['id'])
        require(path.stem == test['id'], 'Active filename differs from its ID: ' + path.name)
        require('state_schema' not in test, 'Current definition contains a case schema: ' + test['id'])
        for variant in test['variants']:
            require('response_schema' not in variant.get('result', {}), 'Current result contains a response schema: ' + test['id'])
        current[test['id']] = test
    require(set(current).isdisjoint(old_ids), 'Current IDs overlap the historical root suite')
    require(set(current) == set(expected), 'Active definition IDs differ from the selected template build')
    for identity, test in current.items():
        require(test == expected[identity], 'Active definition differs from freshly compiled templates/evaluator: ' + identity)
    catalog = json.loads((root / 'evaluation/catalog.json').read_text(encoding='utf8'))
    seen = set()
    active = set()
    for entry in catalog['definitions']:
        require(entry['id'] not in seen, 'Duplicate catalog ID: ' + entry['id'])
        seen.add(entry['id'])
        path = regular_file(root, entry['path'])
        raw = path.read_bytes()
        definition = json.loads(raw)
        require(definition['id'] == entry['id'], 'Catalog points to a different definition: ' + entry['path'])
        require(entry['source_sha256'] in {hashlib.sha256(raw).hexdigest(), hashlib.sha256(checkout_content(raw)).hexdigest()},
                'Catalog source hash is stale: ' + entry['path'])
        require(entry['variants'] == [v['id'] for v in definition['variants']], 'Catalog variants differ: ' + entry['path'])
        if entry['scope'] == 'active':
            require(entry['path'] == 'test_specs/' + entry['id'] + '.json', 'Active catalog path is not current: ' + entry['path'])
            active.add(entry['id'])
    require(active == set(current), 'Catalog active coverage differs from current definitions')
    return {'active_definitions_checked': len(current), 'catalog_pointers_checked': len(seen)}


def audit(root, baseline=BASELINE):
    root = Path(root).resolve()
    require(bool(re.fullmatch('[0-9a-f]{40}', baseline)), 'Baseline must be a complete commit SHA')
    entries = git_tree(root, baseline)
    relocations = result_relocations(root, entries)
    suite_moved = suite_relocations(root, entries)
    require(not set(relocations).intersection(suite_moved), 'Duplicate evidence relocation across reviewed archives')
    relocated_names = set(relocations) | set(suite_moved)
    preserved = {prefix: 0 for prefix in PRESERVED}
    immutable_count = 0
    old_ids = set()
    with GitObjects(root) as objects:
        for name, oid in entries.items():
            prefix = next((prefix for prefix in PRESERVED if name.startswith(prefix)), None)
            if prefix:
                before = objects.read(oid)
                archived = regular_file(root, 'archives/pre-template-builder/' + name).read_bytes()
                require(checkout_content(before) == checkout_content(archived), 'Archived baseline bytes changed: ' + name)
                preserved[prefix] += 1
                if name.startswith('test_specs/') and PurePosixPath(name).suffix == '.json':
                    old_ids.add(json.loads(before)['id'])
            elif immutable(name):
                if name in relocations:
                    verify_result_relocation(root, name, relocations[name])
                if name in suite_moved:
                    verify_suite_relocation(root, name, suite_moved[name])
                original = root / name
                if name in suite_moved:
                    parts = PurePosixPath(name).parts
                    require(not any(root.joinpath(*parts[:i]).is_symlink() for i in range(1, len(parts)+1)),
                            'Missing or unsafe file: ' + name)
                # An archive never conceals changed or unsafe evidence still at its original path.
                if name not in relocated_names or original.exists() or original.is_symlink():
                    raw = regular_file(root, name).read_bytes()
                    # The common path needs no baseline blob transfer at all.
                    if oid not in {blob_id(raw), blob_id(checkout_content(raw))}:
                        require(checkout_content(raw) == checkout_content(objects.read(oid)), 'Immutable evidence changed: ' + name)
                immutable_count += 1
    require(all(preserved.values()), 'Pinned baseline does not contain every required root archive')
    require(immutable_count > 0, 'Pinned baseline has no saved evidence to audit')
    current = verify_current(root, old_ids)
    return {'baseline': baseline, 'intentional_suite_and_evaluator_migration': True,
            'archived_files_checked': preserved, 'immutable_evidence_files_checked': immutable_count,
            'archived_result_files_checked': len(relocations),
            'archived_suite_evidence_files_checked': len(suite_moved),
            'historical_root_ids': len(old_ids), **current,
            'source_equivalence_claimed': False, 'inference_performed': False, 'files_modified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        report = audit(args.root)
    except Exception as exc:
        print('MIGRATION AUDIT FAILED: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
