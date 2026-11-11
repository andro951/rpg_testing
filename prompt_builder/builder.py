"""Compile editable files into frozen tests. Does not run a model or read old schemas."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

from evaluation import array_identities_intent as evaluator
from evaluation.catalog import definition_source_sha256
from workbench.domain import digest, read_json, safe_id, validate_test, write_json
from .presentation import render, has_array, SERIALIZERS
from .template_text import assemble, read_text

ROOT=Path(__file__).parent/'templates'
VERSION='file-templates-v1'

def folder(root,category,name):
    safe_id(name)
    base=(Path(root)/category).resolve();target=(base/name).resolve()
    if not target.is_relative_to(base)or not target.is_dir():raise ValueError(f'Unknown {category}: {name}')
    return target

def discover(root=ROOT):
    root=Path(root)
    return {category:sorted(p.name for p in (root/category).iterdir()if p.is_dir()and(p/required).is_file())
            for category,required in [('input_format','format.json'),('output_format','format.json'),('test_cases','starting_data.json')]}

def load_case(name,root=ROOT):
    path=folder(root,'test_cases',name)
    state=read_json(path/'starting_data.json');expected=read_json(path/'expected_result.json');patch=read_json(path/'expected_patch.json')
    identities=read_json(path/'array_identities.json')
    evaluator.validate_data(state,identities);evaluator.validate_data(expected,identities)
    actual=evaluator.apply_patch(state,patch,identities)
    # A reference is checked separately. It NEVER enters model-input assembly.
    from workbench.scoring import equal
    if not equal(evaluator.unordered(actual['final_state']),evaluator.unordered(expected)):
        raise ValueError(f'{name}: expected_patch does not produce expected_result')
    return {'id':name,'starting_data':state,'requested_change':read_text(path/'requested_change.txt'),
            'expected_result':expected,'expected_patch':patch,'array_identities':identities}

def configuration(root,category,name):
    data=read_json(folder(root,category,name)/'format.json')
    if category=='input_format'and data.get('serializer')not in SERIALIZERS:raise ValueError('Unknown input serializer')
    if category=='output_format'and data.get('decoder')not in evaluator.OUTPUT_FORMATS:raise ValueError('Unknown output decoder')
    return data

def prompt(case,input_format,output_format,root=ROOT,*,with_parts=False):
    input_config=configuration(root,'input_format',input_format)
    configuration(root,'output_format',output_format)
    serializer=input_config['serializer']
    # The map selects keys/path parts for these conversions only. It is never
    # a template binding or a separately rendered description of the data.
    current_data=(render(case['starting_data'],serializer,case.get('array_identities'))
                  if serializer in ('id_keyed_arrays','full_paths')
                  else render(case['starting_data'],serializer))
    return assemble(root,input_format=input_format,output_format=output_format,
        current_data=current_data,task=case['requested_change'],with_parts=with_parts)

def validate_presentation_identity(case,formats,root=ROOT):
    """Keep the data-only named-table convention consistent with the validator.

    Only keyed arrays and full paths may use declarations to select their IDs.
    Tables still receive no metadata. Empty arrays display no element selectors
    and need no comparison.
    """
    if not any(configuration(root,'input_format',mode)['serializer']=='named_tables' for mode in formats):
        return
    from evaluation.array_identity_map import IdentityMap
    from .presentation import id_field
    declarations=IdentityMap(case['array_identities'])
    def walk(value,path):
        if isinstance(value,dict):
            for key,child in value.items():walk(child,path+(key,))
        elif isinstance(value,list):
            if value and id_field(value)!=declarations.field(value,path):
                raise ValueError('ID-dependent presentation disagrees with validator identity at '+repr(path)+'; use normal_json')
            for child in value:walk(child,path+(None,))
    walk(case['starting_data'],())


def applicable(case,output_format,root=ROOT):
    config=configuration(root,'output_format',output_format)
    if config['decoder']!='typed_lines':return None
    from .reference_output import encode
    from evaluation.array_identities_intent import normalize_response
    try:
        raw=encode(case['starting_data'],case['expected_patch'],output_format,case['array_identities'])
        normalize_response(raw,case['starting_data'],output_format,case['array_identities'])
    except ValueError as exc:return str(exc)
    return None


def apply_saved_promotion(test, repository=None):
    """Preserve accepted guidance only for the exact compiled template inputs."""
    from optimization.promotion import compiled
    repository = Path(repository) if repository is not None else Path(__file__).resolve().parents[1]
    promoted = compiled(repository, test['id'], base_test=test)
    return promoted if promoted is not None else test


def compile_test(case,output_format,*,input_formats=None,root=ROOT,repetitions=3,promotion_root=None):
    if isinstance(case,str):case=load_case(case,root)
    reason=applicable(case,output_format,root)
    if reason:raise ValueError(f'{case["id"]}/{output_format}: {reason}')
    selection=read_json(Path(root)/'common/selection.json')
    formats=input_formats or selection['input_formats']
    skip_keyed=selection.get('skip_id_keyed_when_no_arrays',True)
    if type(skip_keyed)is not bool:raise ValueError('skip_id_keyed_when_no_arrays must be boolean')
    config=configuration(root,'output_format',output_format)
    validate_presentation_identity(case,formats,root)
    assembled={mode:prompt(case,mode,output_format,root,with_parts=True)for mode in formats
              if not(skip_keyed and configuration(root,'input_format',mode)['serializer']=='id_keyed_arrays'and not has_array(case['starting_data']))}
    requests={mode:result[0]for mode,result in assembled.items()}
    if not requests:raise ValueError('No applicable input formats')
    system=next(iter(requests.values()))[0]['content']
    if any(r[0]['content']!=system for r in requests.values()):raise ValueError('System text must agree across variants')
    test={'schema_version':2,'id':case['id']+'__'+output_format,'name':case['id'].replace('_',' ').capitalize(),
          'description':'Schema-free database updates; final-state grading with an expected-patch difference diagnostic.',
          'workflow':'steps','enabled':True,'instructions':system,'repetitions':repetitions,'timeout_seconds':120,
          'source':{'initial_state':copy.deepcopy(case['starting_data']),'array_identities':copy.deepcopy(case['array_identities'])},'expected_state':copy.deepcopy(case['expected_result']),
          'prompt_builder':{'version':VERSION,'fixture':case['id'],'method':output_format,'prompt_digest':digest(requests),
                            'review_status':'user_authorized_implementation','schema_hints':False},'variants':[]}
    for mode,msgs in requests.items():
        # Capture source fields during assembly, never reverse-parse editable headings.
        user=msgs[-1]['content'];bindings=assembled[mode][1]
        test['variants'].append({'id':mode,'prompt_style':'direct_text_v1','prompt_bindings':bindings,'state_presentation':'raw_json','cache':'default',
             'expected_patch':copy.deepcopy(case['expected_patch']),
             'steps':[{'id':'patch','type':'generate','prompt':user,'output':{'type':'text'},'sampling':{'temperature':0,'top_p':1,'seed':42}}],
             'result':{'step':'patch','representation':'dot_patch_v1','output_format':config['decoder'],'evaluator':evaluator.configuration()}})
    validate_test(test)
    return apply_saved_promotion(test, promotion_root)

def source_hashes(root):
    root=Path(root)
    # Record source provenance, including evaluation-only case answers. Hashing
    # an answer does not insert it into model input. Frozen references are excluded.
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(root.rglob('*'))
            if p.is_file()and p.suffix in('.txt','.json')and 'reference'not in p.parts}

def _build(output,*,root=ROOT,input_formats=None,output_formats=None,cases=None,repetitions=3,promotion_root=None):
    root=Path(root);output=Path(output)
    selection=read_json(root/'common/selection.json')
    modes=input_formats or selection['input_formats'];formats=output_formats or selection['output_formats'];names=cases or selection['test_cases']
    if len(set(names))!=len(names)or len(set(modes))!=len(modes)or len(set(formats))!=len(formats):raise ValueError('Duplicate selection')
    manifest={'version':VERSION,'schema_hints':False,'evaluator':evaluator.configuration(),'model_runs_started_by_builder':0,
              'source_hashes':source_hashes(root),'test_cases':names,'input_formats':modes,'output_formats':formats,'prompts':[],'unsupported':[]}
    for name in names:
        case=load_case(name,root)
        for form in formats:
            reason=applicable(case,form,root)
            if reason:
                manifest['unsupported'].append({'test_case':name,'output_format':form,'reason':reason});continue
            test=compile_test(case,form,input_formats=modes,root=root,repetitions=repetitions,promotion_root=promotion_root)
            write_json(output/'test_specs'/(test['id']+'.json'),test)
            write_json(output/'references'/(test['id']+'.json'),{'synthetic_reference_only':True,'array_identities':case['array_identities'],'expected_patch':case['expected_patch'],'expected_state':case['expected_result']})
            for variant in test['variants']:
                from workbench.workflows import messages
                request=messages(test,variant['steps'][0],{},variant)
                target=output/'prompts'/test['id']/variant['id'];write_json(target.with_suffix('.messages.json'),request)
                target.with_suffix('.txt').write_text('SYSTEM MESSAGE\n'+request[0]['content']+'\n\nUSER MESSAGE\n'+request[-1]['content'],encoding='utf8')
                manifest['prompts'].append({'test_id':test['id'],'test_case':name,'input_format':variant['id'],'output_format':form,'message_digest':digest(request),'repetitions':repetitions,'file':target.with_suffix('.messages.json').relative_to(output).as_posix()})
    manifest['prompt_count']=len(manifest['prompts']);manifest['observations_per_model']=sum(p['repetitions']for p in manifest['prompts'])
    manifest['test_spec_files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted((output/'test_specs').glob('*.json'))}
    write_json(output/'manifest.json',manifest)
    return manifest


def build(output,**settings):
    """Publish a complete build only on success; never mix two selections."""
    import os
    import shutil
    import tempfile
    output=Path(output)
    if output.is_symlink():raise ValueError('Build output cannot be a symlink')
    allowed={'test_specs','references','prompts','manifest.json'}
    if output.exists()and any(p.name not in allowed for p in output.iterdir()):
        raise ValueError('Output contains unmanaged files; choose a dedicated build directory')
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.prompt-build-',dir=output.parent))
    try:
        manifest=_build(stage,**settings)
        previous=None
        if output.exists():
            if any(output.iterdir()):
                # Preserve older generated test data; no archived builder code.
                stamp=digest({p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*'))if p.is_file()})[:16]
                history=output.parent/(output.name+'.history');history.mkdir(exist_ok=True)
                previous=history/stamp
                if previous.exists():
                    # Same complete build already saved; keep a unique copy rather than erase it.
                    import time
                    previous=history/(stamp+'-'+str(time.time_ns()))
                os.replace(output,previous)
            else:output.rmdir()
        try:os.replace(stage,output)
        except BaseException:
            if previous is not None and not output.exists():os.replace(previous,output)
            raise
        return manifest
    finally:
        if stage.exists():shutil.rmtree(stage)


def install(output,repository=None):
    """Activate a completed build; preserve superseded definitions as test data."""
    import shutil
    from workbench.domain import experiment_spec
    output=Path(output);repository=Path(repository)if repository else Path(__file__).resolve().parents[1]
    manifest=read_json(output/'manifest.json')
    if manifest.get('version')!=VERSION:raise ValueError('Not a completed template build')
    inventory=manifest.get('test_spec_files',{})
    actual={p.name for p in (output/'test_specs').glob('*.json')}
    if not inventory or actual!=set(inventory):raise ValueError('Build test inventory does not match manifest; rebuild before installing')
    for name,expected_hash in inventory.items():
        if Path(name).name!=name or hashlib.sha256((output/'test_specs'/name).read_bytes()).hexdigest()!=expected_hash:
            raise ValueError('Build test hash does not match manifest: '+name)
    generated={name:read_json(output/'test_specs'/name)for name in inventory}
    if not generated:raise ValueError('Refusing to install an empty suite')
    for t in generated.values():validate_test(t)
    from workbench.workflows import messages
    by_id={t['id']:t for t in generated.values()}
    expected_views={(t['id'],v['id'])for t in generated.values()for v in t['variants']}
    seen=set()
    for row in manifest['prompts']:
        key=(row['test_id'],row['input_format'])
        if key not in expected_views or key in seen:raise ValueError('Manifest prompt inventory mismatch')
        seen.add(key);test=by_id[key[0]];variant=next(v for v in test['variants']if v['id']==key[1])
        request=messages(test,variant['steps'][0],{},variant)
        file=(output/row['file']).resolve()
        if not file.is_relative_to(output.resolve()) or read_json(file)!=request or digest(request)!=row['message_digest']:
            raise ValueError('Generated prompt preview does not match frozen definition')
    if seen!=expected_views:raise ValueError('Manifest is missing generated prompt views')
    current=repository/'test_specs';current.mkdir(exist_ok=True)
    managed={p.name:p for p in current.glob('*.json')if read_json(p).get('prompt_builder',{}).get('version')in('database-v3','file-templates-v1')}
    collisions=(set(generated)&{p.name for p in current.glob('*.json')})-set(managed)
    if collisions:raise ValueError('Refusing to overwrite unmanaged tests: '+', '.join(sorted(collisions)))
    changed={name:p for name,p in managed.items()if name not in generated or read_json(p)!=generated[name]}
    if changed:
        stamp=digest({name:hashlib.sha256(p.read_bytes()).hexdigest()for name,p in sorted(changed.items())})[:16]
        archive=repository/'archives/template-builds'/stamp/'test_specs'
        archive.mkdir(parents=True,exist_ok=True)
        for name,p in changed.items():
            dest=archive/name
            if dest.exists()and dest.read_bytes()!=p.read_bytes():raise ValueError('Archive conflict')
            shutil.copy2(p,dest)
        # Preview messages and their manifest are frozen research artifacts too.
        # Preserve exact bytes before replacing the current generated view.
        previews=repository/'prompts/current-suite'
        if previews.exists():
            saved=archive.parent/'prompts/current-suite'
            for source in sorted(previews.rglob('*')):
                if not source.is_file():continue
                dest=saved/source.relative_to(previews)
                if dest.exists()and dest.read_bytes()!=source.read_bytes():raise ValueError('Archived preview conflict')
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,dest)
    for name,t in generated.items():write_json(current/name,t)
    for name,p in managed.items():
        if name not in generated:p.unlink()
    # Catalog retains historical definitions; replaced current entries point to
    # their preserved pre-template snapshot on the initial migration.
    catpath=repository/'evaluation/catalog.json';catalog=read_json(catpath)
    entries=[]
    for entry in catalog['definitions']:
        path=entry.get('path','')
        if path.startswith('test_specs/'):
            if Path(path).name in generated:continue
            old=repository/'archives/pre-template-builder'/path
            if old.exists():entry={**entry,'path':old.relative_to(repository).as_posix(),'scope':'archived'}
            elif Path(path).name in managed:continue
        entries.append(entry)
    groups=read_json(repository/'reporting/grouping_metadata.json')
    timing=read_json(repository/'reporting/timing_expectations.json')
    fixture_path=repository/'evaluation/fixtures.json';fixtures=read_json(fixture_path)
    rows=[]
    for row in fixtures['fixtures']:
        path=row.get('source_path','')
        if path.startswith('test_specs/'):
            if Path(path).name in generated:continue
            old=repository/'archives/pre-template-builder'/path
            if old.exists():row={**row,'source_path':old.relative_to(repository).as_posix()}
            elif Path(path).name in managed:continue
        rows.append(row)
    for name,test in generated.items():
        path=current/name
        entries.append({'id':test['id'],'path':path.relative_to(repository).as_posix(),'scope':'active','family':'database',
                        'source_sha256':definition_source_sha256(path),'specific_requirements':test['description'],
                        'variants':[v['id']for v in test['variants']]})
        groups[test['id']]={};timing[test['id']]={}
        for v in test['variants']:
            groups[test['id']][v['id']]={'ability_category':'Database operations','task_type':'Schema-free database update',
                'prompt_comparison_set':test['name'],'test_version':'file-templates-v1','operation_method':test['prompt_builder']['method'],
                'input_presentation':v['id'],'reviewed_definition':digest(experiment_spec(test,v))}
            from .reference_output import encode
            from workbench.workflows import evaluate
            raw=encode(test['source']['initial_state'],v['expected_patch'],v['result']['output_format'],test['source']['array_identities'])
            if evaluate(test,v,{'patch':raw}).get('exact_match')is not True:raise ValueError('Synthetic reference does not pass its selected reader: '+test['id'])
            rows.append({'test_id':test['id'],'variant_id':v['id'],'source_path':path.relative_to(repository).as_posix(),
                'label':'synthetic known pass, not model inference','outputs':{'patch':raw},'expected_outcome':'PASS'})
    catalog['definitions']=entries;fixtures['fixtures']=rows
    write_json(catpath,catalog);write_json(fixture_path,fixtures)
    write_json(repository/'reporting/grouping_metadata.json',groups);write_json(repository/'reporting/timing_expectations.json',timing)
    # Current preview location is explicit; prior previews remain archived.
    previews=repository/'prompts/current-suite'
    if previews.exists():shutil.rmtree(previews)  # generated only; sources live in templates
    shutil.copytree(output/'prompts',previews)
    write_json(previews/'manifest.json',manifest)
    from tools.build_prompt_sharing import build as sharing
    write_json(repository/'optimization/sharing.json',sharing(repository))
    return {'installed_definitions':len(generated),'prompt_count':manifest['prompt_count'],'archived_changed_definitions':len(changed)}
