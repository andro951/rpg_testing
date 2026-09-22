"""Pure scheduling, persistence and workflow validation; no inference or network."""
from __future__ import annotations
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any

TIERS = (8, 12, 16, 24, 32, 40, 48, 80)
ENGINE_VERSION = 'seeded-repetitions-1'


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def read_json(path: Path) -> Any:
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError(f'Duplicate JSON key: {k}')
            out[k] = v
        return out
    def bad(value):
        raise ValueError(f'Invalid JSON number: {value}')
    result = json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=pairs, parse_constant=bad)
    canonical(result)
    return result


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def safe_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}', value):
        raise ValueError('IDs must contain only letters, numbers, dots, dashes and underscores')
    return value


def device_tier(capacity: float, gpu_name: str = "") -> int | None:
    """Round only known nominal capacities (ECC reporting), not arbitrary shortages."""
    if re.fullmatch(r'(?:NVIDIA\s+)?L4',gpu_name.strip(),re.I) and 21<=capacity<=24.48:return 24
    for tier in (8, 11, 12, 16, 24, 32, 40, 48, 80):
        if tier * .98 <= capacity <= tier * 1.02:
            return tier
    return None


def eligibility(required: int | None, capacity: float) -> str | None:
    if required not in TIERS:
        return None
    actual = device_tier(capacity)
    if actual == required:
        return 'assigned tier'
    if required == 8 and actual == 11:
        return 'one-tier-up comparison (11 GB opportunity)'
    i = TIERS.index(required)
    if i + 1 < len(TIERS) and actual == TIERS[i + 1]:
        return 'one-tier-up comparison'
    return None


def recommend_vram(size_bytes: int) -> int | None:
    needed = size_bytes / 2**30 * 1.10 + 1.5
    return next((tier for tier in TIERS if tier >= needed), None)


