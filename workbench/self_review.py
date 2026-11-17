"""Bounded model self-review, without access to test definitions or grading."""
from __future__ import annotations
import copy
import re
import time

RETRY_LIMIT = 3
LEGACY_PROTOCOL = 'yes-no-v1'
JUSTIFIED_PROTOCOL = 'justified-v2'
JUSTIFIED_REVIEW_QUESTION = (
    'Does this answer look correct? Start with Yes or No on its own line. '
    'Then provide a natural-language justification of your decision. '
    'If Yes, explain why the answer is correct. If No, explain both what is right '
    'and what is wrong with the answer; if nothing is right, say so. '
    'Review the answer against the original request, including its output format.')
JUSTIFIED_REPLACEMENT_REQUEST = (
    'Use your review above to correct the previous answer. Preserve the parts you '
    'identified as right and fix the parts you identified as wrong. Provide a complete '
    'new answer to the original request, following its requested output format.')

REVIEW_QUESTION = 'Does this answer look correct? Yes or no.'
REPLACEMENT_REQUEST = ('You judged your previous answer wrong. Provide a new answer to the original request, '
                       'following its requested output format.')


def enabled(variant):
    value = variant.get('retry_enabled', False)
    if type(value) is not bool:
        raise ValueError('retry_enabled must be boolean')
    protocol(variant)
    return value


def protocol(variant):
    value = variant.get('retry_protocol', LEGACY_PROTOCOL)
    if value not in (LEGACY_PROTOCOL, JUSTIFIED_PROTOCOL):
        raise ValueError('Unknown retry_protocol')
    if 'retry_protocol' in variant and not variant.get('retry_enabled', False):
        raise ValueError('retry_protocol requires retry_enabled')
    return value


def justified_decision(text):
    """Verdict is explicit first line; prose is retained, never semantically graded."""
    if not isinstance(text, str):
        return 'ambiguous'
    lines = text.strip().splitlines()
    if len(lines) < 2 or not any(c.isalnum() for c in '\n'.join(lines[1:])):
        return 'ambiguous'
    return decision(lines[0])


def decision(text):
    """Accept only one yes/no word, optionally followed by one period/exclamation."""
    match = re.fullmatch(r'(yes|no)[.!]?', text.strip(), re.IGNORECASE) if isinstance(text, str) else None
    return match.group(1).lower() if match else 'ambiguous'


def generate(prompt, schema, request, calls, events, metadata, cancel=None, on_stage=None, finish='stop', review_protocol=LEGACY_PROTOCOL):
    """Record each request before propagating failures; return the last answer call.

    Ambiguous reviews stop immediately with the last answer unendorsed. They do
    not authorize replacements or acceptance. At most four answers/four reviews.
    ``request`` applies the existing backend's controls and whole-case deadline.
    """
    from .workflows import Cancelled
    if review_protocol not in (LEGACY_PROTOCOL, JUSTIFIED_PROTOCOL):
        raise ValueError('Unknown retry_protocol')
    justified = review_protocol == JUSTIFIED_PROTOCOL
    question = JUSTIFIED_REVIEW_QUESTION if justified else REVIEW_QUESTION
    replacement = JUSTIFIED_REPLACEMENT_REQUEST if justified else REPLACEMENT_REQUEST
    history = copy.deepcopy(prompt)
    def ask(kind, attempt, output_schema):
        if cancel and cancel.is_set():
            raise Cancelled('Stopped by user')
        if on_stage:
            on_stage(metadata['step'] + ':' + kind + ':' + str(attempt))
        info = {**metadata, 'messages': copy.deepcopy(history), 'schema': output_schema,
                'call_kind': kind, 'answer_attempt': attempt}
        if justified:
            info['review_protocol'] = review_protocol
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
        history.append({'role': 'user', 'content': question})
        review = ask('self_review', attempt, None)
        verdict = (justified_decision if justified else decision)(review['text'])
        review['review_decision'] = verdict
        outcome = ('accepted' if verdict == 'yes' else 'ambiguous_review' if verdict == 'ambiguous'
                   else 'retry_budget_exhausted' if attempt == RETRY_LIMIT else 'replacement_requested')
        events.append({'step': metadata['step'], 'iteration': metadata.get('iteration', 0),
                       'status': 'self_review', 'answer_attempt': attempt, 'decision': verdict,
                       'outcome': outcome, 'retries_used': attempt, 'retry_limit': RETRY_LIMIT})
        if verdict != 'no' or attempt == RETRY_LIMIT:
            return answer
        history.append({'role': 'user', 'content': replacement})
        answer = ask('replacement_answer', attempt + 1, schema)
    raise AssertionError('unreachable')
