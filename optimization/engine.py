"""Durable OPRO sessions: origin gate, full task-type validation, local rankings."""
import copy
import math
import secrets
import time
import uuid
from datetime import datetime, timezone
from workbench.domain import code_fingerprint, digest, read_json
from workbench.judgements import JudgementStore, review_lock
from workbench.workflows import Cancelled
from evaluation.core import assess_record
from .storage import Store
from .templates import LABELS, freeze, parse_candidate, projection
from .runtime import Runtime, discover
from .token_budget import plan as token_plan, round_context
from workbench.execution_policy import DoesNotFit

DEFAULTS = {'max_attempts': 20, 'temperature_min': .5, 'temperature_max': .9,
            'reasoning': False}


def now():
    return datetime.now(timezone.utc).isoformat()


def settings(value, allow_legacy=False):
    if allow_legacy and isinstance(value, dict):
        value = {key: val for key, val in value.items() if key not in ('context_tokens', 'output_reserve')}
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError('Unknown optimization setting')
    result = {**DEFAULTS, **value}
    for key, lo, hi in (('max_attempts', 1, 10000),):
        if type(result[key]) is not int or not lo <= result[key] <= hi:
            raise ValueError('Invalid ' + key)
    for key in ('temperature_min', 'temperature_max'):
        if type(result[key]) not in (int, float) or not math.isfinite(result[key]) or not 0 <= result[key] <= 2:
            raise ValueError('Temperature must be finite and between 0 and 2.')
    if result['temperature_min'] > result['temperature_max']:
        raise ValueError('Minimum temperature exceeds maximum.')
    if type(result['reasoning']) is not bool:
        raise ValueError('Reasoning must be a boolean.')
    return result


def create(app, payload, cohort=None):
    if set(payload) - {'generator_id', 'origin_model_id', 'settings'}:
        raise ValueError('Unknown optimization session option')
    config = settings(payload.get('settings', {}))
    cohort = cohort or discover(app)
    if not cohort['models']:
        raise ValueError('No runnable models on this host.')
    generator = next((m for m in cohort['models'] if m['id'] == payload.get('generator_id') and m['provider'] == 'native'), None)
    if generator is None:
        raise ValueError('Choose an installed runnable native optimizer model.')
    origin_model_id = payload.get('origin_model_id') or cohort['models'][0]['id']
    if not any(m['id'] == origin_model_id for m in cohort['models']):
        raise ValueError('Choose a runnable starting-case model.')
    scope = freeze(app.root)
    definition = read_json(app.root / 'optimization/definitions/array_move_patch.json')
    session = {'schema_version': 1, 'id': uuid.uuid4().hex, 'created': now(), 'status': 'ready',
               'settings': config, 'generator_id': generator['id'], 'origin_model_id': origin_model_id, 'scope': scope, 'definition': definition,
               'cohort': cohort, 'cohort_history': [cohort], 'attempts': [], 'observations': [], 'message': '',
               'optimizer_system': (app.root / 'docs/prompt-optimization/optimizer-system.txt').read_text(encoding='utf-8'),
               'optimizer_user': (app.root / 'docs/prompt-optimization/optimizer-user-template.txt').read_text(encoding='utf-8')}
    Store(app.root).save(session)
    return session


def trial_key(session, candidate, model, case, repetition):
    return digest({'workflow': session['scope']['workflow_fingerprint'], 'candidate': candidate,
                   'model_identity': model['identity'], 'condition': projection(case, candidate, model['provider'] == 'perchance'),
                   'repetition': repetition})


