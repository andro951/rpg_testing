"""Read-only views of remote trials, including the former repetition-collapse policy."""
from .domain import digest

LEGACY_POLICY = 'perchance-capability-baseline-v1'
LEGACY_ADAPTER_HASH = '5d9c66643a60542ac665cd45a6dc216d1517cc23c21a2edba78a7c69b03a3730'


def observation_aliases(record):
    aliases = record.get('aliases', [])
    policy = record.get('capability_policy', {})
    if policy.get('policy') == LEGACY_POLICY:
        # Old repetition aliases are not new trials under the revised user rule.
        return [a for a in aliases if a.get('repetition') == record.get('repetition', 0)]
    return aliases


def model_conditions(record):
    policy = record.get('capability_policy', {})
    return {k: policy.get(k) for k in ('provider', 'worker_url', 'epoch', 'workflow_code', 'remote_model')}


def requested_case_keys(records):
    return {digest({'provider': model_conditions(r), 'definition': a.get('requested_definition'),
                    'test_id': a.get('test_id'), 'variant_id': a.get('variant_id'), 'repetition': a.get('repetition')})
            if isinstance(a.get('requested_definition'), dict) else a['requested_id']
            for r in records for a in observation_aliases(r)}
