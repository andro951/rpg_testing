"""Independent suite contract and exact coverage accounting. No model inference."""
from __future__ import annotations

from pathlib import Path
from workbench.domain import read_json, safe_id
from .presentation import has_array

SCHEMA_VERSION = 1
DIMENSIONS = ('test_cases', 'input_formats', 'output_formats')
CATEGORIES = dict(zip(DIMENSIONS, ('test_cases', 'input_format', 'output_format')))


def names(value, label):
    if not isinstance(value, list) or not value or any(not isinstance(v, str) for v in value):
        raise ValueError(label + ' must be a nonempty list')
    for value_id in value:
        safe_id(value_id)
    if len(set(value)) != len(value):
        raise ValueError('Duplicate selection in ' + label)
    return list(value)


def contract(root):
    """A missing required folder must not silently shrink the discovered suite.

    The reviewed minimum lives in editable JSON, independently of selection.json.
    New case folders and active output folders extend it without Python edits.
    """
    from .builder import configuration, discover
    root = Path(root)
    policy = read_json(root / 'common/coverage.json')
    if policy.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('Missing or invalid current suite coverage contract')
    found = discover(root)
    expected = {}
    for key, category in CATEGORIES.items():
        required = names(policy.get(key), 'coverage.' + key)
        missing = sorted(set(required) - set(found[category]))
        if missing:
            raise ValueError('Required ' + category + ' folders missing: ' + ', '.join(missing))
        if key == 'test_cases':
            active = found[category]
        elif key == 'output_formats':
            active = []
            for name in found[category]:
                status = configuration(root, category, name).get('status', 'active')
                if status not in ('active', 'historical', 'experimental'):
                    raise ValueError('Invalid output format status: ' + name)
                if status == 'active':
                    active.append(name)
            if set(required) - set(active):
                raise ValueError('Required output formats must remain active')
        else:
            active = [name for name in found[category]
                      if configuration(root, category, name).get('status') == 'active']
        expected[key] = sorted(set(required) | set(active))
    return expected


def resolve(root, *, cases=None, input_formats=None, output_formats=None):
    from .builder import discover
    expected = contract(root)
    defaults = read_json(Path(root) / 'common/selection.json')
    arguments = dict(test_cases=cases, input_formats=input_formats, output_formats=output_formats)
    found = discover(root)
    selected = {}
    for key, arg in arguments.items():
        chosen = names(defaults.get(key) if arg is None else arg, key)
        unknown = sorted(set(chosen) - set(found[CATEGORIES[key]]))
        if unknown:
            raise ValueError('Unknown ' + key + ': ' + ', '.join(unknown))
        if arg is None and set(chosen) != set(expected[key]):
            raise ValueError('Default ' + key + ' must cover the complete current suite; missing: '
                             + ', '.join(sorted(set(expected[key]) - set(chosen)))
                             + '; noncurrent: ' + ', '.join(sorted(set(chosen) - set(expected[key])))
                             + '. Use explicit selectors for a subset or historical/experimental formats.')
        selected[key] = chosen
    return selected, sorted(key for key, arg in arguments.items() if arg is not None)


def matrix(root, selection):
    """Return intended prompt identities and justified input non-applicability."""
    from .builder import configuration
    root = Path(root)
    skip = read_json(root / 'common/selection.json').get('skip_id_keyed_when_no_arrays', True)
    if type(skip) is not bool:
        raise ValueError('skip_id_keyed_when_no_arrays must be boolean')
    views = set()
    exclusions = []
    variants = {}
    for case in selection['test_cases']:
        state = read_json(root / 'test_cases' / case / 'starting_data.json')
        modes = []
        for mode in selection['input_formats']:
            serializer = configuration(root, 'input_format', mode)['serializer']
            if skip and serializer == 'id_keyed_arrays' and not has_array(state):
                exclusions.append({'test_case': case, 'input_format': mode,
                                   'reason': 'No arrays: keyed-array input duplicates normal JSON',
                                   'output_formats': sorted(selection['output_formats'])})
            else:
                modes.append(mode)
        variants[case] = sorted(modes)
        for mode in modes:
            for form in selection['output_formats']:
                views.add((case, mode, form))
    return views, exclusions, variants


