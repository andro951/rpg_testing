"""Explain deterministic response contracts using captured definitions and evidence."""
from __future__ import annotations

import copy
import hashlib
import re
from collections import Counter

from workbench.domain import canonical, digest
from workbench.scoring import apply, changes, equal, idx, parse, pointer

VERSION = 'detailed-evaluator-v1'
PASS, FAIL, NOT_EVALUATED, NOT_APPLICABLE = 'passed', 'failed', 'not_evaluated', 'not_applicable'


def preview(value):
    """Bound explanations, while retaining a checksum of unabridged values."""
    text = canonical(value)
    if len(text) <= 600:
        return value
    return {'summary': text[:400], 'length': len(value) if hasattr(value, '__len__') else None,
            'sha256': hashlib.sha256(text.encode()).hexdigest(), 'truncated': True}


class Report:
    def __init__(self):
        self.checks = []

    def add(self, code, status, explanation, *, scope='response', expected=None, actual=None, **metadata):
        check = {'code': code, 'status': status, 'scope': scope, 'explanation': explanation, **metadata}
        if expected is not None:
            check['expected'] = preview(expected)
        if actual is not None:
            check['actual'] = preview(actual)
        self.checks.append(check)
        return status == PASS

    def compare(self, code, expected, actual, explanation, **metadata):
        return self.add(code, PASS if equal(expected, actual) else FAIL, explanation,
                        expected=expected, actual=actual, **metadata)


class ResolutionError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def resolve(doc, parts, *, add=False):
    """Resolve against this operation's current state, distinguishing failure causes."""
    node = doc
    for n, key in enumerate(parts):
        leaf = n == len(parts) - 1
        if isinstance(node, dict):
            if key not in node:
                if leaf and add:
                    return None
                raise ResolutionError('missing_field' if leaf else 'missing_ancestor',
                                      f'Key {key!r} does not exist at /' + '/'.join(parts[:n]))
            node = node[key]
        elif isinstance(node, list):
            try:
                position = idx(key, len(node), leaf and add)
            except ValueError as exc:
                code = 'array_bounds' if str(exc) == 'Array index out of bounds' else 'array_index'
                raise ResolutionError(code, str(exc) + f': {key!r}, array length {len(node)}') from exc
            node = node[position] if position < len(node) else None
        else:
            raise ResolutionError('non_container', f'Cannot access {key!r} inside {type(node).__name__}')
    return node


def array_checks(report, path, expected, actual):
    """Separate array membership/content/order instead of flooding shifted-index diffs."""
    report.compare('array.length', len(expected), len(actual), f'{path}: required array length.', scope=path)
    keyed = all(isinstance(x, dict) and isinstance(x.get('ticket_id'), str) for x in expected + actual)
    ids = [x['ticket_id'] for x in expected + actual] if keyed else []
    keyed = keyed and len(set(ids[:len(expected)])) == len(expected) and len(set(ids[len(expected):])) == len(actual)
    if keyed:
        wanted = [x['ticket_id'] for x in expected]
        got = [x['ticket_id'] for x in actual]
        missing = list((Counter(wanted) - Counter(got)).elements())
        extra = list((Counter(got) - Counter(wanted)).elements())
        report.add('array.membership', FAIL if missing or extra else PASS,
                   f'{path}: missing ticket IDs {preview(missing)}; unexpected ticket IDs {preview(extra)}.', scope=path,
                   actual={'missing': missing, 'unexpected': extra})
        mismatch = next((n for n, (x, y) in enumerate(zip(wanted, got)) if x != y), min(len(wanted), len(got)))
        context = '' if wanted == got else f' First mismatch at index {mismatch}: expected {wanted[mismatch] if mismatch < len(wanted) else "end of array"}, got {got[mismatch] if mismatch < len(got) else "end of array"}.'
        report.compare('array.order', wanted, got, f'{path}: ticket order must match the requested placement.' + context, scope=path)
        expected_by_id = {x['ticket_id']: x for x in expected}
        for item in actual:
            if item['ticket_id'] in expected_by_id:
                differences = changes(expected_by_id[item['ticket_id']], item)
                if differences:
                    report.add('array.record_content', FAIL,
                               f'{path}: ticket {item["ticket_id"]} has wrong or missing fields.', scope=path,
                               actual=differences, expected=expected_by_id[item['ticket_id']])
        if not any(c['code'] == 'array.record_content' and c['scope'] == path for c in report.checks):
            report.add('array.record_content', PASS, f'{path}: all shared tickets retain their required contents.', scope=path)
    else:
        missing = list((Counter(map(canonical, expected)) - Counter(map(canonical, actual))).elements())
        extra = list((Counter(map(canonical, actual)) - Counter(map(canonical, expected))).elements())
        report.add('array.membership', FAIL if missing or extra else PASS,
                   f'{path}: missing items {preview(missing)}; unexpected items {preview(extra)}.', scope=path)
        mismatch = next((n for n, (x, y) in enumerate(zip(expected, actual)) if not equal(x, y)), min(len(expected), len(actual)))
        context = '' if equal(expected, actual) else f' First mismatch at index {mismatch}: expected {preview(expected[mismatch]) if mismatch < len(expected) else "end of array"}, got {preview(actual[mismatch]) if mismatch < len(actual) else "end of array"}.'
        report.compare('array.order', expected, actual, f'{path}: item contents and order must match.' + context, scope=path)


