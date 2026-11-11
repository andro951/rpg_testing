"""Reproducible saved-definition recipes for accepted, fully validated OPRO winners."""
import copy
from workbench.domain import digest, read_json, validate_test
from optimization.templates import render


def apply(test, recipe):
    if recipe.get('review_status') != 'accepted' or digest(recipe['candidate']) != recipe['candidate_digest']:
        raise ValueError('Promotion needs an accepted exact candidate')
    if recipe.get('base_definition_digest', digest(test)) != digest(test):
        raise ValueError('Base definition changed since OPRO promotion')
    candidate=recipe['candidate']
    validation=recipe.get('validation',{})
    if validation.get('complete') is not True or not validation.get('required') or validation.get('passes')!=validation['required']:
        raise ValueError('Promotion requires complete successful validation')
    if candidate.get('template_format')=='lpil':
        from .templates import validate_lpil_candidate
        validate_lpil_candidate(candidate)
    else:
        from optimization.templates import parse_candidate
        parse_candidate('SYSTEM_MESSAGE:\n'+candidate['system']+'\nUSER_MESSAGE:\n'+candidate['user'])
    text=candidate['system']+'\n'+candidate['user']
    import json
    if test['id'] in text or json.dumps(test.get('expected_state'),ensure_ascii=False) in text:
        raise ValueError('Candidate contains a fixture identity or expected state')
    def evaluator_version(variant):
        selected = variant.get('result', {}).get('evaluator')
        return selected.get('version') if isinstance(selected, dict) else selected
    schema_free = all(evaluator_version(v) == 'schema-free-intent-v1' for v in test['variants'])
    def identifiers(value,schema):
        if isinstance(value,dict):
            for name,child in value.items():yield from identifiers(child,schema.get('properties',{}).get(name,{}))
        elif isinstance(value,list):
            if schema_free:
                from evaluation.schema_free_intent import id_field
                field=id_field(value)
            else:
                field=schema.get('x-id-field')
            for element in value:
                if field and isinstance(element,dict) and isinstance(element.get(field),str) and len(element[field])>=4:yield element[field]
                if schema_free and field is None and isinstance(element, str) and len(element) >= 4:yield element
                yield from identifiers(element,schema.get('items',{}))
    if any(identifier in text for identifier in identifiers(test['source']['initial_state'],test.get('state_schema',{}))):
        raise ValueError('Candidate contains a literal fixture element ID')
    result = copy.deepcopy(test)
    requests = {}
    for variant in result['variants']:
        if len(variant['steps']) != 1 or variant['steps'][0]['type'] != 'generate':
            raise ValueError('Automatic promotion currently requires a single database generation step')
        request = render(recipe['candidate'], {**variant['prompt_bindings'], 'prior_outputs': '{}'})
        if [m['role'] for m in request] != ['system', 'user']:
            raise ValueError('Promotion requires one system and one user message')
        requests[variant['id']] = request
        variant['steps'][0]['prompt'] = request[1]['content']
    systems = {r[0]['content'] for r in requests.values()}
    if len(systems) != 1:
        raise ValueError('Promoted system instruction varies with presentation')
    result['instructions'] = systems.pop()
    result['prompt_builder'].update(prompt_digest=digest(requests), review_status='accepted',
        automatic_promotion={'session_id': recipe['session_id'], 'candidate_digest': recipe['candidate_digest'],
                             'validation': recipe['validation'], 'approval_basis': recipe['approval_basis'],
                             'template_definition_digest': recipe.get('template_definition_digest', digest(test))})
    validate_test(result)
    return result


def compiled(root, test_id, base_test=None):
    """Replay a saved recipe, optionally checking freshly compiled template input."""
    path = root / 'optimization/active_promotions.json'
    if not path.exists():
        return None
    found = [recipe for recipe in read_json(path).get('recipes', {}).values()
             if recipe['base_test']['id'] == test_id]
    if not found:
        return None
    if len(found) != 1:
        raise ValueError('Duplicate promotion recipe for definition: ' + test_id)
    recipe = found[0]
    base = recipe['base_test']
    if recipe.get('base_definition_digest', digest(base)) != digest(base):
        raise ValueError('Base definition changed since OPRO promotion')
    template_digest = recipe.get('template_definition_digest', digest(base))
    if base_test is not None and digest(base_test) != template_digest:
        raise ValueError('Stale OPRO promotion for ' + test_id +
                         ': compiled templates, data, controls or evaluator changed; review a new recipe')
    return apply(base, recipe)