def _summary(selection, views, repetitions):
    return {**{key: sorted(selection[key]) for key in DIMENSIONS},
            'test_case_count': len(selection['test_cases']),
            'input_format_count': len(selection['input_formats']),
            'output_format_count': len(selection['output_formats']),
            'test_definition_count': len({(c, o) for c, _, o in views}),
            'distinct_prompt_count': len(views),
            'repetitions_per_prompt': repetitions,
            'observations_per_model': len(views) * repetitions}


def report(root, selected, prompts, unsupported, repetitions, explicit_selectors):
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError('repetitions must be a positive integer')
    expected = contract(root)
    expected_views, exclusions, variants = matrix(root, expected)
    requested_views, requested_exclusions, _ = matrix(root, selected)
    actual_views = set()
    for row in prompts:
        key = (row['test_case'], row['input_format'], row['output_format'])
        if key in actual_views or key not in requested_views or row.get('repetitions') != repetitions:
            raise ValueError('Manifest prompt scope or repetitions mismatch')
        if row.get('test_id') != key[0] + '__' + key[2]:
            raise ValueError('Manifest prompt test identity mismatch')
        actual_views.add(key)
    unsupported_views = set()
    seen = set()
    for row in unsupported:
        key = (row['test_case'], row['output_format'])
        if (key in seen or key[0] not in selected['test_cases'] or key[1] not in selected['output_formats']
                or not isinstance(row.get('reason'), str) or not row['reason']):
            raise ValueError('Invalid unsupported coverage entry')
        seen.add(key)
        unsupported_views.update(v for v in requested_views if (v[0], v[2]) == key)
    if actual_views & unsupported_views or actual_views | unsupported_views != requested_views:
        raise ValueError('Manifest is missing requested prompt combinations')
    omitted = expected_views - requested_views
    missing = expected_views - actual_views
    extras = actual_views - expected_views
    complete = not missing
    scope = ('full' if not extras else 'extended') if complete else ('subset' if omitted else 'incomplete')
    actual = {key: sorted({v[i] for v in actual_views}) for i, key in enumerate(DIMENSIONS)}
    return {'schema_version': SCHEMA_VERSION, 'scope': scope, 'complete': complete,
            'explicit_selectors': sorted(explicit_selectors),
            'expected': {**_summary(expected, expected_views, repetitions),
                         'input_variants_by_case': variants,
                         'candidate_prompt_count': len(expected['test_cases']) * len(expected['input_formats']) * len(expected['output_formats'])},
            'actual': _summary(actual, actual_views, repetitions),
            'omitted': {**{key: sorted(set(expected[key]) - set(selected[key])) for key in DIMENSIONS},
                        'distinct_prompt_count': len(omitted), 'observations_per_model': len(omitted) * repetitions},
            'missing_distinct_prompt_count': len(missing),
            'extra_distinct_prompt_count': len(extras),
            'unsupported': list(unsupported),
            'unsupported_distinct_prompt_count': len(unsupported_views),
            'input_exclusions': exclusions,
            'selected_input_exclusions': requested_exclusions,
            'noncurrent_output_formats': [{'output_format': name,
                                          'status': read_json(Path(root) / 'output_format' / name / 'format.json').get('status', 'active')}
                                         for name in sorted(set(selected['output_formats']) - set(expected['output_formats']))]}