def state_checks(report, test, actual):
    before, expected = test['source']['initial_state'], test['expected_state']
    required = changes(before, expected)
    predicted = changes(before, actual)
    for path, change in sorted(required.items()):
        got = predicted.get(path)
        report.compare('task.required_change', change, got,
                       f'{path}: apply the established change; hypothetical actions are not additional changes.', scope=path)
    extras = sorted(predicted.keys() - required.keys())
    report.add('state.preservation', FAIL if extras else PASS,
               'Unrelated tracked fields must remain unchanged.' + (' Unexpected changes: ' + ', '.join(extras) if extras else ''),
               scope='final_state', actual=extras)
    def arrays(wanted, got, path=''):
        if isinstance(wanted, dict) and isinstance(got, dict):
            for key in sorted(wanted.keys() & got.keys()):
                arrays(wanted[key], got[key], path + '/' + key.replace('~', '~0').replace('/', '~1'))
        elif isinstance(wanted, list) and isinstance(got, list):
            array_checks(report, path, wanted, got)
    arrays(expected, actual)
    if test.get('state_schema'):
        from jsonschema import Draft202012Validator
        from workbench.domain import local_schema
        local_schema(test['state_schema'])
        problems = sorted((e.message for e in Draft202012Validator(test['state_schema']).iter_errors(actual)))
        report.add('state.schema', FAIL if problems else PASS, 'Final state schema: ' + '; '.join(problems), scope='final_state')
    report.compare('state.final', expected, actual, 'Final state must equal the fixed oracle, including unchanged data.', scope='final_state')