def refresh_current_previews(root, changed):
    """Refresh the new active preview layout from the authoritative saved tests."""
    from workbench.workflows import messages
    from workbench.domain import write_json
    previews = root / 'prompts/current-suite'
    path = previews / 'manifest.json'
    if not path.exists():
        return
    manifest = read_json(path)
    for entry in manifest['prompts']:
        if entry['test_id'] not in changed:
            continue
        test = changed[entry['test_id']]
        variant = next(v for v in test['variants'] if v['id'] == entry['input_format'])
        request = messages(test, variant['steps'][0], {}, variant)
        target = previews / test['id'] / variant['id']
        text = 'SYSTEM MESSAGE\n' + request[0]['content'] + '\n\nUSER MESSAGE\n' + request[-1]['content']
        target.parent.mkdir(parents=True, exist_ok=True)
        write_json(target.with_suffix('.messages.json'), request)
        target.with_suffix('.txt').write_text(text, encoding='utf8')
        entry.update(message_digest=digest(request), prompt_digest=test['prompt_builder']['prompt_digest'],
                     automatic_promotion=copy.deepcopy(test['prompt_builder']['automatic_promotion']))
    write_json(path, manifest)


def rebuild(root):
    """Replay saved definition recipes, retaining the original base definitions."""
    from workbench.domain import write_json
    registry = read_json(root / 'optimization/active_promotions.json')
    changed={}
    for recipe in registry['recipes'].values():
        test = apply(recipe['base_test'], recipe)
        path = root / 'test_specs' / (test['id'] + '.json')
        if not path.exists() or read_json(path) not in (recipe['base_test'], test):
            raise ValueError('Conflicting or inactive definition during promotion replay: ' + test['id'])
        if test['id'] in changed:
            raise ValueError('Duplicate promotion recipe for definition: ' + test['id'])
        changed[test['id']]=test
    for test in changed.values():
        write_json(root / 'test_specs' / (test['id'] + '.json'), test)
    # Refresh definition-bound exports after all replay targets pass validation.
    groups_path=root/'reporting/grouping_metadata.json'
    if groups_path.exists():
        from workbench.domain import experiment_spec
        groups=read_json(groups_path)
        for test in changed.values():
            for variant in test['variants']:
                entry=groups.get(test['id'],{}).get(variant['id'])
                if entry is not None:entry['reviewed_definition']=digest(experiment_spec(test,variant))
        write_json(groups_path,groups)
        from tools.build_prompt_sharing import build
        write_json(root/'optimization/sharing.json',build(root))
    catalog_path=root/'evaluation/catalog.json'
    if catalog_path.exists():
        from evaluation.catalog import definition_source_sha256
        catalog=read_json(catalog_path)
        for entry in catalog['definitions']:
            if entry['id'] in changed:entry['source_sha256']=definition_source_sha256(root/entry['path'])
        write_json(catalog_path,catalog)
    manifest_path=root/'prompts/patch-suite/manifest.json'
    if manifest_path.exists():
        from workbench.prompt_rendering import preview
        from workbench.workflows import messages
        import hashlib
        manifest=read_json(manifest_path)
        for entry in manifest['prompts']:
            if entry['test_id'] not in changed:continue
            test=changed[entry['test_id']]
            variant=next(v for v in test['variants'] if v['id']==entry['presentation'])
            request=messages(test,variant['steps'][0],{},variant);text=preview(request)
            for key in ('file','review_file'):
                if entry.get(key):
                    p=root/entry[key];p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8')
            write_json((root/entry['file']).with_suffix('.messages.json'),request)
            entry.update(prompt_digest=test['prompt_builder']['prompt_digest'],message_digest=digest(request),prompt_sha256=hashlib.sha256(text.encode()).hexdigest())
        write_json(manifest_path,manifest)
    refresh_current_previews(root, changed)
