"""Synthetic JSONL peer for Codex transport tests; never calls a model."""
import json
import sys

mode = sys.argv[1]
for line in sys.stdin:
    request = json.loads(line)
    method, ident = request.get('method'), request.get('id')
    if ident is None:
        continue
    def reply(value):
        print(json.dumps({'id': ident, 'result': value}), flush=True)
    def event(method, params):
        print(json.dumps({'method': method, 'params': params}), flush=True)
    if method == 'initialize':
        if mode == 'malformed':
            print('invalid JSON', flush=True)
        else:
            reply({'userAgent': 'fake'})
    elif method == 'account/read':
        reply({'requiresOpenaiAuth': True, 'account': None if mode == 'signed-out' else {'type': 'chatgpt'}})
    elif method == 'model/list':
        cursor = request['params'].get('cursor')
        reply({'data': [{'model': 'fake-gpt-' + ('b' if cursor else 'a'), 'displayName': 'Synthetic GPT',
                        'supportedReasoningEfforts': [{'reasoningEffort': 'low'}, {'reasoningEffort': 'high'}],
                        'defaultReasoningEffort': 'low', 'isDefault': not cursor}],
               'nextCursor': None if cursor else 'page2'})
    elif method in ('thread/start', 'thread/resume'):
        if method == 'thread/resume' and mode == 'resume-fail':
            print(json.dumps({'id': ident, 'error': {'code': -1, 'message': 'Synthetic thread missing'}}), flush=True)
        else:
            reply({'thread': {'id': request['params'].get('threadId', 'synthetic-thread')}})
    elif method == 'turn/start':
        if mode == 'disconnect':
            sys.exit(0)
        if mode == 'rpc-error':
            print(json.dumps({'id': ident, 'error': {'code': -1, 'message': 'Synthetic turn rejected'}}), flush=True)
            continue
        thread = request['params']['threadId']
        common = {'threadId': thread, 'turnId': 'synthetic-turn'}
        event('turn/started', {'threadId': thread, 'turn': {'id': 'synthetic-turn'}})
        reply({'turn': {'id': 'synthetic-turn'}})
        if mode == 'interactive':
            print(json.dumps({'id': 'tool-1', 'method': 'item/tool/requestUserInput', 'params': common}), flush=True)
            continue
        event('item/completed', {**common, 'item': {'id': 'comment', 'type': 'agentMessage', 'phase': 'commentary', 'text': 'Thinking'}})
        event('item/started', {**common, 'item': {'id': 'answer', 'type': 'agentMessage', 'phase': 'final_answer', 'text': ''}})
        event('item/agentMessage/delta', {**common, 'itemId': 'answer', 'delta': 'Synthetic proposal'})
        event('item/completed', {**common, 'item': {'id': 'answer', 'type': 'agentMessage', 'phase': 'final_answer', 'text': 'Synthetic proposal'}})
        event('thread/tokenUsage/updated', {**common, 'tokenUsage': {'total': {'totalTokens': 123}}})
        event('turn/completed', {'threadId': thread, 'turn': {'id': 'synthetic-turn', 'status': 'failed' if mode == 'failed' else 'completed',
                                                           'error': {'message': 'Synthetic generation failure'}, 'items': []}})
    elif method == 'turn/interrupt':
        reply({})
