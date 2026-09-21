"""Native unattended-run policy. These are operational safeguards, not output caps."""
from __future__ import annotations
import re
from .domain import digest

POLICY_VERSION = 'native-two-pass-v1'
LOAD_TIMEOUT_SECONDS = 180
PRIMARY_CASE_SECONDS = 600
RECOVERY_CASE_SECONDS = 300
MAX_CONTEXT_EXPANSIONS = 2
MAX_RECOVERY_LOADS = 4

class RunFailure(RuntimeError):
    reason = 'runtime_error'
    recoverable = False
    def __init__(self, message, evidence=None):
        super().__init__(message)
        self.evidence = evidence or {}

class DoesNotFit(RunFailure):
    reason = 'gpu_memory'
    recoverable = True

class CPUOffload(DoesNotFit):
    reason = 'cpu_offload'

class UnverifiedPlacement(RunFailure):
    reason = 'placement_unverified'

class RuntimeStall(RunFailure):
    reason = 'runtime_stall'

class ContextCapacity(RunFailure):
    reason = 'context_capacity'
    def __init__(self, message, required_tokens=None, evidence=None):
        super().__init__(message, evidence)
        self.required_tokens = required_tokens


def placement(lines):
    """Backend evidence, not a claim of zero CPU activity or Windows residency proof."""
    ratio = None; cpu_kv = []; cpu_compute = []
    for line in lines:
        match = re.search(r'\boffloaded\s+(\d+)\s*/\s*(\d+)\s+layers?\s+to\s+GPU', line, re.I)
        if match:
            loaded, total = map(int, match.groups())
            if 0 <= loaded <= total and total > 0:
                ratio = {'gpu_layers': loaded, 'total_layers': total, 'cpu_layers': total-loaded, 'line': line}
        if re.search(r'\bCPU\s+KV\s+(?:buffer|cache)', line, re.I) and not re.search(r'\b0\.0+\s+MiB', line):
            cpu_kv.append(line)
        # Host-pinned CUDA_Host/CPU_Mapped buffers alone are not CPU model execution.
        if re.search(r'\bCPU\s+compute\s+buffer', line, re.I) and not re.search(r'\b0\.0+\s+MiB', line):
            cpu_compute.append(line)
    result = {'status': 'unverified', 'gpu_layers': None, 'total_layers': None, 'cpu_layers': None,
              'cpu_kv_evidence': cpu_kv, 'cpu_compute_evidence': cpu_compute,
              'scope': 'backend-reported model layers and placement diagnostics; not independent OS allocation verification'}
    if ratio:
        result.update(ratio)
        result['status'] = 'cpu_offloaded' if ratio['cpu_layers'] or cpu_kv or cpu_compute else 'full_gpu'
    return result


def classify_load_failure(message):
    if re.search(r'out of memory|cuda.*alloc|failed to allocate|not enough (?:device |GPU )?memory|VK_ERROR_OUT_OF_DEVICE_MEMORY', message, re.I):
        return DoesNotFit(message)
    return RunFailure(message)


def recovery_layers(total_layers):
    """Finite GPU+CPU trials, never a hidden all-CPU fallback."""
    if type(total_layers) is not int or total_layers < 2:
        return []
    return list(dict.fromkeys(max(1, min(total_layers-1, int(total_layers*f))) for f in (.75, .5, .25, .1)))[:MAX_RECOVERY_LOADS]


def fallback_id(primary_id):
    return digest({'primary_case_id': primary_id, 'execution_class': 'cpu_offloaded', 'policy': POLICY_VERSION})


def next_context(context, required=None):
    current, maximum = context['allocated_tokens'], context['native_tokens']
    desired = max(current*2, (required or 0)+4096)
    value = min(maximum, 1 << (max(1, desired)-1).bit_length())
    if value <= current:
        return None
    return {**context, 'allocated_tokens': value, 'expanded_from': current,
            'output_cap': None, 'reason': 'automatic context-capacity recovery'}