def validate_manifest(manifest, root):
    """Recompute coverage from current sources, never trust a 'complete' label."""
    from .builder import applicable, load_case, source_hashes
    from evaluation import array_identities_intent as evaluator
    if manifest.get('source_hashes') != source_hashes(root):
        raise ValueError('Build sources are stale or changed; rebuild before installing or running all tests')
    if manifest.get('evaluator') != evaluator.configuration():
        raise ValueError('Build evaluator is stale; rebuild before installing or running all tests')
    coverage = manifest.get('coverage', {})
    explicit = coverage.get('explicit_selectors')
    if not isinstance(explicit, list) or len(set(explicit)) != len(explicit) or set(explicit) - set(DIMENSIONS):
        raise ValueError('Missing or invalid coverage selection metadata; rebuild the suite')
    selected = {key: names(manifest.get(key), key) for key in DIMENSIONS}
    args = {'cases': selected['test_cases'] if 'test_cases' in explicit else None,
            'input_formats': selected['input_formats'] if 'input_formats' in explicit else None,
            'output_formats': selected['output_formats'] if 'output_formats' in explicit else None}
    resolved, _ = resolve(root, **args)
    if selected != resolved:
        raise ValueError('Manifest selection differs from its recorded scope')
    unsupported = []
    for name in selected['test_cases']:
        case = load_case(name, root)
        for form in selected['output_formats']:
            reason = applicable(case, form, root)
            if reason:
                unsupported.append({'test_case': name, 'output_format': form, 'reason': reason})
    if manifest.get('unsupported') != unsupported:
        raise ValueError('Manifest unsupported coverage differs from current capabilities')
    actual = report(root, selected, manifest.get('prompts', []), unsupported,
                    manifest.get('repetitions'), explicit)
    if actual != coverage:
        raise ValueError('Manifest coverage is stale or tampered; rebuild the suite')
    if (manifest.get('prompt_count') != actual['actual']['distinct_prompt_count']
            or manifest.get('observations_per_model') != actual['actual']['observations_per_model']):
        raise ValueError('Manifest prompt/observation counts do not match actual coverage')
    return actual


def runtime_report(repository, selection=None, tests=None):
    """Validate active coverage; all-tests execution fails closed on a subset.

    Unrelated legacy/example harnesses with no template-suite markers are unchanged.
    An explicit test selection may run a verified partial installed suite.
    """
    root = Path(repository)
    templates = root / 'prompt_builder/templates'
    manifest_path = root / 'prompts/current-suite/manifest.json'
    if not templates.exists() and not manifest_path.exists():
        return None
    if not manifest_path.is_file():
        raise ValueError('Current suite coverage manifest is missing; rebuild and install the complete suite')
    manifest = read_json(manifest_path)
    coverage = validate_manifest(manifest, templates)
    from .builder import validate_artifacts
    validate_artifacts(root, manifest, prompt_base=root / 'prompts/current-suite', installed=True)
    targeted = bool(selection and any(k in selection for k in ('test_id', 'test_ids', 'variant_id')))
    if not targeted and not coverage['complete']:
        raise ValueError('Run all requires complete current coverage: '
                         + str(coverage['missing_distinct_prompt_count'])
                         + ' distinct prompts are missing. Rebuild/install the full suite or explicitly select tests.')
    if tests is None:
        from workbench.judgements import load_tests
        tests = load_tests(root / 'test_specs')
    if tests is not None:
        available = {(t['id'], v['id']) for t in tests if t.get('enabled', True)
                     for v in t['variants'] if v.get('enabled', True)}
        expected = {(r['test_id'], r['input_format']) for r in manifest['prompts']}
        if not targeted and not expected <= available:
            raise ValueError('Run all is missing disabled or rejected required variants; select an explicit subset instead')
        if not targeted and available - expected:
            raise ValueError('Run all includes enabled tests outside the verified coverage manifest; compile/register them before running all tests')
        if targeted:
            selected_ids = {selection['test_id']} if 'test_id' in selection else set(selection.get('test_ids', []))
            manifest_ids = {test_id for test_id, _ in expected}
            if selected_ids - manifest_ids:
                raise ValueError('Selected tests are outside the verified coverage manifest; compile/register them before running')
    rows = manifest['prompts']
    if targeted:
        ids = {selection['test_id']} if 'test_id' in selection else set(selection.get('test_ids', []))
        rows = [row for row in rows if row['test_id'] in ids
                and ('variant_id' not in selection or row['input_format'] == selection['variant_id'])]
    if tests is not None:
        rows = [row for row in rows if (row['test_id'], row['input_format']) in available]
    expected_views = matrix(templates, contract(templates))[0]
    return {**coverage, 'run_scope': 'explicit_subset' if targeted else 'all_current_tests',
            'run_selection': selection,
            'run_actual': {'test_cases': sorted({row['test_case'] for row in rows}),
                           'input_formats': sorted({row['input_format'] for row in rows}),
                           'output_formats': sorted({row['output_format'] for row in rows}),
                           'distinct_prompt_count': len(rows),
                           'observations_per_model': sum(row['repetitions'] for row in rows)},
            'run_omitted_distinct_prompt_count': coverage['expected']['distinct_prompt_count']
                - sum((row['test_case'], row['input_format'], row['output_format']) in expected_views
                      for row in rows)}
