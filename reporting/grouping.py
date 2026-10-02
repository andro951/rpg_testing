"""Reporting metadata lives outside execution specs and never changes case identity."""
from functools import lru_cache
import json
from pathlib import Path
from workbench.domain import digest, experiment_spec


AXES = ('ability_category', 'task_type', 'prompt_comparison_set', 'test_version', 'input_presentation')


@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name('grouping_metadata.json').read_text(encoding='utf-8'))


def row_grouping(test, variant, test_id, variant_id):
    """Use reviewed labels; guard comparison sets against different fixtures/oracles."""
    entry = catalog().get(test_id, {}).get(variant_id)
    reviewed = entry is not None and entry.get('reviewed_definition') == digest(experiment_spec(test, variant))
    if entry is None:
        presentation = variant.get('state_presentation', test.get('state_presentation', 'unknown'))
        entry = dict(ability_category='Other objective tests', task_type=test_id,
                     prompt_comparison_set=test.get('name', test_id), test_version=variant_id,
                     input_presentation={'raw_json': 'Normal JSON', 'indexed_arrays': 'Indexed arrays',
                                         'full_paths': 'Full paths'}.get(presentation, 'Unspecified'))
    result = {axis: {'key': entry[axis], 'label': entry[axis]} for axis in AXES}
    fixture = {'source': test.get('source'), 'expected_state': test.get('expected_state'),
               'answers': variant.get('expected_answers'), 'result': variant.get('result')}
    # Instructions and presentation can vary in a comparison; the required answer cannot.
    result['prompt_comparison_set']['key'] += ':' + digest(fixture)
    # Embedded prompts can carry source data too. Only reviewed definitions may
    # share a comparison set; edited/unknown historical definitions stay separate.
    if not reviewed:
        result['prompt_comparison_set']['key'] += ':unreviewed:' + digest(experiment_spec(test, variant))
    return result