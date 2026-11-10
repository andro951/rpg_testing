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


def expected_definitions(root):
    # Compilation is pure and checks reference data without executing a model.
    sys.path.insert(0, str(root))
    from prompt_builder.builder import applicable, compile_test, load_case
    templates = root / 'prompt_builder/templates'
    selection = json.loads((templates / 'common/selection.json').read_text(encoding='utf8'))
    expected = {}
    for name in selection['test_cases']:
        case = load_case(name, templates)
        for output_format in selection['output_formats']:
            if applicable(case, output_format, templates):
                continue
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
