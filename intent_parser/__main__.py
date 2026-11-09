"""Usage: python -m intent_parser prepared-records.json [--json-patch]."""
import argparse
import json
import sys
from .replay import replay_prepared
from . import (parse_intent, parse_intent_with_diagnostics, convert_intent,
               normalize_intent, apply_patch, build_prompt)


def _json_lines():
    for line in sys.stdin:
        try:
            request = json.loads(line)
            options = request.get('options', {})
            action = request.get('action', 'normalize')
            if action == 'parse':
                result = parse_intent(request['text'], options)
            elif action == 'diagnostics':
                result = parse_intent_with_diagnostics(request['text'], options)
            elif action == 'normalize':
                result = normalize_intent(request['text'], request['input'], options)
            elif action == 'convert':
                result = convert_intent(request['ir'], request['input'], options)
            elif action == 'apply':
                result = apply_patch(request['input'], request['patch'], options)
            elif action == 'prompt':
                result = build_prompt({'request': request['request'], 'document': request['input'], 'idKey': options.get('idKey', 'id')})
            elif action == 'replay':
                result = replay_prepared(request['records'], options)
            else:
                raise ValueError('Unknown action')
            response = {'ok': True, 'result': result}
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            response = {'ok': False, 'error': str(exc)}
        print(json.dumps(response, ensure_ascii=True, allow_nan=False))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ['--json-lines']:
        return _json_lines()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('records')
    parser.add_argument('--json-patch', action='store_true')
    args = parser.parse_args(argv)
    try:
        with open(args.records, encoding='utf-8') as stream:
            report = replay_prepared(json.load(stream), {'json_patch': args.json_patch})
        json.dump(report, sys.stdout, ensure_ascii=True, indent=2, allow_nan=False)
        sys.stdout.write('\n')
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
