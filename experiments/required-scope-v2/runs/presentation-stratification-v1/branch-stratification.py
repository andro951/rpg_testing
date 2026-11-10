"""Stratify later versioned-branch audits separately from the nine fixed cohorts."""
import collections,json
from pathlib import Path
base=Path(r'E:\Source\Repos\rpg_testing\experiments\required-scope-v2\runs')
models=['local-cb6dd200423a32cc','local-28df315996a77e69','local-81e2a88130ccfa4e','local-2542aed68e6bb077','local-8c5e666555c53096']
campaigns=[('literal-text-heldout-v2',models),('safe-text-heldout-v1',models),('dot-rewrite-heldout-v1',models),('vl8-copy-confirm-v1',models[:1]),('fourb-text-confirm-v1',models[1:2]),('marker-v1-heldout',models[1:2]),('nineb-copy-confirm-v1',models[2:3]+models[4:5]),('vl8-copy-regression-v1',models[:1]),('fourb-literal-regression-v1',models[1:2]),('fourb-copy-regression-v1',models[1:2])]
out={'note':'Each campaign remains separate; these are repeated presentations and not independent tasks. Pairwise comparison preserves complete recipe, model, task and repetition.','campaigns':{}}
for campaign,available in campaigns:
 target={}
 for m in available:
  folder=base/campaign/'desktop'/m
  if campaign=='dot-rewrite-heldout-v1' and m=='local-2542aed68e6bb077':folder=base/campaign/'desktop'/(m+'-resumed')
  a=json.loads((folder/'audit.json').read_text(encoding='utf8'));pairs=a['pairs'];arms=sorted(set().union(*(set(x)-{'fixture','variant','repetition','source_cohort'} for x in pairs)));assert 'original' in arms
  presentations={}
  for pres in ('normal_json','id_keyed_arrays','full_paths'):
   xs=[x for x in pairs if x['variant']==pres];tasks={(x.get('source_cohort',''),x['fixture']) for x in xs};presentations[pres]={'matched_pairs':len(xs),'distinct_tasks':len(tasks),'outcomes':{arm:dict(collections.Counter(x[arm] for x in xs)) for arm in arms},'versus_original':{arm:dict(collections.Counter(x['original']+' -> '+x[arm] for x in xs)) for arm in arms if arm!='original'}}
  target[m]={'observations':a['observations'],'unmatched':a.get('unmatched',[]),'presentations':presentations}
 out['campaigns'][campaign]=target
p=Path(__file__).resolve().parent/'branch-stratified.json';p.write_text(json.dumps(out,indent=2)+'\n',encoding='utf8');print('Saved',len(campaigns),'separate branch campaigns.')
for campaign in ('literal-text-heldout-v2','safe-text-heldout-v1','dot-rewrite-heldout-v1','vl8-copy-confirm-v1','fourb-text-confirm-v1','nineb-copy-confirm-v1'):
 print('\n',campaign)
 for m,x in out['campaigns'][campaign].items():
  print(m,'; '.join(p+':'+str(v['outcomes']) for p,v in x['presentations'].items()))