def score(session, candidate, models, records, members=None):
    members = members if members is not None else session['scope']['layers'][-1]['members']
    by_key = {r['trial_key']: r for r in records if r['status'] in ('completed', 'timeout')}
    needed = {}
    summary = []
    for model in models:
        for member in members:
            case = session['scope']['cases'][member]
            keys = set()
            for repetition in range(case['test'].get('repetitions', 1)):
                key = trial_key(session, candidate, model, case, repetition)
                keys.add(key)
                needed[key] = by_key.get(key)
            present = [by_key[k] for k in keys if k in by_key]
            summary.append({'model_id': model['id'], 'case_id': member, 'recorded': len(present), 'required': len(keys),
                            'passes': sum(r.get('pass', False) for r in present),
                            'percentage': 100 * sum(r.get('pass', False) for r in present) / len(present) if present else None})
    recorded = [r for r in needed.values() if r is not None]
    passed = sum(bool(r.get('pass')) for r in recorded)
    return {'complete': bool(needed) and len(recorded) == len(needed), 'required': len(needed),
            'recorded': len(recorded), 'passes': passed, 'percentage': 100 * passed / len(recorded) if recorded else None,
            'summary': summary}


def top_three(session, models, records):
    ranked = []
    seen = set()
    for attempt in session['attempts']:
        candidate = attempt.get('candidate')
        if candidate is None or digest(candidate) in seen:
            continue
        seen.add(digest(candidate))
        result = score(session, candidate, models, records)
        if result['complete']:
            ranked.append({'attempt': attempt['number'], 'candidate': candidate, **result})
    return sorted(ranked, key=lambda item: (-item['percentage'], item['attempt']))[:3]


def view(app, session_id):
    store = Store(app.root)
    session = store.load(session_id)
    records = store.observations(session)
    models = session['cohort']['models']
    return {**session, 'top_three': top_three(session, models, records),
            'baseline': score(session, None, models, records),
            'attempts': [{**a, 'score': score(session, a['candidate'], models, records) if a.get('candidate') else None} for a in session['attempts']]}


def update_settings(app, session_id, value):
    """Explicit generator-only edits preserve test coverage and consumed attempts."""
    config = settings(value)
    store = Store(app.root)
    session = store.load(session_id)
    change = {'kind': 'generation_settings_change', 'previous': session['settings'], 'settings': config, 'at': now()}
    session.setdefault('configuration_history', []).append(store.evidence(session_id, change))
    session['settings'] = config
    session['updated'] = now()
    store.save(session)
    return session


def prune_order(history):
    def key(item):
        invalid = item.get('candidate') is None
        layer = item.get('layer', -1)
        percentage = item.get('score', {}).get('percentage')
        return (0 if invalid else 1, layer, percentage if percentage is not None else -1, item['number'])
    return sorted(history, key=key)


def generation_packet(session, models, records, store):
    top = top_three(session, models, records)
    protected_ids = {item['attempt'] for item in top}
    def trial_evidence(record):
        return {k: record.get(k) for k in ('model_id', 'case_id', 'repetition', 'status', 'pass', 'outputs', 'score', 'evaluation')} | {
            'calls': [{k: call.get(k) for k in ('step', 'request_messages', 'text', 'finish_reason', 'sampling', 'requested_sampling', 'applied_sampling')}
                      for call in record.get('calls', [])]}
    baseline = [trial_evidence(r) for r in records if r.get('candidate') is None]
    def detailed(attempt):
        item = copy.deepcopy(attempt)
        if item.get('candidate'):
            item['score'] = score(session, item['candidate'], models, records)
        evidence = item.get('response_evidence') or item.get('error_evidence')
        if evidence:
            item['generation'] = store.get_evidence(session['id'], evidence)
        item['trials'] = [trial_evidence(r) for r in records if r.get('candidate') == item.get('candidate') and item.get('candidate') is not None]
        return item
    history = [detailed(a) for a in session['attempts'] if a['number'] not in protected_ids]
    packet = {'experiment': session['definition']['id'], 'immutable_contract': session['definition']['candidate_control'],
              'required_labels': session['definition']['required_labels'], 'evaluation_policy': 'Unchanged objective oracles; benchmark reasoning off; full repetitions. Origin pass then complete task type on all current host models.',
              'current_machine_models': [{'id': m['id'], 'identity': m['identity'], 'provider': m['provider']} for m in models],
              'scope': {'type': 'Array move', 'cases': list(session['scope']['cases']), 'origin_model_id': session['origin_model_id']},
              'baseline_summary': score(session, None, models, records),
              'reference_evidence': baseline, 'top_three': top, 'history': history,
              'pruned_attempts': [], 'attempt_limit': session['settings']['max_attempts']}
    # Protected top-three exact templates and model/case summaries survive all pruning.
    return packet


