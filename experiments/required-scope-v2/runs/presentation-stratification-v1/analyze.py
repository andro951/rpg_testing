"""Retrospective audit-only stratification; no model requests or edited old records."""
import collections,json,re
from pathlib import Path

base=Path(r'E:\Source\Repos\rpg_testing\experiments\required-scope-v2')
cohorts=['generalization-holdout-v1','schema-diversity-v1','array-boundaries-v1','id-routing-v1','array-scale-v1','multi-change-v1','reserved-id-v1','paired-id-characters-v1','selection-burden-v1']
models=['local-cb6dd200423a32cc','local-28df315996a77e69','local-81e2a88130ccfa4e','local-2542aed68e6bb077','local-8c5e666555c53096']
arms=['research_json_v2','research_slash_json_v1','path_list_v1'];presentations=['normal_json','id_keyed_arrays','full_paths'];safe=re.compile(r'^[A-Za-z0-9_-]+$')
read=lambda p:json.loads(p.read_text(encoding='utf8'))

def inspect(schema,value,ids,fields):
    typ=schema.get('type')
    if typ=='object' and isinstance(value,dict):
        for k,v in value.items():
            fields.add(k)
            if k in schema.get('properties',{}):inspect(schema['properties'][k],v,ids,fields)
    elif typ=='array' and isinstance(value,list):
        item=schema.get('items',{});idfield=schema.get('x-id-field')
        for x in value:
            if idfield and isinstance(x,dict) and idfield in x:ids.add(str(x[idfield]))
            elif item.get('type')!='object':ids.add(str(x))
            inspect(item,x,ids,fields)

def id_fields(schema,out):
    if isinstance(schema,dict):
        if schema.get('x-id-field'):out.add(schema['x-id-field'])
        for v in schema.values():id_fields(v,out)
    elif isinstance(schema,list):
        for v in schema:id_fields(v,out)

def text_in_object(value,excluded):
    if isinstance(value,dict):return any(k not in excluded and text_in_object(v,excluded) for k,v in value.items())
    if isinstance(value,list):return any(text_in_object(v,excluded) for v in value)
    return isinstance(value,str)

cases={};cells={};coverage={}
for cohort in cohorts:
    folder=base/'cohorts'/cohort;manifest=read(folder/'manifest.json');refs=read(folder/'references.json');specs={}
    for p in (folder/'test_specs').glob('*__research_json_v2.json'):
        t=read(p);fixture=t['prompt_builder']['fixture'];identifiers=set();fields=set();excluded=set();id_fields(t['state_schema'],excluded)
        inspect(t['state_schema'],t['source']['initial_state'],identifiers,fields);inspect(t['state_schema'],t['expected_state'],identifiers,fields)
        ref=next(x for x in refs if x['test_id']==t['id']);ops=json.loads(ref['answer']);text_value=any((o['op']=='replace' and isinstance(o.get('value'),str)) or (o['op']=='add' and isinstance(o.get('value'),dict) and text_in_object(o['value'],excluded)) for o in ops)
        clean=all(safe.fullmatch(x) for x in identifiers|fields)
        cases[(cohort,fixture)]={'id_category':'safe_all_id_value_and_field_components' if clean else 'contains_reserved_id_value_or_field_component','text_value':text_value,'methods':{},'identifier_samples':sorted(identifiers),'field_samples':sorted(fields)}
        specs[t['id']]=fixture
    expected=8 if cohort=='selection-burden-v1' else 6;assert len(specs)==expected,(cohort,len(specs))
    lookup={(x['test_id'],x['variant_id']):(x['fixture'],x.get('method')) for x in manifest['requests']}
    for model in models:
        a=read(base/'runs'/cohort/'desktop'/model/'audit.json');assert a['observations']==expected*27
        seen=set()
        for e in a['evidence']:
            fixture,method=lookup[(e['test_id'],e['variant_id'])];assert method in arms and (cohort,fixture) in cases
            k=(model,cohort,fixture,e['variant_id'],e['repetition'],method);assert k not in cells;cells[k]=e['outcome'];seen.add(k)
        assert len(seen)==expected*27
    coverage[cohort]=expected
assert len(cells)==7560 and len(cases)==56

def summarize(subset):
    group={};pairs={};method_pairs={}
    for model in models:
        group[model]={};pairs[model]={};method_pairs[model]={}
        for arm in arms:
            group[model][arm]={};pairs[model][arm]={}
            for pres in presentations:
                vals=[cells[(model,c,f,pres,r,arm)] for c,f in subset for r in range(3)]
                group[model][arm][pres]=dict(collections.Counter(vals))
            for other in ('id_keyed_arrays','full_paths'):
                transitions=collections.Counter(cells[(model,c,f,'normal_json',r,arm)]+' -> '+cells[(model,c,f,other,r,arm)] for c,f in subset for r in range(3))
                pairs[model][arm][other]=dict(transitions)
        for pres in presentations:
            method_pairs[model][pres]={}
            for arm in ('research_slash_json_v1','path_list_v1'):
                transitions=collections.Counter(cells[(model,c,f,pres,r,'research_json_v2')]+' -> '+cells[(model,c,f,pres,r,arm)] for c,f in subset for r in range(3))
                method_pairs[model][pres][arm]=dict(transitions)
    return group,pairs,method_pairs

subsets={'all':list(cases),'safe_all_id_value_and_field_components':[k for k,v in cases.items() if v['id_category']=='safe_all_id_value_and_field_components'],'contains_reserved_id_value_or_field_component':[k for k,v in cases.items() if v['id_category']=='contains_reserved_id_value_or_field_component'],'text_value':[k for k,v in cases.items() if v['text_value']],'non_text_value':[k for k,v in cases.items() if not v['text_value']]}
result={'cohorts':coverage,'models':models,'recipes':arms,'presentations':presentations,'tasks':len(cases),'observations':len(cells),'case_metadata':{c+'/'+f:v for (c,f),v in cases.items()},'groups':{}}
for name,subset in subsets.items():
 counts,matched,methods=summarize(subset);result['groups'][name]={'tasks':len(subset),'cohorts':len(set(c for c,_ in subset)),'cases_by_cohort':dict(collections.Counter(c for c,_ in subset)),'outcomes':counts,'matched_presentation_transitions_vs_normal':matched,'matched_method_transitions_vs_dot':methods}
out=Path(__file__).resolve().parent/'stratified.json';out.write_text(json.dumps(result,indent=2,ensure_ascii=True)+'\n',encoding='utf8')
print('Validated',len(cells),'audited records across',len(cases),'tasks and',len(cohorts),'cohorts.')
for name,g in result['groups'].items():print(name,'tasks',g['tasks'],'cohorts',g['cohorts'])
for model in models:
 print('\n',model)
 for arm in arms:
  scores=result['groups']['all']['outcomes'][model][arm];print(arm,' '.join(p+':'+str(scores[p].get('PASS',0))+'/168' for p in presentations))
