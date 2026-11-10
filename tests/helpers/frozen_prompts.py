"""Read immutable saved definitions and synthetic references, never rebuild them."""
import copy
from functools import lru_cache
from pathlib import Path
from workbench.domain import read_json

REPO = Path(__file__).resolve().parents[2]
INPUTS = REPO / 'archives/prompt-builder-inputs'


@lru_cache(maxsize=1)
def snapshots():
    return read_json(INPUTS / 'frozen_definitions.json')


def definition(fixture_id, method='value_patch'):
    return copy.deepcopy(snapshots()['methods'][method][fixture_id]['definition'])


def reference(fixture_id, method='value_patch'):
    row = snapshots()['methods'][method][fixture_id]
    return copy.deepcopy((row['response'], row['expected_state']))


def historical_suite():
    """Root definitions move to this archive when the new template suite activates."""
    archived = REPO / 'archives/pre-template-builder/test_specs'
    return archived if archived.exists() else REPO / 'test_specs'
