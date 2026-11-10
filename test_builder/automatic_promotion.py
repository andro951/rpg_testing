"""Reproducible normal-builder recipes for accepted, fully validated OPRO winners."""
import copy
from workbench.domain import digest, read_json, validate_test
from optimization.templates import render


def apply(test, recipe):
    if recipe.get('review_status') != 'accepted' or digest(recipe['candidate']) != recipe['candidate_digest']:
        raise ValueError('Promotion needs an accepted exact candidate')
    candidate=recipe['candidate']
    validation=recipe.get('validation',{})
    if validation.get('complete') is not True or not validation.get('required') or validation.get('passes')!=validation['required']:
        raise ValueError('Promotion requires complete successful validation')
    if candidate.get('template_format')=='lpil':
        from .normal_prompt import _validate_candidate
        _validate_candidate(candidate)
    else:
        from optimization.templates import parse_candidate
        parse_candidate('SYSTEM_MESSAGE:\n'+candidate['system']+'\nUSER_MESSAGE:\n'+candidate['user'])
    text=candidate['system']+'\n'+candidate['user']
    import json
    if test['id'] in text or json.dumps(test.get('expected_state'),ensure_ascii=False) in text:
        raise ValueError('Candidate contains a fixture identity or expected state')
    def identifiers(value,schema):
        if isinstance(value,dict):
            for name,child in value.items():yield from identifiers(child,schema.get('properties',{}).get(name,{}))
        elif isinstance(value,list):
            field=schema.get('x-id-field')
            for element in value:
                if field and isinstance(element,dict) and isinstance(element.get(field),str) and len(element[field])>=4:yield element[field]
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
                             'validation': recipe['validation'], 'approval_basis': recipe['approval_basis']})
    validate_test(result)
    return result


def compiled(root, fixture, method):
    path = root / 'test_builder/active_opro_promotions.json'
    if not path.exists():
        return None
    registry = read_json(path)
    recipe = registry.get('recipes', {}).get(method + '/' + fixture['id'])
    if recipe is None:
        return None
    base = recipe['base_test']
    if digest(fixture) != recipe['fixture_digest']:
        raise ValueError('Fixture changed since OPRO promotion; review a new recipe')
    return apply(base, recipe)


def rebuild(root):
    """Replay saved normal-builder recipes, retaining the original base definitions."""
    from workbench.domain import write_json
    registry = read_json(root / 'test_builder/active_opro_promotions.json')
    changed={}
    for recipe in registry['recipes'].values():
        test = apply(recipe['base_test'], recipe)
        write_json(root / 'test_specs' / (test['id'] + '.json'), test)
        changed[test['id']]=test
    # Refresh definition-bound sidecars using the normal suite builder's functions.
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
        import hashlib
        catalog=read_json(catalog_path)
        for entry in catalog['definitions']:
            if entry['id'] in changed:entry['source_sha256']=hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()
        write_json(catalog_path,catalog)
    manifest_path=root/'prompts/patch-suite/manifest.json'
    if manifest_path.exists():
        from .normal_prompt import preview
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