def code_fingerprint():
    """Only experiment-affecting implementation, not CSS or laptop paths."""
    base=Path(__file__).parent
    return digest({name:hashlib.sha256((base/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                   for name in ('domain.py','workflows.py','scoring.py','backends.py','inventory.py','presentation.py','seedcheck.py','native.py','scheduler.py','execution_policy.py','telemetry.py')})


def experiment_spec(test: dict, variant: dict) -> dict:
    """Only this variant and shared experimental fields, not neighboring variants/UI labels."""
    presentation = {'variants', 'repetitions', 'enabled', 'name', 'description'}
    return {'test': {k: v for k, v in test.items() if k not in presentation},
            'variant': {k: v for k, v in variant.items() if k not in {'enabled', 'name', 'description'}}}


def case_id(model: dict, test: dict, variant: dict, repetition: int, target: dict) -> str:
    identity = {'engine': ENGINE_VERSION, 'workflow_code': code_fingerprint(), 'model': model['id'],
                'artifact_pin': model.get('artifact_identity') or model.get('sha256', {}), 'experiment': experiment_spec(test, variant),
                'repetition': repetition, 'target': target}
    return digest(identity)


class ResultStore:
    """Files are authoritative. Deleting a file makes its case pending. No tracker."""
    def __init__(self, root: Path):
        self.root = root

    def path(self, model_id: str, cid: str) -> Path:
        safe_id(model_id)
        if not re.fullmatch(r'[0-9a-f]{64}', cid):
            raise ValueError('Invalid case ID')
        return self.root / model_id / f'{cid}.json'

    def read(self, path: Path) -> dict:
        record = read_json(path)
        if not isinstance(record,dict):raise ValueError('Result must be a JSON object')
        checksum = record.pop('sha256', None)
        if checksum != digest(record):
            raise ValueError(f'Checksum mismatch: {path.name}')
        if record.get('status') not in ('completed', 'skipped', 'error', 'aborted'):
            raise ValueError(f'Unknown result status: {path.name}')
        if path.stem != record.get('case_id') or path.parent.name != record.get('model_id'):
            raise ValueError('Result identity does not match its filename')
        record['sha256'] = checksum
        return record

    def done(self, model_id: str, cid: str) -> bool:
        path = self.path(model_id, cid)
        return path.exists() and self.read(path)['status'] in ('completed','skipped')

    def save(self, record: dict) -> Path:
        record = dict(record)
        record.pop('sha256', None)
        path = self.path(record['model_id'], record['case_id'])
        if path.exists():
            previous = self.read(path)
            if previous['status'] == 'completed':
                raise ValueError('Refusing to overwrite a completed result; delete it to rerun')
            # Keep earlier infrastructure/abort evidence in the authoritative file.
            # Deleting the case still removes its completion state and all attempts.
            history = list(previous.pop('attempts', []))
            previous.pop('sha256', None)
            history.append(previous)
            record['attempts'] = history
        if record['status'] not in ('completed', 'skipped', 'error', 'aborted'):
            raise ValueError('Unknown status')
        record = {'status': record.pop('status'), **record}
        write_json(path, {**record, 'sha256': digest(record)})
        return path

    def all(self) -> list[dict]:
        return [self.read(p) for p in sorted(self.root.glob('*/*.json'))]


def local_schema(schema):
    """Never resolve network/file references from a test definition."""
    if isinstance(schema,dict):
        for key,value in schema.items():
            if key in ('$ref','$dynamicRef') and (not isinstance(value,str) or not value.startswith('#')):
                raise ValueError('JSON schemas must use local # references only')
            local_schema(value)
    elif isinstance(schema,list):
        for item in schema:local_schema(item)


def validate_test(test: dict) -> None:
    from jsonschema import Draft202012Validator
    safe_id(test['id'])
    if test.get('schema_version') != 2 or test.get('workflow') != 'steps':
        raise ValueError('Expected schema_version 2 and workflow steps')
    for prohibited in ('max_output_tokens', 'max_tokens', 'context_tokens', 'context_length'):
        if prohibited in test:
            raise ValueError(f'{prohibited} is automatic, not a test setting')
    if type(test.get('repetitions', 1)) is not int or test.get('repetitions', 1) < 1:
        raise ValueError('repetitions must be positive')
    if type(test.get('timeout_seconds')) is not int or test['timeout_seconds'] < 1:
        raise ValueError('timeout_seconds must be a positive integer')
    if not isinstance(test.get('source'), dict) or not isinstance(test.get('variants'), list) or not test['variants']:
        raise ValueError('Test needs source and nonempty variants')
    if test.get('state_presentation','indexed_arrays') not in ('raw_json','indexed_arrays'):
        raise ValueError('Unknown state presentation')
    if 'expected' in test['source'] or 'expected_state' in test['source']:
        raise ValueError('Ground truth must not be placed in source')
    schema = test.get('state_schema')
    if schema:
        local_schema(schema)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        validator.validate(test['source']['initial_state'])
        if 'expected_state' in test:
            validator.validate(test['expected_state'])
    variants = set()
    def steps(items, known):
        if not isinstance(items, list) or not items:
            raise ValueError('Workflow needs steps')
        local = set()
        for s in items:
            if set(s) - {'id','type','prompt','output','sampling','uses','when','assign','steps','max_iterations','until'}:
                raise ValueError('Unknown step setting; context/output limits are automatic')
            sid = safe_id(s['id'])
            if sid in local or sid in known:
                raise ValueError('Duplicate step ID')
            local.add(sid)
            when = s.get('when')
            if when and (when.get('step') not in known or 'equals' not in when):
                raise ValueError('Condition references an unavailable step')
            if s.get('type') == 'loop':
                if not isinstance(s.get('until'), dict) or 'equals' not in s['until']:
                    raise ValueError('A loop requires an explicit until condition')
                if type(s.get('max_iterations')) is not int or not 1 <= s['max_iterations'] <= 10:
                    raise ValueError('Loops require 1..10 iterations')
                steps(s['steps'], known)
                if s.get('until', {}).get('step') not in known:
                    raise ValueError('Loop stop condition references missing step')
            elif s.get('type') == 'generate':
                if not isinstance(s.get('prompt'), str):
                    raise ValueError('Prompt must be text')
                if any(ref not in known for ref in s.get('uses', [])):
                    raise ValueError('Step references unavailable output')
                output = s.get('output', {'type': 'text'})
                if output.get('type') not in ('text', 'json', 'boolean', 'string', 'enum'):
                    raise ValueError('Unknown output type')
                if output.get('type') == 'enum' and not output.get('values'):
                    raise ValueError('Enum requires choices')
                if 'schema' in output:
                    local_schema(output['schema'])
                    Draft202012Validator.check_schema(output['schema'])
                settings = s.get('sampling', {})
                if set(settings) - {'temperature', 'top_p', 'top_k', 'min_p', 'seed', 'repeat_penalty'}:
                    raise ValueError('Unknown sampling setting; no output/context caps')
                for key, val in settings.items():
                    if type(val) not in (int, float) or not math.isfinite(val):
                        raise ValueError('Sampling settings must be finite numbers')
                if settings.get('temperature', 0) < 0 or not 0 < settings.get('top_p', 1) <= 1:
                    raise ValueError('Invalid sampling range')
                if type(settings.get('top_k',0)) is not int or settings.get('top_k',0)<0 or not 0<=settings.get('min_p',0)<=1 or settings.get('repeat_penalty',1)<=0:
                    raise ValueError('Invalid sampler parameter')
                if type(settings.get('seed', 42)) is not int or not 0 <= settings.get('seed', 42) <= 0xFFFFFFFF:
                    raise ValueError('Seed must be an unsigned 32-bit integer')
            else:
                raise ValueError('Unknown step type')
            known.add(sid)
            if s.get('assign'):
                if s['assign'] not in known:
                    raise ValueError('assign can only replace an existing step output')
    for variant in test['variants']:
        safe_id(variant['id'])
        if variant['id'] in variants:
            raise ValueError('Duplicate variant')
        variants.add(variant['id'])
        if variant.get('cache', 'default') not in ('default', 'on', 'off'):
            raise ValueError('Unknown cache mode')
        if variant.get('state_presentation',test.get('state_presentation','indexed_arrays')) not in ('raw_json','indexed_arrays'):
            raise ValueError('Unknown state presentation')
        known = set()
        steps(variant['steps'], known)
        result = variant.get('result', {})
        if result.get('step') and result['step'] not in known:
            raise ValueError('Result references missing step')
        if result.get('representation', 'json_patch') not in ('json_patch', 'semantic', 'state', 'answers'):
            raise ValueError('Unknown result representation')
        required_ops=result.get('required_ops')
        if required_ops is not None:
            allowed={'add','remove','replace','move','copy','test'}
            if result.get('representation','json_patch')!='json_patch' or not isinstance(required_ops,list) or not required_ops or any(op not in allowed for op in required_ops):
                raise ValueError('required_ops must be a nonempty list of RFC 6902 operations for json_patch results')
        for check in variant.get('checks', []):
            if check.get('step') not in known or check.get('operator') not in ('equals', 'contains', 'not_contains'):
                raise ValueError('Invalid objective check')


def load_tests(folder: Path) -> list[dict]:
    tests = [read_json(p) for p in sorted(folder.glob('*.json'))]
    ids = set()
    for test in tests:
        validate_test(test)
        if test['id'] in ids:
            raise ValueError('Duplicate test ID across files')
        ids.add(test['id'])
    return [t for t in tests if t.get('enabled', True)]
