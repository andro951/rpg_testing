"""Run the new suite twice in an isolated workbench using explicit oracle mocks."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_builder.builder import ROOT, compile_test, oracle
from workbench.controller import Controller
from workbench.demo_native import DemoNative
from workbench.domain import read_json, write_json


def main():
    responses = {}
    expected = 0
    with tempfile.TemporaryDirectory(prefix='patch-suite-smoke-') as folder:
        root = Path(folder)
        for fixture in read_json(ROOT/'fixtures.json')['fixtures']:
            draft = compile_test(fixture)
            review = {'status':'accepted', 'prompt_digest':draft['prompt_builder']['prompt_digest']}
            # Synthetic approvals exist only in this temporary mock project.
            test = compile_test(fixture, {draft['id']:{'assistant':review, 'isaac':review}})
            write_json(root/'test_specs'/(test['id']+'.json'), test)
            expected += len(test['variants']) * test['repetitions']
            answer = oracle(fixture)
            for variant in test['variants']:
                responses[variant['steps'][0]['prompt']] = answer if isinstance(answer,str) else json.dumps(answer[0])
        requests = []
        class OracleMock(DemoNative):
            def generate(self, messages, settings, schema, cache='default', cancel=None):
                content = messages[-1]['content']
                requests.append(content)
                return {'text':responses[content], 'finish_reason':'stop', 'simulated':True,
                        'usage':{}, 'timings':{}, 'raw_chunks':[], 'cached_tokens':None}
        app = Controller(root, demo=True)
        app.selftest = lambda: None
        with patch('workbench.demo_native.DemoNative', OracleMock):
            app.run()
            records = app.store.all()
            assert len(records) == expected, (len(records), app.report)
            assert all(r['simulated'] and r['score']['exact_match'] for r in records)
            saved = {p:p.read_bytes() for p in app.store.root.glob('*/*.json')}
            before = len(requests)
            app.run()
            assert app.completed_now == 0
            assert len(requests) == before
            assert app.report['plan']['pending'] == 0
            assert app.report['plan']['complete'] == expected
            assert all(p.read_bytes()==value for p,value in saved.items())
        print(f'PASS: {expected} simulated observations. Second run makes no calls and preserves every saved byte.')
        print('No model inference, user approvals, or study results were created.')


if __name__ == '__main__':
    main()
