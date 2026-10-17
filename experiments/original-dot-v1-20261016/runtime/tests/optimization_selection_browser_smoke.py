"""Real result-table → evidence → OPRO navigation; synthetic model inference only."""
import copy
import json
import os
import sys
import threading
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_optimization_selection import SelectionTests,ROOT
from tests.test_prompt_optimization import MockRuntime
from test_builder.builder import oracle
from workbench.domain import read_json
from workbench.server import WorkbenchServer
from workbench.workflows import evaluate
from optimization.storage import Store
from optimization.templates import bindings,render


class DatabaseRuntime(MockRuntime):
    def evaluate(self,model,case,candidate,repetition):
        self.trials.append((model['id'],case['id'],candidate,repetition))
        fixture=next(f for f in read_json(ROOT/'test_builder/fixtures.json')['fixtures'] if f['id']==case['test']['prompt_builder']['fixture'])
        outputs={'patch':json.dumps(oracle(fixture)[0])}
        messages=render(candidate,bindings(case)) if candidate else [{'role':'user','content':case['variant']['steps'][0]['prompt']}]
        return {'outputs':outputs,'calls':[{'step':'patch','text':outputs['patch'],'request_messages':messages,'finish_reason':'stop'}],
                'score':evaluate(case['test'],case['variant'],outputs),'measurement_valid':True,'simulated':True}


def main():
    fixture=SelectionTests();fixture.setUp()
    record=fixture.record()
    server=WorkbenchServer(('127.0.0.1',0),fixture.app)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    runtimes=[]
    def runtime(app,cohort):
        result=DatabaseRuntime(app,cohort);runtimes.append(result);return result
    codex={'models':[{'id':'synthetic-gpt','name':'Synthetic GPT','efforts':['low'],'default_effort':'low'}],'default_model':'synthetic-gpt'}
    try:
        with patch('optimization.runtime.discover',return_value=fixture.cohort),patch('optimization.engine.discover',return_value=fixture.cohort), \
             patch('optimization.codex.discover',return_value=codex),patch('optimization.engine.Runtime',side_effect=runtime),sync_playwright() as p:
            executable=os.environ.get('REPORT_BROWSER_EXECUTABLE')
            browser=p.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
            context=browser.new_context(viewport={'width':1440,'height':1080})
            errors=[]
            def observe(page):
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.on('console',lambda message:print('Browser error:',message.text,flush=True) if message.type=='error' else None)
            context.on('page',observe)
            table=context.new_page();table.goto(base+'/results/')
            if errors:raise AssertionError(errors)
            if not table.locator('tr[data-kind=case] td[data-outcome=fail] button').count():
                raise AssertionError(table.locator('body').inner_text()[:2500])
            with table.expect_popup() as opened:
                table.locator('tr[data-kind=case] td[data-outcome=fail] button').first.click()
            detail=opened.value
            expect(detail.get_by_role('heading',level=1)).to_have_text('FAIL')
            action=detail.get_by_role('button',name='Optimize this prompt (OPRO)',exact=True)
            expect(action).to_be_enabled()
            assert len(Store(fixture.root).list())==0
            action.click()
            expect(detail.locator('#page-optimization')).to_be_visible()
            expect(detail.locator('#optimization-test')).to_have_value(record['test_id'])
            expect(detail.locator('#optimization-presentation')).to_have_value('full_paths')
            expect(detail.locator('#optimization-origin-model')).to_have_value('local-a')
            expect(detail.locator('#optimization-target-details')).to_contain_text('saved result')
            expect(detail.get_by_role('button',name='Continue session',exact=True)).to_be_disabled()
            assert len(Store(fixture.root).list())==0
            detail.locator('#optimization-provider').select_option('local')
            expect(detail.locator('#optimization-start')).to_be_enabled()
            (ROOT/'.local').mkdir(exist_ok=True)
            detail.screenshot(path=str(ROOT/'.local/opro-selection-ready.png'),full_page=True)
            with detail.expect_response('**/api/optimization/run') as started:
                detail.locator('#optimization-start').click()
            assert started.value.status==202,started.value.text()
            payload=started.value.request.post_data_json
            assert payload['target']['test_id']==record['test_id']
            assert payload['target']['variant_id']=='full_paths'
            assert payload['source_result']=={'model_id':'local-a','case_id':record['case_id']}
            expect(detail.locator('#optimization-status')).to_contain_text('perfect',timeout=30000)
            saved=Store(fixture.root).list()[0]
            assert saved['scope']['task_type']=='Database Copy'
            assert saved['scope']['target']['variant_id']=='full_paths'
            assert saved['source_result']['case_id']==record['case_id']
            assert len(runtimes[-1].trials)==72
            assert len(runtimes[-1].requests)==1
            assert 'Saved result selected by the user' in runtimes[-1].requests[0]['messages'][0]['content']
            detail.wait_for_function('() => state && !state.busy')
            detail.get_by_role('button',name='Continue session',exact=True).click()
            detail.wait_for_function('() => state && !state.busy')
            if fixture.app.thread:fixture.app.thread.join(10)
            assert runtimes[-1].trials==[] and runtimes[-1].requests==[]

            manual=context.new_page();manual.goto(base+'/#'+urlencode({'page':'optimization','test_id':record['test_id'],'variant_id':'full_paths','definition_id':'0'*64,'origin_model_id':'local-a'}))
            expect(manual.locator('#optimization-target-details')).to_contain_text('has changed')
            expect(manual.locator('#optimization-start')).to_be_disabled()
            manual.get_by_role('button',name='Use current test version').click()
            expect(manual.locator('#optimization-start')).to_be_enabled()
            manual.locator('#optimization-test').select_option('db_v3_update_field__value_patch')
            assert manual.locator('#optimization-presentation option').all_text_contents()==['Normal JSON','Full paths']

            missing=context.new_page();missing.goto(base+'/#'+urlencode({'page':'optimization',**saved['scope']['target'],'origin_model_id':'not-installed'}))
            expect(missing.locator('#optimization-target-details')).to_contain_text('recorded model is unavailable')
            expect(missing.locator('#optimization-start')).to_be_disabled()
            missing.locator('#optimization-origin-model').select_option('local-a')
            expect(missing.locator('#optimization-start')).to_be_enabled()
            assert len(Store(fixture.root).list())==1
            assert not errors,errors
            browser.close()
    finally:
        fixture.app.control('stop')
        if fixture.app.thread:fixture.app.thread.join(10)
        server.shutdown();server.server_close();thread.join(5)
        fixture.doCleanups()
    print('PASS: real table/result/OPRO navigation, exact test/presentation/model, no automatic inference, generic Copy optimization, source feedback, resume, changed-version confirmation and unavailable-model recovery. Synthetic inference only.')


if __name__=='__main__':main()
