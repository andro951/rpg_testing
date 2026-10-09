"""Host-local model discovery and isolated generator/test execution adapters."""
import copy
import re
import time
from contextlib import nullcontext
from workbench import inventory
from workbench.domain import device_tier, digest
from workbench.native import NativeBackend, _template_compatible_messages
from workbench.workflows import execute
from .templates import bindings, render


def discover(app):
    if app.demo:
        models = app.demo_models()
        gpu = {'name': 'SIMULATED 8 GB GPU', 'total_gib': 8}
    else:
        gpus = inventory.detect_gpus()
        if len(gpus) != 1:
            raise ValueError('Prompt optimization requires exactly one visible GPU on the execution host.')
        gpu = gpus[0]
        folder = app.settings.get('model_root')
        if not folder:
            raise ValueError('Choose the host models folder in Worker setup first.')
        models = inventory.scan_models(folder, app.catalog())
    tier = device_tier(gpu['total_gib'], gpu['name'])
    available, excluded = [], []
    for model in models:
        item = copy.deepcopy(model)
        reason = None
        if not item.get('complete') or item.get('errors'):
            reason = 'Missing or invalid model artifacts'
        elif not item.get('catalog', {}).get('enabled', True):
            reason = 'Disabled model'
        elif item.get('required_vram_gb') is None:
            reason = 'Assign this model a memory budget in Installed models first'
        elif item['required_vram_gb'] > tier:
            reason = 'Model memory assignment exceeds this host'
        elif not app.demo and not inventory.executable('llama-server', app.settings.get('llama_path', '')):
            reason = 'Native GPU runtime unavailable'
        if reason:
            excluded.append({'id': item['id'], 'reason': reason})
            continue
        item['provider'] = 'native'
        item['identity'] = digest({'id': item['id'], 'artifact': app.identify_artifact(item),
                                   'runtime': app.backend_version(), 'policy': 'full_gpu_reasoning_off'}) if not app.demo else digest({'id': item['id'], 'simulated': True})
        available.append(item)
    if tier == 8 and not app.demo:
        from workbench import perchance
        item = perchance.model()
        item['name'] = 'Perchance Text Generator'
        item['identity'] = digest({'provider': 'perchance', 'url': app.settings.get('perchance_url'),
                                   'epoch': app.settings.get('perchance_epoch'), 'worker': perchance.WORKER.read_text(encoding='utf-8')})
        available.append(item)
    def parameter_count(item):
        text = str(item.get('name', item['id'])) + ' ' + ' '.join(item.get('paths', []))
        return max([float(x) for x in re.findall(r'(\d+(?:\.\d+)?)[bB](?:\b|[-_])', text)] or [0])
    qwen = [m for m in available if m['provider'] == 'native' and re.search(r'qwen[\s._-]*3[._]5', str(m), re.I)]
    preferred = max(qwen, key=parameter_count)['id'] if qwen else None
    return {'models': available, 'excluded': excluded, 'gpu': gpu, 'default_generator': preferred,
            'simulated': app.demo, 'scope': 'origin pass, then all Array move JSON Patch tests on every listed host model'}


class GeneratorBackend(NativeBackend):
    """Reasoning is independently enabled only on the optimizer process."""
    def __init__(self, settings, gpu, log, reasoning=False):
        super().__init__(settings, gpu, log)
        self.reasoning = reasoning

    def launch_arguments(self, *args, **kwargs):
        arguments = super().launch_arguments(*args, **kwargs)
        arguments[arguments.index('--reasoning') + 1] = 'on' if self.reasoning else 'off'
        return arguments

    def token_count(self, messages):
        effective, _ = _template_compatible_messages(messages, self.load_metadata.get('properties', {}))
        text = self.transport.request('/apply-template', {'messages': effective})['prompt']
        return len(self.transport.request('/tokenize', {'content': text, 'add_special': True})['tokens'])

    def propose(self, messages, sampling, output_limit, cancel):
        effective, adaptation = _template_compatible_messages(messages, self.load_metadata.get('properties', {}))
        body = {'model': self.owned_id, 'messages': effective, **sampling, 'max_tokens': output_limit,
                'stream': True, 'stream_options': {'include_usage': True}, 'cache_prompt': False, 'id_slot': 0}
        result = self.transport.request('/v1/chat/completions', body, stream=True, cancel=cancel)
        return {**result, 'request_messages': effective, 'message_adaptation': adaptation}


