"""Explicit, capability-aware remote text provider; native inference identity is untouched."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from .judgements import load_tests, guarded_run, JudgementStore, definition_id
from .domain import canonical, digest, code_fingerprint, experiment_spec, device_tier, write_json
from .planning import validate_selection
from .workflows import messages, condition, output_schema, evaluate, Cancelled, repetition_seed
from .scoring import parse

MODEL_ID = 'perchance-text-generator'
TIMEOUT_SECONDS = 300
VERSION = 'perchance-capability-baseline-v1'
DEFAULT_URL = 'https://perchance.org/056uh2nc6k'
WORKER = Path(__file__).resolve().parents[1] / 'tools/perchance-text/worker.js'
UNAVAILABLE = ('temperature', 'top_p', 'top_k', 'min_p', 'seed', 'repeat_penalty',
               'cache', 'cache_verification', 'constrained_decoding', 'context_allocation',
               'gpu_placement', 'remote_model_identity', 'token_timings')


def selected(selection):
    return bool(selection and selection.get('model_id') == MODEL_ID)


def model():
    return {'id': MODEL_ID, 'base_model': 'Perchance Text Generator', 'quantization': 'Remote service',
            'required_vram_gb': 8, 'provider': 'perchance', 'enabled': True}


def validate_url(value):
    url = urlsplit(value)
    if url.scheme != 'https' or url.hostname != 'perchance.org' or url.username or url.password or url.port or not url.path.strip('/') or url.fragment:
        raise ValueError('Use an HTTPS Perchance generator URL without credentials, port or fragment')
    return value


def identity(settings):
    files = [Path(__file__), WORKER]
    return {'provider': 'Perchance Text Generator', 'policy': VERSION,
            'worker_url': validate_url(settings.get('perchance_url', DEFAULT_URL)),
            'epoch': settings.get('perchance_epoch', '1'),
            'adapter_hash': digest({p.name: hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in files}),
            'workflow_code': code_fingerprint(), 'remote_model': None,
            'capability_evidence': {'reviewed': '2026-10-01', 'source': 'tools/perchance-text/worker.js',
                                    'reason': 'Worker forwards instruction/startWith/hideStartWith/stopSequences/onChunk only; no verified experimental controls'},
            'capabilities': {key: 'unavailable_in_adapter' for key in UNAVAILABLE}}


def effective(test, variant):
    t, v = copy.deepcopy(test), copy.deepcopy(variant)
    t.pop('variants', None)
    for key in ('id', 'name', 'description', 'enabled', 'repetitions', 'provenance', 'timeout_seconds'):
        t.pop(key, None)
        v.pop(key, None)
    v['cache'] = 'default'
    v.pop('min_cached_tokens', None)
    v.setdefault('prompt_style', 'conversational_v2')
    v.setdefault('state_presentation', test.get('state_presentation', 'indexed_arrays'))
    def walk(steps):
        for step in steps:
            step.pop('sampling', None)
            if step.get('type') == 'loop':
                walk(step['steps'])
    walk(v['steps'])
    return {'test': t, 'variant': v}


def plan(tests, settings, target, store, selection):
    validate_selection(selection, [model()], tests)
    provider = identity(settings)
    groups = {}
    for test in sorted(tests, key=lambda item: item['id']):
        if not test.get('enabled', True):
            continue
        for variant in sorted(test['variants'], key=lambda item: item['id']):
            if not variant.get('enabled', True):
                continue
            definition = effective(test, variant)
            #Client GPU/OS are provenance, not applied remote model conditions.
            cid = digest({'provider': provider, 'effective': definition})
            group = groups.setdefault(cid, {'case_id': cid, 'test': copy.deepcopy(test), 'variant': variant,
                                           'effective': definition, 'aliases': []})
            group['test']['timeout_seconds'] = TIMEOUT_SECONDS
            for rep in range(test.get('repetitions', 1)):
                group['aliases'].append({'test_id': test['id'], 'variant_id': variant['id'], 'repetition': rep,
                    'requested_id': digest({'provider': provider, 'definition': experiment_spec(test, variant), 'repetition': rep}),
                    'requested_definition': experiment_spec(test, variant),
                    'requested_timeout_seconds': test['timeout_seconds'],
                    'observation_id': cid, 'collapsed_dimensions': list(UNAVAILABLE)})
    jobs, complete, requested = [], 0, 0
    for group in groups.values():
        matching = [a for a in group['aliases'] if
                    ('test_id' not in selection or a['test_id'] == selection['test_id']) and
                    ('test_ids' not in selection or a['test_id'] in selection['test_ids']) and
                    ('variant_id' not in selection or a['variant_id'] == selection['variant_id'])]
        if not matching:
            continue
        group['selected_aliases'] = [a['requested_id'] for a in matching]
        requested += len(matching)
        group['done'] = store.done(MODEL_ID, group['case_id'])
        complete += int(group['done'])
        jobs.append(group)
    return {'provider': provider, 'target': target, 'selection': copy.deepcopy(selection), 'groups': jobs,
            'requested_cases': requested, 'independent_observations': len(jobs),
            'collapsed_cases': requested - len(jobs), 'feature_only_cases': 0, 'complete': complete,
            'pending': len(jobs) - complete, 'remote_provider': True}


def browser_executable(settings):
    explicit = settings.get('perchance_browser', '')
    if explicit:
        return str(Path(explicit)) if Path(explicit).is_file() else None
    candidates = [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                  r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                  r'C:\Program Files\Google\Chrome\Application\chrome.exe']
    return next((p for p in candidates if Path(p).is_file()), None) or next(
        (p for name in ('chromium', 'chromium-browser', 'google-chrome') if (p := shutil.which(name))), None)


def preflight(app, preparation=None, selection=None):
    from .inventory import detect_gpus
    issues = []
    tests = load_tests(app.root / 'test_specs')
    validate_selection(selection, [model()], tests)
    if preparation:
        gpu = {'name': preparation['gpu_name'], 'total_gib': preparation['vram_gb'], 'driver': None}
    else:
        try:
            gpus = detect_gpus()
            if len(gpus) != 1:
                raise ValueError('Exactly one visible GPU is required for the 8 GB assignment')
            gpu = gpus[0]
        except Exception as exc:
            issues.append({'id': 'perchance_gpu', 'message': str(exc), 'level': 'blocked'})
            gpu = {'name': 'Unavailable', 'total_gib': 0, 'driver': None}
    tier = device_tier(gpu['total_gib'], gpu['name'])
    if tier != 8:
        issues.append({'id': 'perchance_tier', 'message': 'Perchance is assigned strictly to an 8 GB worker; larger tiers are excluded.', 'level': 'blocked'})
    target = {'backend': 'perchance', 'vram_gb': tier or gpu['total_gib'], 'gpu_name': gpu['name'],
              'os': platform.platform(), 'execution_class': 'remote_service', 'execution_policy': VERSION}
    result = plan(tests, app.settings, target, app.store, selection)
    if result['pending']:
        if importlib.util.find_spec('playwright') is None:
            issues.append({'id': 'perchance_dependency', 'message': 'Perchance needs its browser dependency. Open Worker setup and use Install optional Perchance dependency.',
                           'level': 'blocked', 'label': 'Open Perchance setup', 'action': {'type': 'setup'}})
        if not browser_executable(app.settings):
            issues.append({'id': 'perchance_browser', 'message': 'Install Edge/Chrome or configure an existing browser executable in Perchance setup.',
                           'level': 'blocked', 'label': 'Open Perchance setup', 'action': {'type': 'setup'}})
        try:
            with tempfile.TemporaryFile(dir=app.store.root):
                pass
        except OSError as exc:
            issues.append({'id': 'perchance_storage', 'message': str(exc), 'level': 'blocked'})
    for p in (app.store.root / MODEL_ID).glob('*.json'):
        try:
            app.store.read(p)
        except (ValueError, TypeError, KeyError) as exc:
            issues.append({'id': 'corrupt_' + p.stem, 'message': str(exc), 'level': 'blocked',
                           'label': 'Delete corrupted result', 'action': {'type': 'delete_corrupt', 'model_id': MODEL_ID, 'case_id': p.stem}})
    public = {k: v for k, v in result.items() if k != 'groups'}
    public['groups'] = [{'model_id': MODEL_ID, 'pending': result['pending'], 'complete': result['complete'],
                         'reason': f"{result['requested_cases']} requested cases → {result['independent_observations']} independent observations; unsupported controls collapsed"}]
    return {'ready': not issues and not preparation, 'prepared': not issues and bool(preparation),
            'preparation_only': bool(preparation), 'remote_provider': True, 'selection': selection,
            'issues': issues, 'plan': public, 'gpu': gpu, 'folder': {'path': None, 'source': 'Remote service: no GGUFs'},
            'note': 'Remote service conditions; sampling/cache/model defaults are unavailable. Browser/site readiness is verified at session start.'}, result


class PerchanceTimeout(RuntimeError):
    pass


class BrowserBackend:
    """All Playwright operations occur on the run thread; cancel only sets a signal."""
    def __init__(self, settings):
        self.settings = settings
        self.cancel_requested = False
        self.page = self.frame = self.context = self.playwright = None
        self.deadline = None
        self.environment = {}
        self.temp = None

    def open(self):
        from playwright.sync_api import sync_playwright
        profile = self.settings.get('perchance_profile')
        self.temp = None if profile else tempfile.TemporaryDirectory(prefix='rpg-perchance-')
        profile = profile or self.temp.name
        self.playwright = sync_playwright().start()
        self.context = self.playwright.chromium.launch_persistent_context(profile,
            executable_path=browser_executable(self.settings), headless=self.settings.get('perchance_headless', False),
            viewport={'width': 1100, 'height': 800})
        self.reset()

    def reset(self):
        if self.page:
            self.page.close()
        self.page = self.context.new_page()
        self.page.goto(validate_url(self.settings.get('perchance_url', DEFAULT_URL)), wait_until='domcontentloaded', timeout=60000)
        started = time.monotonic()
        while time.monotonic() - started < self.settings.get('perchance_ready_seconds', 90):
            if self.cancel_requested:
                raise Cancelled('Stopped during Perchance startup')
            for frame in self.page.frames:
                try:
                    if frame.evaluate("() => typeof (globalThis.root?.aiTextPlugin || globalThis.root?.$moduleSpace?.['ai-text-plugin'] || globalThis.aiTextPlugin) === 'function'"):
                        frame.evaluate(WORKER.read_text(encoding='utf-8'))
                        self.frame = frame
                        self.environment = frame.evaluate('() => RpgPerchanceText.Environment()')
                        return
                except Exception:
                    continue
            self.page.wait_for_timeout(100)
        detail = 'Perchance page did not expose the text plugin; check its saved imports and Internet/site readiness'
        if 'verification' in self.page.title().lower() or 'just a moment' in self.page.title().lower():
            detail = 'Perchance security verification blocked startup. Use Verify Perchance connection with a visible window to complete verification manually. No generation ran.'
        raise RuntimeError(detail)

    def cancel(self):
        self.cancel_requested = True

    def close(self):
        try:
            if self.context:
                self.context.close()
        finally:
            try:
                if self.playwright:
                    self.playwright.stop()
            finally:
                if self.temp:
                    self.temp.cleanup()
                self.context = self.page = self.frame = self.playwright = None

    def generate(self, prompt, requested, schema, cancel):
        instruction = '\n\n'.join(f"{message['role'].upper()}:\n{message['content']}" for message in prompt)
        jid = uuid.uuid4().hex
        start = time.perf_counter()
        snapshot = {'text': '', 'chunks': [], 'state': 'running'}
        def call():
            return {'text': snapshot.get('text', ''), 'finish_reason': 'provider_completed' if snapshot.get('state') == 'completed' else snapshot.get('state'),
                    'request_seconds': time.perf_counter() - start,
                    'first_visible_text_seconds': snapshot.get('firstVisibleMs') / 1000 if snapshot.get('firstVisibleMs') is not None else None,
                    'first_token_seconds': None, 'usage': {}, 'timings': {}, 'cached_tokens': None,
                    'raw_chunks': snapshot.get('chunks', []), 'provider_result': snapshot,
                    'effective_instruction': instruction, 'serializer_version': 'role-labels-v1',
                    'requested_sampling': requested, 'sampling': None, 'applied_sampling': None,
                    'schema_requested': schema, 'constrained_decoding': False,
                    'environment': copy.deepcopy(self.environment)}
        try:
            self.frame.evaluate('(job) => RpgPerchanceText.Start(job)', {'id': jid, 'instruction': instruction})
            while True:
                snapshot = self.frame.evaluate('(id) => RpgPerchanceText.Snapshot(id)', jid)
                stopped = self.cancel_requested or bool(cancel and cancel.is_set())
                expired = self.deadline is not None and time.monotonic() >= self.deadline
                if stopped or expired:
                    error = Cancelled('Stopped by user') if stopped else PerchanceTimeout('Workflow deadline exceeded')
                    error.partial_response = call()
                    try:
                        self.frame.evaluate('(id) => RpgPerchanceText.Cancel(id)', jid)
                    finally:
                        self.page.close(); self.page = self.frame = None
                    raise error
                if snapshot['state'] == 'completed':
                    return call()
                if snapshot['state'] != 'running':
                    raise RuntimeError(snapshot.get('error') or 'Perchance job did not complete')
                self.page.wait_for_timeout(50)
        except Exception as exc:
            if not hasattr(exc, 'partial_response'):
                exc.partial_response = call()
            raise


def execute_job(job, backend, cancel, progress=None):
    from jsonschema import Draft202012Validator
    test, variant = job['test'], job['variant']
    values, calls, events = {}, [], []
    started = time.perf_counter()
    error = None
    def partial():
        return {'calls': calls, 'outputs': values, 'step_events': events, 'pipeline_seconds': time.perf_counter() - started}
    def walk(steps, iteration=0):
        for step in steps:
            if cancel.is_set():
                raise Cancelled('Stopped')
            if not condition(step.get('when'), values):
                events.append({'step': step['id'], 'status': 'skipped', 'iteration': iteration})
                continue
            if step['type'] == 'loop':
                iterations = 0
                for number in range(step['max_iterations']):
                    if condition(step.get('until'), values):
                        break
                    walk(step['steps'], number + 1)
                    iterations += 1
                events.append({'step': step['id'], 'status': 'loop_finished', 'iterations': iterations})
                continue
            if progress:
                progress(step['id'])
            prompt = messages(test, step, values, variant)
            schema = output_schema(step.get('output', {'type': 'text'}))
            requested = {'temperature': 0, 'top_p': 1, 'top_k': 0, 'min_p': 0, 'seed': 42, **step.get('sampling', {})}
            try:
                response = backend.generate(prompt, requested, schema, cancel)
            except Exception as exc:
                if hasattr(exc, 'partial_response'):
                    calls.append({'step': step['id'], 'iteration': iteration, 'messages': prompt, **exc.partial_response})
                raise
            calls.append({'step': step['id'], 'iteration': iteration, 'messages': prompt, **response})
            if response.get('finish_reason') != 'provider_completed':
                raise ValueError('Provider did not complete the text request')
            value = response['text'] if schema is None else parse(response['text'])
            if schema is not None:
                Draft202012Validator(schema).validate(value)
            values[step['id']] = value
            if step.get('assign'):
                values[step['assign']] = value
            events.append({'step': step['id'], 'status': 'completed', 'iteration': iteration})
    from jsonschema.exceptions import ValidationError
    try:
        walk(variant['steps'])
    except (ValueError, KeyError, TypeError, ValidationError) as exc:
        error = str(exc)
    except Exception as exc:
        exc.partial = partial()
        raise
    result = partial()
    scoring = time.perf_counter()
    result['score'] = {'valid': False, 'exact_match': False, 'error': error} if error else evaluate(test, variant, values)
    result.update(scoring_seconds=time.perf_counter() - scoring, cache_mode='provider_default_unknown',
                  cache_verified=None, measurement_valid=True, sampling_seed_policy='unavailable; repetitions collapsed',
                  feature_applicability={'cache_control': False, 'seed_control': False, 'constrained_decoding': False},
                  gpu_memory=None)
    return result


@guarded_run
def run(app, report, pending, backend_factory=BrowserBackend, append=False):
    entries = JudgementStore(app.root).read()['entries']
    jobs = [g for g in pending['groups'] if not g['done'] and not entries.get(definition_id(g['test'], g['variant']), {}).get('blocked')]
    if not append:
        app.run_total = len(jobs); app.run_processed = 0
    artifact = app.data / 'perchance-plans' / (uuid.uuid4().hex + '.json')
    write_json(artifact, pending)
    if not jobs:
        return
    if app.cancel_event.is_set():
        raise Cancelled('Stopped before opening Perchance')
    backend = backend_factory({**app.settings, 'perchance_profile': str(app.data / 'perchance-profile')})
    app.backend = backend
    try:
        backend.open()
        for job in jobs:
            if app.cancel_event.is_set():
                raise Cancelled('Stopped')
            while app.pause_requested:
                if app.cancel_event.wait(.1):
                    raise Cancelled('Stopped while paused')
                app.state = 'paused'
            app.state = 'running'
            if getattr(backend, 'page', True) is None:
                backend.reset()
            backend.deadline = time.monotonic() + job['test']['timeout_seconds']
            record = {'case_id': job['case_id'], 'model_id': MODEL_ID, 'model_name': 'Perchance Text Generator',
                      'test_id': job['test']['id'], 'variant_id': job['variant']['id'], 'repetition': 0,
                      'target': pending['target'], 'test_definition': job['test'], 'variant_definition': job['variant'],
                      'effective_definition': job['effective'], 'aliases': job['aliases'],
                      'selected_aliases': job['selected_aliases'], 'capability_policy': pending['provider'],
                      'artifact_identity': pending['provider'], 'execution_class': 'remote_service', 'simulated': False,
                      'valid_for_full_gpu_comparison': False, 'policy': VERSION,
                      'load': {'environment': copy.deepcopy(backend.environment), 'context': {}, 'placement': {}},
                      'timeout_seconds': job['test']['timeout_seconds'], 'started_at': utc_now(),
                      'provenance': {'workflow_code': code_fingerprint(), 'provider': 'perchance', 'remote_model': None}}
            path = app.store.path(MODEL_ID, job['case_id'])
            if path.exists():
                prior = app.store.read(path)
                record['attempts'] = prior.get('attempts', []) + [{k: v for k, v in prior.items() if k != 'attempts'}]
            app.current = {'model': MODEL_ID, 'test': record['test_id'], 'variant': record['variant_id'], 'stage': 'generating'}
            stopped = None
            try:
                app.timing_active = True
                record.update(status='completed', **execute_job(job, backend, app.cancel_event,
                    lambda step: app.set_progress('run', 'Perchance text generation', None, app.run_overall_percent(), step)))
                app.completed_now += 1
            except PerchanceTimeout as exc:
                record.update(status='completed', timed_out=True, reason='case_timeout', error=str(exc),
                              **getattr(exc, 'partial', {}), measurement_valid=True,
                              score={'valid': False, 'exact_match': False, 'error': str(exc)})
                app.completed_now += 1
            except Cancelled as exc:
                record.update(status='aborted', **getattr(exc, 'partial', {}), error=str(exc), measurement_valid=False)
                stopped = exc
            except Exception as exc:
                record.update(status='error', **getattr(exc, 'partial', {}), error=str(exc), measurement_valid=False)
                app.session_errors += 1
                if getattr(backend, 'page', None):
                    backend.page.close(); backend.page = backend.frame = None
            finally:
                app.timing_active = False
            record['finished_at'] = utc_now()
            app.store.save(record); app.run_processed += 1
            app.log('case', f"{record['case_id']} {record['status']} remote_service")
            app.flush_logs()
            if stopped:
                raise stopped
            # This batch contains one provider; stop-after-model finishes its cases.
    finally:
        app.timing_active = False
        backend.close(); app.backend = None


def verify_connection(app):
    """Explicit setup action; establishes the owned profile without inference."""
    backend = BrowserBackend({**app.settings, 'perchance_headless': False,
                              'perchance_profile': str(app.data / 'perchance-profile'),
                              'perchance_ready_seconds': 180})
    app.backend = backend
    try:
        app.message = 'Opening Perchance connection setup. Complete any site verification in the worker window.'
        backend.open()
        app.log('perchance_connection', canonical(backend.environment))
        app.message = 'Perchance text plugin is ready. Connection setup made no generation requests.'
    finally:
        backend.close(); app.backend = None


def utc_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
