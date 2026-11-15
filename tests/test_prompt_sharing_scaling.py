"""Performance refactor parity and strict membership regression checks; no inference."""
import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.build_prompt_sharing import expansion_scopes
from optimization.catalog import validate
from workbench.domain import digest


def legacy_scopes(variants):
    scopes = {}
    for key, entry in variants.items():
        for component, binding in entry['components'].items():
            compatible = [k for k, v in variants.items() if v['objective_optimization_eligible'] and component in v['components']]
            candidates = [('origin', [key]),
                          ('task', [k for k in compatible if variants[k]['task_family'] == entry['task_family']
                                    and (component != 'task_instructions' or variants[k]['output_contract'] == entry['output_contract'])])]
            if component != 'task_instructions':
                if key.startswith('array_patch_'):
                    candidates += [('related_array_operations', [k for k in compatible if k.startswith('array_patch_')])]
                candidates += [('domain', [k for k in compatible if variants[k]['domain'] == entry['domain']]), ('family', compatible)]
            previous = set()
            binding['expansion_levels'] = []
            for level, members in candidates:
                members = sorted(members)
                # Some task labels span domains only when explicitly compatible.
                members = sorted(set(members) | previous)
                if set(members) == previous:
                    continue
                sid = component + ':' + digest(members)[:16]
                scopes.setdefault(sid, {'component': component, 'members': members,
                                        'repetitions': 'full_configured_count', 'models': 'all_eligible_models',
                                        'judgments': 'rejected_tests_must_be_excluded_at_execution'})
                binding['expansion_scopes'].append(sid)
                binding['expansion_levels'].append({'level': level, 'scope_id': sid})
                previous = set(members)
    return scopes


class SharingScalingTests(unittest.TestCase):
    def test_exact_legacy_scope_and_binding_parity(self):
        rng = random.Random(592)
        variants = {}
        for i in range(80):
            key = ('array_patch_' if i % 3 == 0 else 'other_') + str(i)
            eligible = i % 9 != 0
            components = rng.sample(['established_facts', 'task_instructions', 'analysis_instructions'], rng.randrange(1,4)) if eligible else []
            variants[key] = {'objective_optimization_eligible': eligible,
                             'task_family': 'task'+str(i%5), 'domain': 'domain'+str(i%3),
                             'output_contract': 'contract'+str(i%2),
                             'components': {c: {'expansion_scopes':[]} for c in components}}
        old, new = copy.deepcopy(variants), copy.deepcopy(variants)
        self.assertEqual(legacy_scopes(old), expansion_scopes(new))
        self.assertEqual(old, new)

    def validate_fixture(self, mutate=None):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'test_specs').mkdir()
            (root/'test_specs/t.json').write_text(json.dumps({'id':'t','variants':[{'id':'a'},{'id':'b'}]}))
            entries={k:{'source_file':'test_specs/t.json','objective_optimization_eligible':True,
                        'task_family':'task','output_contract':'text','domain':'scalar',
                        'components':{'established_facts':{'slots':[], 'expansion_scopes':['shared']}}}
                     for k in ['t/a','t/b']}
            data={'variants':entries,'scopes':{'shared':{'members':['t/a','t/b']}}}
            if mutate: mutate(data)
            with patch('optimization.catalog.registration', side_effect=lambda t,v,d:d['variants'][t['id']+'/'+v['id']]):
                return validate(root,data)

    def test_shared_membership_validated_with_same_result(self):
        self.assertEqual(self.validate_fixture(), {'definitions':1,'variants':2,'scopes':1})

    def test_ineligible_member_rejected(self):
        with self.assertRaisesRegex(ValueError,'Incompatible expansion member'):
            self.validate_fixture(lambda d:d['variants']['t/b'].update(objective_optimization_eligible=False))

    def test_missing_component_not_hidden_by_scope_cache(self):
        def mutate(d):
            d['variants']['t/b']['components']['analysis_instructions']={'slots':[], 'expansion_scopes':['shared']}
        with self.assertRaisesRegex(ValueError,'Incompatible expansion member'):
            self.validate_fixture(mutate)

    def test_wrong_task_contract_rejected(self):
        def mutate(d):
            for entry in d['variants'].values():
                entry['components']={'task_instructions':{'slots':[], 'expansion_scopes':['shared']}}
            d['variants']['t/b']['output_contract']='other'
        with self.assertRaisesRegex(ValueError,'Incompatible task instruction contract'):
            self.validate_fixture(mutate)

    def test_duplicate_members_rejected(self):
        with self.assertRaisesRegex(ValueError,'Invalid expansion nesting'):
            self.validate_fixture(lambda d:d['scopes']['shared']['members'].append('t/a'))

    def test_each_binding_origin_membership_still_checked(self):
        with self.assertRaisesRegex(ValueError,'Invalid expansion nesting'):
            self.validate_fixture(lambda d:d['scopes']['shared'].update(members=['t/a']))

    def test_each_binding_nesting_still_checked(self):
        def mutate(d):
            d['scopes']['smaller']={'members':['t/b']}
            d['variants']['t/b']['components']['established_facts']['expansion_scopes'].append('smaller')
        with self.assertRaisesRegex(ValueError,'Invalid expansion nesting'):
            self.validate_fixture(mutate)

if __name__=='__main__':unittest.main()