def packet_messages(session, packet):
    import json
    return [{'role': 'system', 'content': session['optimizer_system']},
            {'role': 'user', 'content': session['optimizer_user'].replace('{{optimization_packet_json}}', json.dumps(packet, ensure_ascii=False, indent=2))}]


def fit_packet(session, packet, token_count, limits):
    packet = copy.deepcopy(packet)
    context, reserve = limits['context_tokens'], limits['output_reserve']
    removable = prune_order(packet['history'])
    while True:
        messages = packet_messages(session, packet)
        count = token_count(messages)
        if count + reserve <= context:
            return messages, {'input_tokens': count, 'output_reserve': reserve, 'context_tokens': context,
                              'pruned_attempts': packet['pruned_attempts']}
        if not removable:
            raise ValueError('Protected contract, baseline and top-three summaries exceed the generator context that fits this model/GPU. Nothing was truncated; use a generator with more capacity.')
        remove = removable.pop(0)
        packet['history'] = [a for a in packet['history'] if a['number'] != remove['number']]
        packet['pruned_attempts'].append(remove['number'])


def prepare_generation(session, packet, model, config, runtime, responses=()):
    limits = token_plan(model, packet_messages(session, packet), config['reasoning'], responses)
    ceiling = limits['native_tokens']
    load_attempts = []
    while True:
        allocated = limits['context_tokens']
        try:
            backend = runtime.generator(model, {**config, 'context_tokens': allocated})
        except DoesNotFit as exc:
            load_attempts.append({'context_tokens': allocated, 'status': 'gpu_memory_error',
                                  'error': str(exc), 'evidence': exc.evidence})
            ceiling = allocated // 2
            if ceiling < 1024:
                exc.evidence = {**exc.evidence, 'automatic_token_planning': load_attempts}
                raise
            limits['context_tokens'] = ceiling
            limits['output_reserve'] = min(limits['desired_output_reserve'], ceiling // 4)
            continue
        load_attempts.append({'context_tokens': allocated, 'status': 'loaded'})
        count = backend.token_count(packet_messages(session, packet))
        required = count + limits['output_reserve']
        if required > allocated and allocated < ceiling:
            limits['context_tokens'] = round_context(required, ceiling)
            limits['output_reserve'] = min(limits['desired_output_reserve'], limits['context_tokens'] // 4)
            continue
        try:
            messages, measured = fit_packet(session, packet, backend.token_count, limits)
        except ValueError as exc:
            exc.evidence = {'automatic_token_planning': load_attempts, 'plan': limits}
            raise
        context = {**limits, **measured, 'load_attempts': load_attempts,
                   'memory_context_ceiling': ceiling, 'output_limit_policy': 'EOS, deadline or remaining allocated context',
                   'output_tokens_available': allocated - measured['input_tokens'] - 32}
        return backend, messages, context


class Engine:
    def __init__(self, app, session_id, runtime_factory=None):
        self.app, self.store = app, Store(app.root)
        self.session = self.store.load(session_id)
        self.runtime_factory = runtime_factory or Runtime
        self.runtime = None
        self.records = self.store.observations(self.session)

    def save(self, status=None, message=None):
        if status is not None:
            self.session['status'] = status
        if message is not None:
            self.session['message'] = message
            self.app.message = message
        self.session['updated'] = now()
        self.store.save(self.session)

    def boundary(self):
        if self.app.cancel_event.is_set():
            raise Cancelled('Optimization stopped; saved terminal trials remain complete.')
        if self.app.pause_requested:
            self.app.state = 'paused'
            self.save('paused', 'Paused at an inference boundary. Resume continues missing work.')
            while not self.app.resume_event.wait(.2):
                if self.app.cancel_event.is_set():
                    raise Cancelled('Stopped while paused')
            if self.app.cancel_event.is_set():
                raise Cancelled('Stopped while paused')
            self.app.state = 'running'
            self.save('running')

    def evaluate(self, candidate, models, members):
        terminal = {r['trial_key'] for r in self.records if r['status'] in ('completed', 'timeout')}
        rejected = JudgementStore(self.app.root).read()['entries']
        for model in models:
            for member in members:
                case = self.session['scope']['cases'][member]
                if rejected.get(case['definition_id'], {}).get('blocked'):
                    raise ValueError('A frozen member is now rejected and cannot run: ' + member)
                for repetition in range(case['test'].get('repetitions', 1)):
                    self.boundary()
                    key = trial_key(self.session, candidate, model, case, repetition)
                    if key in terminal:
                        continue
                    self.app.set_progress('optimization', 'Testing ' + model['id'] + ': ' + member, 0, 0,
                                          'Repetition ' + str(repetition + 1) + '; benchmark reasoning off')
                    record = {'kind': 'trial', 'trial_key': key, 'candidate': candidate, 'model_id': model['id'],
                              'model_identity': model['identity'], 'case_id': member, 'repetition': repetition,
                              'test_definition': case['test'], 'variant_definition': case['variant'],
                              'started': now(), 'status': 'started', 'pass': False,
                              'timeout_seconds': 300 if model['provider'] == 'perchance' else 120}
                    record['coverage_aliases'] = [other for other, definition in self.session['scope']['cases'].items()
                                                  if repetition < definition['test'].get('repetitions', 1)
                                                  and trial_key(self.session, candidate, model, definition, repetition) == key]
                    # Save the intention before inference, including interruptions.
                    self.store.evidence(self.session['id'], record)
                    try:
                        outcome = self.runtime.evaluate(model, case, candidate, repetition)
                        record.update(outcome, status='completed', timed_out=False,
                                      **{'pass': bool(outcome.get('score', {}).get('exact_match'))})
                    except Exception as exc:
                        partial = getattr(exc, 'partial', {})
                        record.update(partial if isinstance(partial, dict) else {})
                        if getattr(exc, 'partial_response', None) and not record.get('calls'):
                            record['calls'] = [exc.partial_response]
                        timed_out = getattr(self.runtime, 'trial_started', True) and (
                            getattr(self.runtime.backend, 'timed_out', False) or type(exc).__name__ == 'PerchanceTimeout')
                        record.update(status='aborted' if isinstance(exc, Cancelled) else 'timeout' if timed_out else 'error',
                                      timed_out=timed_out, error=str(exc))
                        record['evaluation'] = assess_record(record)
                        record['finished'] = now()
                        evidence = self.store.evidence(self.session['id'], record)
                        self.session['observations'].append(evidence)
                        self.records.append(record)
                        self.save()
                        if not timed_out:
                            raise
                        self.runtime.close()
                    else:
                        record['evaluation'] = assess_record(record)
                        record['finished'] = now()
                        evidence = self.store.evidence(self.session['id'], record)
                        self.session['observations'].append(evidence)
                        self.records.append(record)
                        self.save()
                    terminal.add(key)

    def generate(self, models):
        self.boundary()
        generator = next((m for m in models if m['id'] == self.session['generator_id'] and m['provider'] == 'native'), None)
        if generator is None:
            raise ValueError('The selected generator is unavailable on this host. Saved candidates can still be evaluated here.')
        config = settings(self.session['settings'], allow_legacy=True)
        packet = generation_packet(self.session, models, self.records, self.store)
        responses = [self.store.get_evidence(self.session['id'], attempt['response_evidence'])
                     for attempt in self.session['attempts'] if attempt.get('response_evidence')]
        try:
            backend, messages, context = prepare_generation(self.session, packet, generator, config, self.runtime, responses)
        except Exception as exc:
            key = self.store.evidence(self.session['id'], {'kind': 'generation_preparation_error', 'at': now(),
                'error': str(exc), 'evidence': getattr(exc, 'evidence', {}),
                'load_metadata': copy.deepcopy(getattr(self.runtime.backend, 'load_metadata', {}))})
            self.session.setdefault('preparation_errors', []).append(key)
            self.save()
            raise
        random = secrets.SystemRandom()
        sampling = {'temperature': random.uniform(config['temperature_min'], config['temperature_max']),
                    'seed': random.randrange(2**32), 'top_p': 1, 'top_k': 0, 'min_p': 0}
        request = {'kind': 'generation_request', 'messages': messages, 'sampling': sampling, 'context': context,
                   'reasoning': config['reasoning'], 'generator_identity': generator['identity'], 'started': now(),
                   'load_metadata': copy.deepcopy(getattr(backend, 'load_metadata', {}))}
        attempt = {'number': len(self.session['attempts']) + 1, 'status': 'generating', 'layer': -1,
                   'request_evidence': self.store.evidence(self.session['id'], request)}
        self.session['attempts'].append(attempt)
        self.save('running', 'Generating candidate ' + str(attempt['number']))
        try:
            with backend.budget(300):
                response = backend.propose(messages, sampling, context['output_tokens_available'], self.app.cancel_event)
            attempt['response_evidence'] = self.store.evidence(self.session['id'], {'kind': 'generation_response', **response})
            if response.get('finish_reason') != 'stop':
                raise ValueError('Generator did not complete normally: ' + str(response.get('finish_reason')))
            candidate = parse_candidate(response['text'], self.session['definition']['required_labels'])
            attempt['candidate'] = candidate
            if any(a.get('candidate') == candidate for a in self.session['attempts'][:-1]):
                attempt.update(status='duplicate', feedback='Duplicate template pair; attempt saved, no duplicate trials or ranking slot.')
            else:
                attempt['status'] = 'evaluating'
        except ValueError as exc:
            attempt.update(status='invalid', feedback=str(exc))
        except Exception as exc:
            attempt.update(status='interrupted' if isinstance(exc, Cancelled) else 'generation_error', feedback=str(exc))
            attempt['error_evidence'] = self.store.evidence(self.session['id'], {'kind': 'generation_error', 'message': str(exc),
                'partial_response': getattr(exc, 'partial_response', {}), 'partial': getattr(exc, 'partial', {})})
            self.save()
            raise
        self.save()
        return attempt

    def run(self, mode='optimize', cohort=None):
        with review_lock(self.app.root):
            if code_fingerprint() != self.session['scope']['workflow_fingerprint']:
                raise ValueError('Workflow changed since this session was frozen; create a new reviewed session.')
            cohort = cohort or discover(self.app)
            # Optimization resumes use their original local cohort. Cross-machine
            # evaluation deliberately establishes a new local comparison cohort.
            if mode == 'evaluate_remaining':
                self.session['cohort'] = cohort
                self.session['cohort_history'].append(cohort)
            else:
                identities = {m['identity'] for m in cohort['models']}
                if any(m['identity'] not in identities for m in self.session['cohort']['models']):
                    raise ValueError('A frozen host model is unavailable. Restore it, or use Evaluate remaining on this machine; it cannot silently leave the cohort.')
                by_identity = {m['identity']: m for m in cohort['models']}
                cohort = {**cohort, 'models': [by_identity[m['identity']] for m in self.session['cohort']['models']]}
                self.session['cohort'] = cohort
            if not cohort['models']:
                raise ValueError('No runnable models on the execution host.')
            for attempt in self.session['attempts']:
                if attempt['status'] == 'generating':
                    attempt.update(status='interrupted', feedback='Previous process ended after saving this generation request. No completed proposal was recorded; this attempt remains consumed.')
            self.runtime = self.runtime_factory(self.app, cohort)
            self.app.pause_requested = False
            self.app.resume_event.set()
            self.save('running')
            try:
                full = self.session['scope']['layers'][-1]['members']
                origin = self.session['scope']['layers'][0]['members']
                remote_models = [m for m in cohort['models'] if m['provider'] == 'perchance']
                candidates = [None] + [a['candidate'] for a in self.session['attempts'] if a.get('candidate') and
                                      (mode == 'evaluate_remaining' or a['status'] == 'evaluating')]
                ranked = top_three(self.session, cohort['models'], self.records)
                future_generation = (mode == 'optimize' and len(self.session['attempts']) < self.session['settings']['max_attempts']
                                     and not (ranked and ranked[0]['percentage'] == 100))
                remote_pending = bool(remote_models) and (future_generation or any(not score(self.session, candidate, remote_models, self.records)['complete'] for candidate in candidates))
                if remote_pending:
                    from workbench.perchance_setup import prepare
                    from workbench.perchance import MODEL_ID
                    prepare(self.app, selection={'model_id': MODEL_ID}, force_pending=True)
                    self.session['perchance_setup'] = copy.deepcopy(self.app.perchance_setup_decision)
                    if self.app.perchance_setup_decision['status'] in ('declined', 'failed'):
                        # Keep the frozen provider in coverage, but do native work.
                        models = [m for m in cohort['models'] if m['provider'] != 'perchance']
                    else:
                        models = cohort['models']
                else:
                    models = cohort['models']
                if mode == 'evaluate_remaining':
                    self.evaluate(None, models, full)
                    for attempt in self.session['attempts']:
                        if attempt.get('candidate') and attempt['status'] != 'duplicate':
                            self.evaluate(attempt['candidate'], models, full)
                    complete = all(score(self.session, a['candidate'], cohort['models'], self.records)['complete']
                                   for a in self.session['attempts'] if a.get('candidate') and a['status'] != 'duplicate')
                    self.save('finished' if complete else 'pending', 'Saved candidates evaluated on this host; no new generation attempts. Unavailable provider work remains pending.')
                    return
                # Baseline is pinned to the original definitions, not a generated
                # template. All candidate comparisons use identical cohort/cases.
                self.evaluate(None, models, full)
                while True:
                    self.boundary()
                    attempt = next((a for a in self.session['attempts'] if a['status'] == 'evaluating'), None)
                    ranked = top_three(self.session, cohort['models'], self.records)
                    if ranked and ranked[0]['percentage'] == 100:
                        self.save('perfect', '100% on every required current-host trial. Other hosts can evaluate remaining later.')
                        break
                    if attempt is None:
                        if len(self.session['attempts']) >= self.session['settings']['max_attempts']:
                            self.save('attempt_limit', 'Attempt limit reached. All proposals and evidence retained.')
                            break
                        attempt = self.generate(cohort['models'])
                    if attempt['status'] != 'evaluating':
                        continue
                    origin_models = [m for m in cohort['models'] if m['id'] == self.session['origin_model_id']]
                    if not origin_models:
                        raise ValueError('The starting-case model is unavailable on this host.')
                    self.evaluate(attempt['candidate'], [m for m in models if m['id'] == self.session['origin_model_id']], origin)
                    result = score(self.session, attempt['candidate'], origin_models, self.records, origin)
                    attempt['layer'] = 0
                    if not result['complete']:
                        self.save('pending', 'Provider work remains pending; resume on this host to finish the origin gate.')
                        break
                    if result['percentage'] != 100:
                        attempt.update(status='origin_failed', feedback='Starting case did not pass all configured repetitions on the selected starting model.')
                        self.save()
                        continue
                    attempt['layer'] = 1
                    self.evaluate(attempt['candidate'], models, full)
                    result = score(self.session, attempt['candidate'], cohort['models'], self.records)
                    if not result['complete']:
                        self.save('pending', 'Full task-type coverage is incomplete. No partial candidate enters the top three.')
                        break
                    attempt.update(status='complete', feedback='Full task type evaluated; rank by pooled current-host success percentage.')
                    self.save()
            except Cancelled:
                self.save('stopped', 'Stopped. Resume keeps completed pass/fail/timeout observations and consumed attempts.')
                raise
            except Exception as exc:
                self.save('blocked', str(exc))
                raise
            finally:
                self.runtime.close()


def dispatch(app, payload):
    mode = payload.get('mode', 'optimize')
    if mode not in ('optimize', 'evaluate_remaining'):
        raise ValueError('Unknown optimizer operation')
    session_id = payload.get('session_id')
    if session_id is None:
        session_id = create(app, {k: v for k, v in payload.items() if k in ('generator_id', 'origin_model_id', 'settings')})['id']
    Engine(app, session_id).run(mode)
