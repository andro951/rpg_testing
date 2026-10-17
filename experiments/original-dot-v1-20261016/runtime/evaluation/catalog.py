"""Explicit per-definition registrations and variant coverage, outside inference identity."""
from pathlib import Path
from workbench.domain import read_json


def catalog():
    return read_json(Path(__file__).with_name('catalog.json'))


def registration(test_id, variant_id):
    for definition in catalog()['definitions']:
        if definition['id'] == test_id:
            if variant_id not in definition['variants']:
                raise ValueError('Unregistered evaluator variant: ' + variant_id)
            return definition
    raise ValueError('Unregistered evaluator definition: ' + test_id)