def patch_checks(report, test, variant, raw):
    representation = variant['result']['representation']
    try:
        patch = parse(raw) if isinstance(raw, str) else copy.deepcopy(raw)
        canonical(patch)
    except (ValueError, TypeError) as exc:
        report.add('json.document', FAIL, str(exc))
        report.add('state.final', NOT_EVALUATED, 'Parsing failed; no patch was applied.', dependencies=['json.document'])
        return
    report.add('json.document', PASS, 'Valid whole JSON document; no duplicate keys or non-finite numbers.')
    if representation == 'state':
        state_checks(report, test, patch)
        return
    if not isinstance(patch, list):
        report.add('patch.array', FAIL, 'Expected a JSON array of operations.', actual=patch)
        report.add('state.final', NOT_EVALUATED, 'Response was not a patch array.', dependencies=['patch.array'])
        return
    report.add('patch.array', PASS, 'Response is an array of operations.')
    required_ops = variant['result'].get('required_ops')
    if required_ops is not None:
        names = [x.get('op') if isinstance(x, dict) else None for x in patch]
        report.compare('patch.required_operations', required_ops, names,
                       'This contract requires these operation names in this exact order, including any test precondition.')
    doc = copy.deepcopy(test['source']['initial_state'])
    blocked = None
    allowed = {'set', 'list_add', 'list_remove'} if representation == 'semantic' else {'add', 'remove', 'replace', 'move', 'copy', 'test'}
    oracle_changes = changes(test['source']['initial_state'], test['expected_state'])
    for number, item in enumerate(patch):
        meta = {'operation': number, 'scope': 'operation'}
        structure = isinstance(item, dict) and isinstance(item.get('op'), str) and item['op'] in allowed and isinstance(item.get('path'), str)
        if structure:
            op = item['op']
            structure = ('value' in item if op in {'add', 'replace', 'test', 'set', 'list_add', 'list_remove'} else True)
            if op in {'move', 'copy'}:
                structure = structure and isinstance(item.get('from'), str)
            if representation == 'semantic':
                structure = structure and set(item) == {'op', 'path', 'value'}
        report.add('patch.structure', PASS if structure else FAIL,
                   'Operation needs a recognized name, string path and its required value/from fields.' if not structure else 'Operation structure satisfies its declared representation.',
                   actual=item, **meta)
        syntax = structure
        parts = source = None
        if structure:
            for field in ('path', 'from') if item['op'] in {'move', 'copy'} else ('path',):
                try:
                    parsed = pointer(item[field])
                    if field == 'path': parts = parsed
                    else: source = parsed
                    report.add('pointer.syntax', PASS, f'{field}: valid JSON Pointer syntax.', field=field, actual=item[field], **meta)
                except ValueError as exc:
                    syntax = False
                    report.add('pointer.syntax', FAIL, f'{field}: {exc}', field=field, actual=item[field], **meta)
            # A matching proposed scalar value is useful even when its target fails.
            if 'value' in item and len(oracle_changes) == 1:
                expected_path, delta = next(iter(oracle_changes.items()))
                proposed_path = item['path']
                displayed = '/'+'.'.join(pointer(expected_path))
                if 'value' in delta and not isinstance(delta['value'], (list, dict)) and proposed_path in (expected_path, displayed):
                    report.compare('task.proposed_value', delta['value'], item['value'],
                                   'Proposed value comparison only; this does not establish correct targeting or successful application.', **meta)
        if blocked is not None:
            report.add('patch.application', NOT_EVALUATED, f'Operation {blocked} blocked sequential application.', dependencies=[f'operation:{blocked}'], **meta)
            continue
        if not syntax:
            blocked = number
            report.add('patch.application', NOT_EVALUATED, 'Invalid structure/pointer prevents application.', **meta)
            continue
        try:
            context = doc
            resolving_field = 'path'
            if source is not None:
                resolving_field = 'from'
                resolve(doc, source)
                report.add('pointer.source', PASS, 'Source resolves to an existing value.', actual=item['from'], **meta)
                if item['op'] == 'move':
                    if len(parts) > len(source) and parts[:len(source)] == source:
                        raise ResolutionError('move_descendant', 'Cannot move a value into its own descendant.')
                    context = apply(doc, [{'op': 'remove', 'path': item['from']}], 'json_patch')
            resolving_field = 'path'
            old = resolve(context, parts, add=item['op'] in {'add', 'move', 'copy'})
            report.add('pointer.target', PASS, 'Target resolves with the required operation semantics; move destinations resolve after source removal.', actual=item['path'], **meta)
            if representation == 'semantic' and item['op'] in {'list_add', 'list_remove'}:
                if not isinstance(old, list):
                    raise ResolutionError('semantic_array_target', 'Semantic list operation requires an array target.')
                if item['op'] == 'list_remove':
                    matches = sum(equal(x, item['value']) for x in old)
                    report.compare('array.removal_match', 1, matches, 'Semantic removal requires exactly one matching item.', **meta)
            if item['op'] == 'test':
                report.compare('patch.precondition', item['value'], old, 'Test precondition must match the current value before later operations.', **meta)
            doc = apply(doc, [item], representation)
            report.add('patch.application', PASS, 'Operation applied successfully to a copy of the current state.', **meta)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            blocked = number
            code = 'pointer.' + exc.code if isinstance(exc, ResolutionError) else ('patch.precondition_failed' if str(exc) == 'JSON Patch test failed' else 'patch.application_failed')
            explanation = str(exc)
            if isinstance(exc, ResolutionError) and resolving_field == 'path' and len(parts) == 1 and '.' in parts[0]:
                candidate = '/' + '/'.join(parts[0].split('.'))
                try:
                    resolve(context, pointer(candidate), add=item['op'] in {'add', 'move', 'copy'})
                    explanation += f' The displayed dot path corresponds to JSON Pointer {candidate}; the submitted path was not changed or applied.'
                except (ValueError, TypeError):
                    pass
            report.add(code, FAIL, explanation, actual=item, field=resolving_field, **meta)
    if blocked is None:
        state_checks(report, test, doc)
    else:
        report.add('state.final', NOT_EVALUATED, f'Operation {blocked} prevented complete application; final state was not checked.',
                   scope='final_state', dependencies=[f'operation:{blocked}'])


