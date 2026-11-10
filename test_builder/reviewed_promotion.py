"""Explicit versioned OPRO wrappers; the original control renderer stays frozen."""
import copy
import re
from optimization.templates import render
from workbench.domain import digest, validate_test
from .normal_prompt import _validate_candidate


def validate(promotion):
    if not isinstance(promotion, dict) or set(promotion) != {'schema_version', 'id', 'method', 'operation', 'candidate', 'provenance'}:
        raise ValueError('A reviewed promotion needs its version, scope, candidate and provenance')
    if promotion['schema_version'] != 1 or promotion['method'] != 'dot_patch_v1' or promotion['operation'] != 'move':
        raise ValueError('Unsupported reviewed promotion version, method or operation')
    if not isinstance(promotion['id'], str) or not re.fullmatch(r'[a-z0-9_-]+', promotion['id']):
        raise ValueError('Invalid reviewed promotion identity')
    _validate_candidate(promotion['candidate'])
    provenance = promotion['provenance']
    if not isinstance(provenance, dict) or provenance.get('candidate_sha256') != digest(promotion['candidate']):
        raise ValueError('Reviewed candidate checksum mismatch')
    validation = provenance.get('validation', {})
    if validation.get('complete') is not True or validation.get('passes') != 36 or validation.get('required') != 36:
        raise ValueError('Promotion requires complete successful 36-observation Move evidence')
    if provenance.get('review_status') != 'accepted' or not provenance.get('session_id') or not provenance.get('approval_basis'):
        raise ValueError('Promotion needs an accepted review and recorded approval basis')
    return promotion


def apply_to_test(test, promotion, reviews=None):
    validate(promotion)
    if test['prompt_builder']['method'] != promotion['method']:
        raise ValueError('Reviewed promotion method does not match the test')
    if test['prompt_builder']['operation'] != promotion['operation']:
        return test
    result = copy.deepcopy(test)
    # Preserve the historical winner and its evidence; correct only template prose
    # before binding literal data into newly generated prompts.
    candidate = copy.deepcopy(promotion['candidate'])
    candidate['system'] = candidate['system'].replace(
        'Flattened slash paths are an input display format, not the output path format. Interpret their components and construct the required output paths.',
        'Flattened input paths use the same dot-path rules as output operation paths.')
    candidate['user'] = candidate['user'].replace(
        'Use the required output path syntax even when the input displays slash paths.',
        'Use the same dot-path syntax for flattened input paths and output operation paths.')
    requests = {}
    for variant in result['variants']:
        request = render(candidate, {**variant['prompt_bindings'], 'prior_outputs': '{}'})
        if [m['role'] for m in request] != ['system', 'user']:
            raise ValueError('A normal promoted prompt needs one system and one user message')
        requests[variant['id']] = request
        if len(variant['steps']) != 1 or variant['steps'][0]['type'] != 'generate':
            raise ValueError('Reviewed database promotion requires a single generation step')
        variant['steps'][0]['prompt'] = request[-1]['content']
    systems = {request[0]['content'] for request in requests.values()}
    if len(systems) != 1:
        raise ValueError('Normal system instructions must not vary with the input presentation')
    result['instructions'] = next(iter(systems))
    proof = digest(requests)
    review = (reviews or {}).get(result['id'], {})
    approved = all(review.get(role, {}).get('prompt_digest') == proof and review.get(role, {}).get('status') == 'accepted'
                   for role in ('assistant', 'isaac'))
    result['enabled'] = approved
    result['description'] = 'Reviewed OPRO Move wrapper over the original dot-path database control.'
    builder = result['prompt_builder']
    builder['control_prompt_provenance'] = builder.pop('baseline_provenance')
    builder['reviewed_prompt_promotion'] = {'id': promotion['id'], 'provenance': copy.deepcopy(promotion['provenance'])}
    builder['reviewed_prompt_promotion']['input_path_correction'] = {
        'version': 'dot-full-paths-input-v1', 'applied_candidate_sha256': digest(candidate),
        'historical_candidate_unchanged': True, 'exact_winner_messages': False}
    builder['template_sha256'] = digest({'base_template_sha256': builder['template_sha256'], 'candidate': candidate})
    builder.update(prompt_digest=proof, review_status='accepted' if approved else 'needs_review')
    validate_test(result)
    return result
