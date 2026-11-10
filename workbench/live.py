"""Prepare or inspect an isolated current-contract Workbench run; never auto-run.

The default action only creates new definition copies. Serving the prepared
directory is explicit and still requires the normal user's Run action.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

from evaluation.live_intent import VERSION, STRICT, select, identity
from .domain import read_json, validate_test, digest, experiment_spec


def prepare(source, output, evaluator, test_ids=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_dir():
        raise ValueError('Definition source must be an existing test_specs directory')
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('Prepared output must be separate from source definitions')
    if output.exists():
        raise ValueError('Output must be a new directory; existing runs are never overwritten')
    wanted = set(test_ids or [])
    originals = [(p, read_json(p)) for p in sorted(source.glob('*.json'))]
    if wanted - {test['id'] for _, test in originals}:
        raise ValueError('Unknown requested test ID')
    from .judgements import JudgementStore, definition_id
    rejected=JudgementStore(source.parent).read()['entries']
    rows, transformed = [], []
    for path, original in originals:
        if wanted and original['id'] not in wanted:
            continue
        validate_test(original)
        if not original.get('enabled', True):
            continue
        eligible=copy.deepcopy(original)
        for variant in eligible['variants']:
            if rejected.get(definition_id(original, variant), {}).get('blocked'):
                variant['enabled']=False
        if not any(v.get('enabled',True) for v in eligible['variants']):
            continue
        chosen = select(eligible, evaluator)
        validate_test(chosen)
        for old, new in zip(original['variants'], chosen['variants']):
            if not new.get('enabled', True):
                continue
            # Prompt data is not regenerated, rewritten or approved by preparation.
            for before, after in zip(old['steps'], new['steps']):
                if before != after:
                    raise ValueError('Evaluator selection must not change any workflow step')
            rows.append({'test_id': chosen['id'], 'variant_id': new['id'],
                         'source_file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'source_definition_id': digest(experiment_spec(original, old)),
                         'selected_definition_id': digest(experiment_spec(chosen, new))})
        transformed.append(chosen)
    if not transformed:
        raise ValueError('No enabled definitions selected')
    manifest = {'mode': 'prepared-live-evaluator', 'evaluator': evaluator,
                'evaluator_identity': identity() if evaluator == VERSION else None,
                'source_directory': str(source), 'definitions': rows,
                'tests': len(transformed), 'variants': len(rows),
                'inference_started': False, 'prompts_changed': False,
                'note': 'A new evaluation protocol, not a re-score or approval of old evidence. Select the intended model/test scope before Run.'}
    output.mkdir(parents=True, exist_ok=False)
    specs = output/'test_specs'; specs.mkdir()
    for test in transformed:
        with (specs/(test['id']+'.json')).open('x', encoding='utf8') as f:
            json.dump(test, f, ensure_ascii=False, indent=2)
            f.write('\n')
    with (output/'evaluation-selection.json').open('x', encoding='utf8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2); f.write('\n')
    settings = output/'.local/workbench'; settings.mkdir(parents=True)
    with (settings/'settings.json').open('x', encoding='utf8') as f:
        json.dump({'models_folder_version': 1, 'sync_source': False, 'publish_results': False}, f)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--definitions', required=True)
    prep.add_argument('--output', required=True)
    prep.add_argument('--evaluator', choices=(STRICT, VERSION), required=True)
    prep.add_argument('--test', action='append', help='Optional exact test ID; repeat to select a subset')
    serve = commands.add_parser('serve')
    serve.add_argument('--root', required=True)
    serve.add_argument('--port', type=int, default=8787)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        result = prepare(args.definitions, args.output, args.evaluator, args.test)
        print(json.dumps({k: v for k, v in result.items() if k not in ('definitions', 'evaluator_identity')}, indent=2))
        return 0
    root = Path(args.root).resolve()
    if not (root/'evaluation-selection.json').is_file():
        parser.error('Use a prepared isolated root, not an old frozen cohort')
    selection = read_json(root/'evaluation-selection.json')
    from .domain import load_tests
    tests = load_tests(root/'test_specs')
    actual = {(t['id'], v['id']): digest(experiment_spec(t, v)) for t in tests for v in t['variants'] if v.get('enabled', True)}
    expected = {(r['test_id'], r['variant_id']): r['selected_definition_id'] for r in selection['definitions']}
    if actual != expected:
        parser.error('Prepared definitions changed; explicitly prepare a new run')
    if selection['evaluator'] == VERSION and selection['evaluator_identity'] != identity():
        parser.error('Evaluator changed; explicitly prepare a new run')
    # No inference here. Serving uses the established Controller/Session runner.
    from .server import serve
    from .locking import HostLock
    with HostLock(root/'.local/workbench/host.lock'):
        return serve(root, port=args.port, open_browser=False)


if __name__ == '__main__':
    raise SystemExit(main())
