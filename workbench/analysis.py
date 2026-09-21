"""Descriptive exports, not a claim that a tiny smoke suite proves model quality."""
from __future__ import annotations
import csv
import io
import statistics
from .domain import canonical


def summarize(records):
    groups={};seen={}
    for r in records:
        key=r['case_id']
        if key in seen:
            if canonical(seen[key])!=canonical(r):raise ValueError('Conflicting results share a case ID')
            continue
        seen[key]=r
        target=r.get('target',{})
        bucket=(r['model_id'],r.get('variant_id','unknown'),canonical(target),bool(r.get('simulated')))
        groups.setdefault(bucket,[]).append(r)
    summaries=[]
    for (model,variant,target,simulated),items in sorted(groups.items()):
        completed=[r for r in items if r['status']=='completed']
        eligible=[r for r in completed if r.get('measurement_valid',True)]
        scored=[r for r in eligible if type(r.get('score',{}).get('exact_match')) is bool]
        times=[r['pipeline_seconds'] for r in eligible if type(r.get('pipeline_seconds'))in(int,float)]
        summaries.append({'model_id':model,'variant_id':variant,'target':target,'simulated':simulated,
            'completed':len(completed),'infrastructure_errors':sum(r['status']=='error' for r in items),
            'aborted':sum(r['status']=='aborted' for r in items),'invalid_measurements':len(completed)-len(eligible),
            'scored':len(scored),'exact_matches':sum(r['score']['exact_match'] for r in scored),
            'exact_match_rate':sum(r['score']['exact_match'] for r in scored)/len(scored) if scored else None,
            'mean_pipeline_seconds':statistics.mean(times) if times else None,
            'median_pipeline_seconds':statistics.median(times) if times else None})
    return {'groups':summaries,'records':len(seen),'note':'SIMULATED groups are plumbing tests, not model evaluations. Invalid cache measurements are excluded from rates and timing summaries. Different test selections should not be compared as if they were identical.'}


def csv_export(summary):
    out=io.StringIO(newline='')
    fields=['model_id','variant_id','target','simulated','completed','infrastructure_errors','aborted','invalid_measurements','scored','exact_matches','exact_match_rate','mean_pipeline_seconds','median_pipeline_seconds']
    writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader();writer.writerows(summary['groups'])
    return out.getvalue()