def answer_checks(report, variant, values):
    expected = variant.get('expected_answers', {})
    if not expected:
        report.add('answer.oracle', NOT_APPLICABLE, 'No fixed-answer oracle; dialogue quality needs a separate rubric.')
    for step, wanted in expected.items():
        if step not in values:
            report.add('answer.missing', FAIL, f'No answer for required step {step}.', step=step)
            continue
        actual = values[step]
        report.compare('answer.exact', wanted, actual, 'Exact expected answer and type are required.', step=step)
        if isinstance(wanted, str) and re.fullmatch(r'[0-9]+(?:, [0-9]+)?', wanted):
            expected_indices = [int(x) for x in wanted.split(', ')]
            text = actual if isinstance(actual, str) else canonical(actual)
            tokens = re.findall(r'-?\d+(?:\.\d+)?', text)
            unambiguous = len(tokens) == len(expected_indices) and all(re.fullmatch(r'0|[1-9][0-9]*', t) for t in tokens)
            same = unambiguous and [int(t) for t in tokens] == expected_indices
            report.add('index.value', PASS if same else FAIL,
                       'Numeric index values match, but literal formatting is judged separately.' if same else 'Wrong, missing or ambiguous index values; move answers require source then destination.',
                       expected=expected_indices, actual=tokens, step=step)
            report.compare('index.format', wanted, actual, 'Return only the exact requested index text, including move pair order and spacing.', step=step)


def assess(test, variant, values, *, execution='completed', original_score=None):
    """Evaluate supplied completed values; callers must identify partial/error evidence."""
    report = Report()
    report.add('evidence.execution', PASS if execution == 'completed' else NOT_EVALUATED,
               'Completed response.' if execution == 'completed' else f'Execution is {execution}; semantic success is not established.')
    result = variant.get('result', {})
    if execution != 'completed':
        report.add('state.final', NOT_EVALUATED, 'Incomplete or unavailable response; no completed semantic verdict.')
    elif result.get('representation', 'answers') == 'answers':
        answer_checks(report, variant, values)
    elif result.get('step') not in values:
        report.add('answer.missing', FAIL, 'The required final output step has no value.', step=result.get('step'))
        report.add('state.final', NOT_EVALUATED, 'Final output is missing.')
    elif 'expected_state' not in test:
        report.add('state.oracle', NOT_APPLICABLE, 'No fixed final-state oracle.')
    else:
        patch_checks(report, test, variant, values[result['step']])
    for check in variant.get('checks', []):
        actual = values.get(check['step'])
        op = check['operator']
        passed = equal(actual, check['value']) if op == 'equals' else str(check['value']) in str(actual)
        if op == 'not_contains': passed = not passed
        if op not in {'equals', 'contains', 'not_contains'}:
            report.add('workflow.check_contract', NOT_EVALUATED, f'Unsupported check operator {op}.', step=check['step'])
        else:
            report.add('workflow.explicit_check', (PASS if passed else FAIL) if check['step'] in values else NOT_EVALUATED,
                       check.get('name', check['step']) + ': supplementary check, separate from original final exact-match verdict.',
                       step=check['step'], affects_verdict=False, expected=check['value'], actual=actual)
    fixed_oracle = bool(variant.get('expected_answers')) if result.get('representation', 'answers') == 'answers' else 'expected_state' in test
    failed = [c for c in report.checks if c['status'] == FAIL and c.get('affects_verdict', True)]
    outcome = 'INCONCLUSIVE' if execution != 'completed' else ('UNSCORED' if not fixed_oracle else ('FAIL' if failed else 'PASS'))
    return {'evaluator_version': VERSION, 'test_id': test['id'], 'variant_id': variant['id'],
            'definition_hash': digest({'test': test, 'variant': variant}), 'execution_outcome': execution,
            'objective_outcome': outcome, 'primary_reason': failed[0]['explanation'] if failed else None,
            'checks': report.checks, 'original_score': copy.deepcopy(original_score)}


def steps_by_id(steps):
    result = {}
    for step in steps:
        result[step['id']] = step
        result.update(steps_by_id(step.get('steps', [])))
    return result


def completed_call(call):
    return call.get('finish_reason') in {'stop', 'provider_completed'} and not call.get('incomplete')


