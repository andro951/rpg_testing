"""Explicit evaluator dispatch. No implicit changes to frozen test contracts."""
from . import live_intent, schema_free_intent, array_identities_intent


def selected(result):
    evaluator = result.get('evaluator')
    if isinstance(evaluator, dict) and evaluator.get('version') == array_identities_intent.VERSION:
        return array_identities_intent
    if isinstance(evaluator, dict) and evaluator.get('version') == schema_free_intent.VERSION:
        return schema_free_intent
    return live_intent
