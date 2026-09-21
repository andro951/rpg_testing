"""Descriptive summaries that never pool incompatible versions or simulated/real evidence."""
from __future__ import annotations
import csv
import io
import math
import statistics
from .domain import canonical, digest, experiment_spec


def summarize(records):
    groups = {}; seen = {}; corrupt = []
    for r in records:
        if r.get('status') == 'corrupt':
            corrupt.append({k: r.get(k) for k in ('model_id', 'case_id', 'error')})
            continue
        key = r['case_id']
        if key in seen:
            if canonical(seen[key]) != canonical(r):
                raise ValueError('Conflicting results share a case ID')
            continue
        seen[key] = r
        target = r.get('target', {})
        # A different GGUF or edited test is NOT another sample of the same experiment.
        definition = experiment_spec(r.get('test_definition', {}), r.get('variant_definition', {}))
        protocol = digest({'definition': definition, 'artifacts': r.get('artifact_hashes', {}),
                           'implementation': r.get('provenance', {}).get('workflow_code'),
                           'context': r.get('load', {}).get('context'),
                           'measurement_policy': r.get('policy',r.get('measurement_policy')),
                           'execution_class':r.get('execution_class','legacy_unverified'),
                           'placement':{k:r.get('load',{}).get('placement',{}).get(k) for k in ('gpu_layers','total_layers','cpu_layers')}})
        bucket = (r['model_id'], r.get('test_id', 'unknown'), r.get('variant_id', 'unknown'),
                  protocol, canonical(target), bool(r.get('simulated')))
        groups.setdefault(bucket, []).append(r)
    summaries = []
    for (model, test, variant, protocol, target, simulated), items in sorted(groups.items()):
        completed = [r for r in items if r['status'] == 'completed']
        eligible = [r for r in completed if r.get('measurement_valid', True)]
        scored = [r for r in eligible if type(r.get('score', {}).get('exact_match')) is bool]
        times = [r['pipeline_seconds'] for r in eligible if type(r.get('pipeline_seconds')) in (int, float)]
        matches = sum(r['score']['exact_match'] for r in scored)
        prior = [a for r in items for a in r.get('attempts', [])]
        summaries.append({'model_id': model, 'test_id': test, 'variant_id': variant,
            'protocol_id': protocol, 'target': target, 'simulated': simulated,
            'execution_class':items[0].get('execution_class','legacy_unverified'),
            'skipped':sum(r['status']=='skipped' for r in items),'completed': len(completed), 'infrastructure_errors': sum(r['status']=='error' for r in items),
            'aborted': sum(r['status']=='aborted' for r in items), 'prior_attempts': len(prior),
            'prior_infrastructure_errors': sum(a.get('status')=='error' for a in prior),
            'invalid_measurements': len(completed)-len(eligible), 'scored': len(scored),
            'exact_matches': matches, 'exact_match_rate': matches/len(scored) if scored else None,
            'timing_samples': len(times),
            'mean_pipeline_seconds': statistics.mean(times) if times else None,
            'median_pipeline_seconds': statistics.median(times) if times else None,
            'p95_pipeline_seconds': sorted(times)[math.ceil(.95*len(times))-1] if times else None})
    return {'groups': summaries, 'records': len(seen), 'corrupt_files': corrupt,
            'note': 'SIMULATED groups are plumbing tests. Test, artifact and protocol versions stay separate. '
                    'Invalid measurements are excluded from rates/timings; failures are not discarded. '
                    'P95 is a nearest-rank descriptive statistic, not a population guarantee.'}


def csv_export(summary):
    out = io.StringIO(newline='')
    fields = ['model_id','test_id','variant_id','protocol_id','target','simulated','execution_class','skipped','completed',
              'infrastructure_errors','aborted','prior_attempts','prior_infrastructure_errors',
              'invalid_measurements','scored','exact_matches','exact_match_rate','timing_samples',
              'mean_pipeline_seconds','median_pipeline_seconds','p95_pipeline_seconds']
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader(); writer.writerows(summary['groups'])
    return out.getvalue()
