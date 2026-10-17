"""Compact optimizer feedback; immutable raw evidence remains in the store."""
import copy
from workbench.domain import digest


def diagnostic(record):
    evaluation = record.get('evaluation') or {}
    checks = list(evaluation.get('checks', []))
    for step in evaluation.get('steps', []):
        checks.extend(step.get('checks', []))
    passed, other, seen = [], [], set()
    for check in checks:
        # Omit repeated full states, expected answers and duplicate check payloads.
        item = {key: check[key] for key in ('code', 'status', 'explanation', 'scope', 'step', 'operation', 'path', 'field') if key in check}
        identity = digest(item)
        if identity in seen:
            continue
        seen.add(identity)
        if item.get('status') == 'passed':
            if item.get('code') not in passed:
                passed.append(item.get('code'))
        else:
            other.append(item)
    return {'objective_outcome': evaluation.get('objective_outcome', 'UNAVAILABLE'),
            'primary_reason': evaluation.get('primary_reason'), 'passed_checks': passed,
            'other_checks': other}


class EvidencePacket:
    def __init__(self):
        self.prompts = {}

    def trial(self, record):
        item = {key: record.get(key) for key in ('model_id', 'case_id', 'repetition', 'status', 'pass', 'error')}
        item.update({key: copy.deepcopy(record[key]) for key in ('timeout_seconds', 'benchmark_reasoning') if key in record})
        item['evaluation'] = diagnostic(record)
        item['calls'] = []
        present = set()
        for call in record.get('calls', []):
            messages = call.get('request_messages')
            capture = 'effective_request'
            if messages is None:
                messages = call.get('messages')
                capture = 'captured_workflow_messages'
            prompt_id = None
            if messages is not None:
                prompt_id = digest(messages)
                self.prompts.setdefault(prompt_id, copy.deepcopy(messages))
            present.add(call.get('step'))
            item['calls'].append({'step': call.get('step'), 'iteration': call.get('iteration', 0),
                'prompt_id': prompt_id, 'request_capture': capture if prompt_id else 'not_recorded',
                'text': call.get('text'), 'finish_reason': call.get('finish_reason'),
                'incomplete': bool(call.get('incomplete') or record.get('status') != 'completed'),
                **{key: copy.deepcopy(call[key]) for key in ('sampling', 'requested_sampling', 'applied_sampling') if key in call}})
        for step, text in (record.get('outputs') or {}).items():
            if step not in present:
                item['calls'].append({'step': step, 'prompt_id': None, 'request_capture': 'not_recorded',
                    'text': text, 'finish_reason': None, 'incomplete': record.get('status') != 'completed'})
        return item
