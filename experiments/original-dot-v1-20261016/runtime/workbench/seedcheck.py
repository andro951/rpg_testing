"""Seed reproducibility diagnostic for stochastic llama.cpp sampling.

This is an operational check, not a research benchmark case. It intentionally
uses a short open-ended generation at nonzero temperature, repeats the exact
same request with the exact same seed, then changes only the seed.
"""
from __future__ import annotations
import hashlib
import json

POLICY='seed-reproducibility-v1'
PRIMARY_SEED=314159265
ALTERNATE_SEED=271828183
SETTINGS={'temperature':0.8,'top_p':0.95,'top_k':40,'min_p':0.05,'repeat_penalty':1.0}
PROMPT=(
    'SEED_REPRODUCIBILITY_CHECK. Write exactly five sentences of original fictional prose. '
    'The story must involve an abandoned observatory, a sealed metal box, and an unexpected visitor. '
    'Invent the names, setting details, actions, tone, and ending yourself. Return only the story.'
)


def response_digest(result):
    payload={'text':result.get('text',''),'reasoning_text':result.get('reasoning_text','')}
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()


def run_seed_check(backend,cancel=None,progress=None):
    messages=[{'role':'user','content':PROMPT}]
    runs=[]
    try:
        seeds=(PRIMARY_SEED,PRIMARY_SEED,ALTERNATE_SEED)
        for index,seed in enumerate(seeds,1):
            if progress:progress('Seed reproducibility check',100*(index-1)/len(seeds),f'Generation {index}/{len(seeds)} · seed {seed}')
            settings={**SETTINGS,'seed':seed}
            result=backend.generate(messages,settings,None,'off',cancel)
            runs.append({'seed':seed,'finish_reason':result.get('finish_reason'),
                         'digest':response_digest(result),
                         'visible_chars':len(result.get('text','')),
                         'reasoning_chars':len(result.get('reasoning_text',''))})
        if progress:progress('Seed reproducibility check',100,'Three diagnostic generations completed.')
    finally:
        backend.clear_cache()
    complete=all(r['finish_reason']=='stop' for r in runs)
    nonempty=all(r['visible_chars']+r['reasoning_chars']>0 for r in runs)
    same=runs[0]['digest']==runs[1]['digest']
    different=runs[0]['digest']!=runs[2]['digest']
    return {'policy':POLICY,'status':'completed' if complete and nonempty else 'inconclusive',
            'prompt_sha256':hashlib.sha256(PROMPT.encode('utf-8')).hexdigest(),
            'prompt_description':'five-sentence open-ended fiction diagnostic',
            'sampling':SETTINGS,'primary_seed':PRIMARY_SEED,'alternate_seed':ALTERNATE_SEED,
            'same_seed_exact_match':same,'different_seed_changes_output':different,
            'seed_behavior_verified':bool(complete and nonempty and same and different),
            'runs':runs,
            'note':'Exact comparison covers visible and reasoning text; streaming chunk boundaries are ignored.'}


def simulated_seed_check():
    return {'policy':POLICY,'status':'simulated','simulated':True,
            'primary_seed':PRIMARY_SEED,'alternate_seed':ALTERNATE_SEED,
            'same_seed_exact_match':True,'different_seed_changes_output':True,
            'seed_behavior_verified':True,
            'note':'Simulation exercises plumbing only and is not evidence of model seed behavior.'}