def trace_checks(variant, calls):
    """Replay the bounded interpreter's control flow without executing model calls."""
    report = Report()
    values, position, stopped = {}, 0, False
    def condition(rule):
        return rule is None or rule['step'] in values and equal(values[rule['step']], rule.get('equals'))
    def walk(steps, iteration=0):
        nonlocal position, stopped
        for step in steps:
            if stopped: return
            if not condition(step.get('when')): continue
            if step['type'] == 'loop':
                for n in range(step['max_iterations']):
                    if condition(step.get('until')) or stopped: break
                    walk(step['steps'], n+1)
                continue
            if position >= len(calls):
                report.add('workflow.unreached', NOT_EVALUATED, f'Step {step["id"]} has no saved call; later workflow checks are unreached.', scope='workflow')
                stopped = True
                return
            call = calls[position]
            if call.get('step') != step['id'] or ('iteration' in call and call['iteration'] != iteration):
                report.add('workflow.call_order', FAIL, f'Expected {step["id"]} iteration {iteration}, found {call.get("step")} iteration {call.get("iteration")}.', scope='evidence')
                stopped = True
                return
            position += 1
            if not completed_call(call):
                stopped = True
                return
            try:
                kind = step.get('output', {}).get('type', 'text')
                value = call.get('text') if kind == 'text' else parse(call['text'])
                if kind != 'text':
                    from jsonschema import Draft202012Validator
                    from workbench.workflows import output_schema
                    from workbench.domain import local_schema
                    schema = output_schema(step['output']); local_schema(schema)
                    if list(Draft202012Validator(schema).iter_errors(value)):
                        stopped = True
                        break
                values[step['id']] = value
                if step.get('assign'): values[step['assign']] = value
            except (ValueError, TypeError, KeyError):
                stopped = True
                break
    walk(variant.get('steps', []))
    if position < len(calls) and not any(c['status'] == FAIL for c in report.checks):
        report.add('workflow.unexpected_call', FAIL, 'Calls continued after the declared workflow stopped, skipped a branch or reached its repair stopping condition.', scope='evidence')
    elif not stopped:
        report.add('workflow.call_order', PASS, 'Calls follow the declared step order, branch conditions, loop limits and repair stopping condition.', scope='evidence')
    return report.checks