class CandidateBackend:
    def __init__(self, underlying, case, candidate, remote=False):
        self.underlying, self.case, self.candidate, self.remote = underlying, case, candidate, remote
        self.stage = None
        self.prior = {}
        self.supports_cache = not remote
        self.supports_schema = not remote

    def clear_cache(self):
        return self.underlying.clear_cache()

    def generate(self, messages, settings, schema, cache='default', cancel=None):
        effective = messages
        if self.candidate is not None and self.stage == self.case['variant']['result']['step']:
            effective = render(self.candidate, bindings(self.case, self.prior))
        if self.remote:
            result = self.underlying.generate(effective, settings, schema, cancel)
            result = {**result, 'provider_finish_reason': result.get('finish_reason'),
                      'finish_reason': 'stop' if result.get('finish_reason') == 'provider_completed' else result.get('finish_reason')}
        else:
            result = self.underlying.generate(effective, settings, schema, cache, cancel)
        self.prior[self.stage] = result['text']
        return {**result, 'request_messages': result.get('request_messages', effective),
                'original_messages': messages, 'benchmark_reasoning': 'unverified' if self.remote else 'off'}


class Runtime:
    def __init__(self, app, cohort):
        self.app, self.cohort = app, cohort
        self.backend = None
        self.loaded = None
        self.trial_started = False

    def close(self):
        if self.backend:
            if hasattr(self.backend, 'unload'):
                self.backend.unload()
            else:
                self.backend.close()
        self.backend = self.app.backend = self.loaded = None

    def load(self, model, generator=False, settings=None):
        settings = settings or {}
        key = (model['identity'], generator, settings.get('reasoning', False), settings.get('context_tokens', 32768))
        if self.loaded == key:
            return self.backend
        self.close()
        if model['provider'] == 'perchance':
            from workbench.perchance_connection import ControlledBrowserBackend
            config = {**self.app.settings, 'perchance_profile': str(self.app.data / 'perchance-controlled-profile')}
            self.backend = ControlledBrowserBackend(config)
            self.app.backend = self.backend
            self.backend.open()
        else:
            if self.app.demo:
                from workbench.demo_native import DemoNative
                self.backend = DemoNative(self.app.settings, self.cohort['gpu'], self.app.log)
            elif generator:
                self.backend = GeneratorBackend(self.app.settings, self.cohort['gpu'], self.app.log, settings['reasoning'])
            else:
                self.backend = NativeBackend(self.app.settings, self.cohort['gpu'], self.app.log)
            self.app.backend = self.backend
            context = settings.get('context_tokens', 32768)
            limits = [int(v) for k, v in model.get('metadata', {}).items() if k.endswith('.context_length') and isinstance(v, (int, float))]
            if limits and context > max(limits):
                raise ValueError('Requested context exceeds the model metadata context limit.')
            self.backend.load(model, {'allocated_tokens': context}, self.app.cancel_event)
        self.loaded = key
        return self.backend

    def generator(self, model, settings):
        if self.app.demo:
            raise ValueError('Live prompt generation is unavailable in Demo; use the automated mock smoke tests.')
        return self.load(model, True, settings)

    def evaluate(self, model, case, candidate, repetition):
        self.trial_started = False
        from workbench.inventory import automatic_context
        context = automatic_context([case['test']], model.get('metadata', {}))['allocated_tokens'] if model['provider'] == 'native' else 32768
        backend = self.load(model, settings={'context_tokens': context})
        remote = model['provider'] == 'perchance'
        wrapped = CandidateBackend(backend, case, candidate, remote)
        if remote:
            if backend.frame is None:
                backend.reset()
            backend.deadline = time.monotonic() + 300
        budget = nullcontext() if remote else backend.budget(120)
        with budget:
            self.trial_started = True
            result = execute(case['test'], case['variant'], wrapped, self.app.cancel_event,
                             on_stage=lambda stage: setattr(wrapped, 'stage', stage), repetition=repetition)
        return {**result, 'load_metadata': copy.deepcopy(getattr(backend, 'load_metadata', getattr(backend, 'environment', {}))),
                'timeout_seconds': 300 if remote else 120, 'benchmark_reasoning': 'unverified' if remote else 'off'}
