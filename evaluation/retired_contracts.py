"""Retirement metadata only; old response contracts are never decoded or regraded."""

REPRESENTATIONS = frozenset({'ember_text_v1', 'field_value_v2'})
EVALUATORS = frozenset({'schema-free-intent-v1', 'array-identities-intent-v1',
                        'array-identities-intent-v2'})


class RetiredContractError(ValueError):
    """A captured contract is viewable, but cannot be used for new evaluation."""


def reason(result):
    representation = result.get('representation')
    evaluator = result.get('evaluator')
    version = evaluator.get('version') if isinstance(evaluator, dict) else evaluator
    name = representation if representation in REPRESENTATIONS else version if version in EVALUATORS else None
    if name is None:
        return None
    return (f'Retired response contract {name} is unsupported for execution or regrading. '
            'Saved scores and raw evidence remain available unchanged. '
            'Compile a new definition with the current intent evaluator for new work.')


def require_supported(result):
    message = reason(result)
    if message:
        raise RetiredContractError(message)


def configuration_score(result):
    message = reason(result)
    evaluator = result.get('evaluator')
    requested = evaluator if isinstance(evaluator, dict) else {}
    return {'valid': False, 'exact_match': None, 'status': 'configuration_error',
            'error': message, 'contract_status': 'retired',
            'evaluation': {**requested, 'accepted': False, 'failure_stage': 'configuration',
                           'semantic_status': 'not_evaluated', 'error': message}}
