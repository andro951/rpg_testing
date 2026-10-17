"""Automatic generator allocation; estimates are verified by the native tokenizer."""
import math


def native_limit(model):
    limits = [int(value) for key, value in model.get('metadata', {}).items()
              if key.endswith('.context_length') and type(value) in (int, float)
              and math.isfinite(value) and value >= 1024]
    if not limits:
        raise ValueError('The generator model has no usable context metadata. Rescan its model files.')
    return min(limits)


def round_context(required, maximum):
    return min(maximum, max(min(8192, maximum), 1 << (max(1, required) - 1).bit_length()))


def plan(model, messages, reasoning=False, responses=()):
    maximum = native_limit(model)
    input_bytes = sum(len(message['content'].encode('utf-8')) + 128 for message in messages)
    previous_bytes = max((sum(len(response.get(key, '').encode('utf-8')) for key in ('text', 'reasoning_text')
                              if isinstance(response.get(key, ''), str)) for response in responses), default=0)
    allowance = min(maximum // 4, max(8192 if reasoning else 4096, math.ceil(previous_bytes / 2) + 512))
    context = round_context(math.ceil(input_bytes / 3) + allowance + 512, maximum)
    return {'policy': 'automatic-generator-tokens-v1', 'native_tokens': maximum,
            'context_tokens': context, 'output_reserve': min(allowance, context // 4),
            'desired_output_reserve': allowance, 'input_estimate_bytes': input_bytes,
            'prior_output_bytes': previous_bytes,
            'estimate_method': 'UTF-8 input bytes / 3; prior output bytes / 2; exact tokenizer verification before generation'}