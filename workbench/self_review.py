"""Bounded model self-review, without access to test definitions or grading."""
from __future__ import annotations
import copy
import re
import time

RETRY_LIMIT = 3
REVIEW_QUESTION = 'Does this answer look correct? Yes or no.'
REPLACEMENT_REQUEST = ('You judged your previous answer wrong. Provide a new answer to the original request, '
                       'following its requested output format.')


def enabled(variant):
    value = variant.get('retry_enabled', False)
    if type(value) is not bool:
        raise ValueError('retry_enabled must be boolean')
    return value


def decision(text):
    """Accept only one yes/no word, optionally followed by one period/exclamation."""
    match = re.fullmatch(r'(yes|no)[.!]?', text.strip(), re.IGNORECASE) if isinstance(text, str) else None
    return match.group(1).lower() if match else 'ambiguous'


def generate(prompt, schema, request, calls, events, metadata, cancel=None, on_stage=None, finish='stop'):
    """Record each request before propagating failures; return the last answer call.

    Ambiguous reviews stop immediately with the last answer unendorsed. They do
    not authorize replacements or acceptance. At most four answers/four reviews.
    ``request`` applies the existing backend's controls and whole-case deadline.
    """
    from .workflows import Cancelled
    history = copy.deepcopy(prompt)
    def ask(kind, attempt, output_schema):
        if cancel and cancel.is_set():
            raise Cancelled('Stopped by user')
        if on_stage:
            on_stage(metadata['step'] + ':' + kind + ':' + str(attempt))
        info = {**metadata, 'messages': copy.deepcopy(history), 'schema': output_schema,
                'call_kind': kind, 'answer_attempt': attempt}
        started = time.perf_counter()
        try:
            response = request(copy.deepcopy(history), output_schema)
        except Exception as exc:
            calls.append({**info, **(getattr(exc, 'partial_response', None) or {}),
                          'request_error': str(exc), 'incomplete': True,
                          'workflow_request_seconds': time.perf_counter() - started})
            events.append({'step': metadata['step'], 'iteration': metadata.get('iteration', 0),
                           'status': 'self_review_interrupted', 'call_kind': kind, 'answer_attempt': attempt})
            raise
        call = {**info, **response, 'workflow_request_seconds': time.perf_counter() - started}
        calls.append(call)
        if response.get('finish_reason') != finish:
            raise ValueError('Generation ended without completion: ' + str(response.get('finish_reason')))
        history.append({'role': 'assistant', 'content': response['text']})
        return call

    answer = ask('initial_answer', 0, schema)
    for attempt in range(RETRY_LIMIT + 1):
        history.append({'role': 'user', 'content': REVIEW_QUESTION})
        review = ask('self_review', attempt, None)
        verdict = decision(review['text'])
        review['review_decision'] = verdict
        outcome = ('accepted' if verdict == 'yes' else 'ambiguous_review' if verdict == 'ambiguous'
                   else 'retry_budget_exhausted' if attempt == RETRY_LIMIT else 'replacement_requested')
        events.append({'step': metadata['step'], 'iteration': metadata.get('iteration', 0),
                       'status': 'self_review', 'answer_attempt': attempt, 'decision': verdict,
                       'outcome': outcome, 'retries_used': attempt, 'retry_limit': RETRY_LIMIT})
        if verdict != 'no' or attempt == RETRY_LIMIT:
            return answer
        history.append({'role': 'user', 'content': REPLACEMENT_REQUEST})
        answer = ask('replacement_answer', attempt + 1, schema)
    raise AssertionError('unreachable')