def assess_record(record):
    """Replay immutable captured evidence; never substitutes current edited definitions."""
    test, variant = record['test_definition'], record['variant_definition']
    execution = 'timeout' if record.get('timed_out') else record.get('status', 'missing')
    incomplete = any(not completed_call(c) for c in record.get('calls', []))
    if execution == 'completed' and incomplete: execution = 'incomplete'
    assessment = assess(test, variant, record.get('outputs', {}), execution=execution, original_score=record.get('score'))
    assessment.update({'case_id': record.get('case_id'), 'source_record_checksum': record.get('sha256'),
                       'model_id': record.get('model_id'), 'repetition': record.get('repetition'),
                       'measurement_valid': record.get('measurement_valid'), 'steps': []})
    definitions = steps_by_id(variant.get('steps', []))
    reconstructed = {}
    history_checks = Report()
    loops = {}
    def collect_loops(steps, bounds=None):
        for s in steps:
            if bounds is not None: loops[s['id']] = bounds
            if s.get('type') == 'loop': collect_loops(s['steps'], s['max_iterations'])
    collect_loops(variant.get('steps', []))
    for call in record.get('calls', []):
        step = definitions.get(call.get('step'))
        if step is None:
            assessment['checks'].append({'code': 'evidence.unknown_step', 'status': NOT_EVALUATED, 'scope': 'evidence', 'explanation': 'Call has no captured step contract.'})
            continue
        complete = completed_call(call)
        detail = {'step': step['id'], 'iteration': call.get('iteration', 0), 'complete': complete,
                  'messages_sha256': digest(call.get('messages', [])), 'text_sha256': digest(call.get('text')),
                  'checks': [], 'semantic_outcome': 'UNSCORED'}
        r = Report()
        schema_type = step.get('output', {}).get('type', 'text')
        condition = step.get('when')
        if condition:
            valid_branch = condition['step'] in reconstructed and equal(reconstructed[condition['step']], condition.get('equals'))
            history_checks.add('workflow.branch', PASS if valid_branch else FAIL,
                               'A conditional step must run only when its recorded prerequisite matches.', step=step['id'], scope='evidence')
        if step['id'] in loops:
            iteration = call.get('iteration')
            valid_iteration = type(iteration) is int and 1 <= iteration <= loops[step['id']]
            history_checks.add('workflow.loop_bound', PASS if valid_iteration else FAIL,
                               'Repair iteration must stay within the declared workflow bound.', step=step['id'], scope='evidence')
        for used in step.get('uses', []):
            r.add('workflow.prior_output', PASS if used in reconstructed else NOT_EVALUATED,
                  f'Previous output {used} is available.' if used in reconstructed else f'Previous output {used} is unavailable; skipped conditional outputs may legitimately be absent.')
        if not complete:
            r.add('workflow.step_output', NOT_EVALUATED, 'Partial output retained; a complete-looking prefix does not establish completion.')
        elif schema_type != 'text':
            try:
                from jsonschema import Draft202012Validator
                from workbench.workflows import output_schema
                from workbench.domain import local_schema
                value = parse(call['text'])
                schema = output_schema(step['output'])
                local_schema(schema)
                errors = [e.message for e in Draft202012Validator(schema).iter_errors(value)]
                r.add('workflow.output_type', FAIL if errors else PASS, '; '.join(errors) if errors else 'Output satisfies its declared JSON type/schema.')
                if not errors and step['id'] in variant.get('expected_answers', {}):
                    r.compare('answer.exact', variant['expected_answers'][step['id']], value, 'Typed answer must match the fixed expected value.')
            except (ValueError, TypeError, KeyError) as exc:
                r.add('workflow.output_type', FAIL, str(exc))
        elif step['id'] == variant.get('result', {}).get('step') or step.get('assign') == variant.get('result', {}).get('step'):
            if 'expected_state' in test:
                patch_checks(r, test, variant, call.get('text'))
                detail['semantic_outcome'] = 'FAIL' if any(c['status'] == FAIL for c in r.checks) else 'PASS'
        elif step['id'] in variant.get('expected_answers', {}):
            answer_checks(r, {**variant, 'expected_answers': {step['id']: variant['expected_answers'][step['id']]}}, {step['id']: call.get('text')})
        else:
            r.add('workflow.intermediate_meaning', NOT_APPLICABLE, 'No fixed semantic oracle for this intermediate prose; retain it for review.')
        if complete:
            try:
                value = call.get('text') if schema_type == 'text' else parse(call['text'])
                # Verify a review claim against the preceding patch, never against itself.
                if step.get('output', {}).get('type') == 'boolean' and 'patch' in step.get('uses', []) and 'expected_state' in test:
                    prior = assess(test, variant, {variant['result']['step']: reconstructed.get('patch')})
                    correct = prior['objective_outcome'] == 'PASS'
                    r.compare('workflow.self_review', correct, value,
                              'Self-review claim must agree with the independently evaluated preceding patch; it cannot certify success.')
                if not any(c['status'] == FAIL and c['code'] == 'workflow.output_type' for c in r.checks):
                    reconstructed[step['id']] = value
                    if step.get('assign'): reconstructed[step['assign']] = value
            except (ValueError, TypeError, KeyError):
                pass
        detail['checks'] = r.checks
        assessment['steps'].append(detail)
    if record.get('calls'):
        history_checks.checks.extend(trace_checks(variant, record['calls']))
        for key, value in record.get('outputs', {}).items():
            if key in reconstructed:
                history_checks.compare('evidence.output_consistency', value, reconstructed[key],
                                       'Saved output must match the final completed call/assignment for this step.', step=key, scope='evidence')
        for event in record.get('step_events', []):
            step = definitions.get(event.get('step'))
            if step and event.get('status') == 'loop_finished':
                n = event.get('iterations')
                history_checks.add('workflow.loop_bound', PASS if type(n) is int and 0 <= n <= step['max_iterations'] else FAIL,
                                   'Saved loop summary must respect its maximum iteration count.', step=step['id'], scope='evidence')
    else:
        history_checks.add('evidence.call_history', NOT_EVALUATED, 'No call history; step-level timing, message and workflow evidence cannot be verified.', scope='evidence')
    assessment['checks'].extend(history_checks.checks)
    if any(c['status'] == FAIL for c in history_checks.checks):
        assessment['execution_outcome'] = 'evidence_error'
        assessment['objective_outcome'] = 'INCONCLUSIVE'
    old = record.get('score', {}).get('exact_match')
    current = assessment['objective_outcome']
    assessment['score_comparison'] = ('agrees' if (current == 'PASS') == old else 'disagreement') if type(old) is bool and current in {'PASS', 'FAIL'} else 'not_comparable'
    return assessment
