"""Real browser/HTTP/UI with simulated model generation and objective trials."""
import os
import json
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.suite_fixtures import LEGACY_ROOT, fixture_path, legacy_sharing

from tests.test_prompt_optimization import ROOT, MockRuntime, MockGenerator, native
from workbench.controller import Controller
from workbench.server import WorkbenchServer
from optimization.storage import Store


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for folder in ('test_specs', 'examples', 'docs/prompt-optimization', 'optimization/definitions'):
            shutil.copytree(fixture_path(folder), root / folder)
        app = Controller(root, demo=True)
        cohort = {'models': [native()], 'gpu': {'name': 'Mock GPU', 'total_gib': 8},
                  'default_generator': 'local-a', 'excluded': [], 'simulated': False}
        server = WorkbenchServer(('127.0.0.1', 0), app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        created = []
        def factory(owner, options):
            runtime = MockRuntime(owner, options)
            created.append(runtime)
            return runtime
        try:
            with patch('optimization.templates.catalog', side_effect=legacy_sharing), \
                 patch('optimization.runtime.discover', return_value=cohort), \
                 patch('optimization.engine.discover', return_value=cohort), \
                 patch('optimization.engine.Runtime', side_effect=factory), sync_playwright() as playwright:
                executable = os.environ.get('REPORT_BROWSER_EXECUTABLE')
                browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
                page = browser.new_page(viewport={'width': 1440, 'height': 1080})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                pending_scans = []
                page.route('**/api/optimization/options', lambda route: pending_scans.append(route))
                codex_options = {'models': [
                    {'id': 'fake-gpt-a', 'name': 'Synthetic GPT A', 'efforts': ['low', 'high'], 'default_effort': 'low'},
                    {'id': 'fake-gpt-b', 'name': 'Synthetic GPT B', 'efforts': ['medium', 'high'], 'default_effort': 'medium'}],
                    'default_model': 'fake-gpt-a'}
                pending_codex = []
                page.route('**/api/optimization/codex-options', lambda route: pending_codex.append(route))
                page.get_by_role('button', name='Prompt Optimization', exact=True).click()
                expect(page.locator('#optimization-provider')).to_have_value('codex')
                for id in ('optimization-codex-model', 'optimization-codex-effort'):
                    expect(page.locator('#' + id)).to_be_disabled()
                    expect(page.locator('#' + id)).to_have_attribute('aria-busy', 'true')
                    expect(page.locator('#' + id)).to_contain_text('Loading Models')
                    expect(page.locator('#' + id + '-loading')).to_be_visible()
                expect(page.locator('#optimization-temperature_min')).to_be_hidden()
                expect(page.locator('#optimization-generator')).to_be_hidden()
                page.locator('#optimization-provider').select_option('local')
                for id in ('optimization-generator', 'optimization-origin-model'):
                    select = page.locator('#' + id)
                    expect(select).to_be_disabled()
                    expect(select).to_have_attribute('aria-busy', 'true')
                    expect(select.locator('option')).to_have_text('Loading Models')
                    expect(select).to_have_css('background-color', 'rgb(72, 57, 36)')
                    expect(select).to_have_css('color', 'rgb(255, 195, 111)')
                    expect(page.locator('#' + id + '-loading')).to_be_visible()
                expect(page.locator('#optimization-refresh-models')).to_be_disabled()
                expect(page.locator('#optimization-start')).to_be_disabled()
                expect(page.locator('#optimization-scope')).to_have_text('Loading models on the host…')
                page.wait_for_function('() => document.getElementById("optimization-generator-loading").getAnimations().some(animation => animation.playState === "running")')
                page.screenshot(path=str(ROOT / '.local/opro-model-loading-preview.png'))
                # Re-entering during a scan shares the request instead of racing another scan.
                page.locator('nav button[data-page="overview"]').click()
                page.get_by_role('button', name='Prompt Optimization', exact=True).click()
                assert len(pending_scans) == 1
                assert len(pending_codex) == 1
                pending_scans.pop().fulfill(status=200, content_type='application/json', body=json.dumps(cohort))
                pending_codex.pop().fulfill(status=200, content_type='application/json', body=json.dumps(codex_options))
                page.unroute('**/api/optimization/options')
                page.unroute('**/api/optimization/codex-options')
                page.route('**/api/optimization/codex-options', lambda route: route.fulfill(
                    status=200, content_type='application/json', body=json.dumps(codex_options)))
                expect(page.locator('#optimization-generator')).to_have_value('local-a')
                expect(page.locator('#optimization-origin-model')).to_have_value('local-a')
                for id in ('optimization-generator', 'optimization-origin-model'):
                    expect(page.locator('#' + id)).to_be_enabled()
                    expect(page.locator('#' + id)).to_have_attribute('aria-busy', 'false')
                    expect(page.locator('#' + id + '-loading')).to_be_hidden()
                    assert not page.locator('#' + id + '-loading').evaluate('(spinner) => spinner.getAnimations().length')
                    assert page.locator('#' + id).evaluate('(select) => select.style.backgroundColor') == ''
                expect(page.get_by_role('button', name='Start new session', exact=True)).to_be_enabled()
                page.locator('#optimization-generator').select_option('')
                expect(page.locator('#optimization-start')).to_be_disabled()
                page.locator('#optimization-generator').select_option('local-a')
                expect(page.locator('#optimization-start')).to_be_enabled()
                # Independent Codex selectors and writer-specific controls/payloads.
                page.locator('#optimization-provider').select_option('codex')
                expect(page.locator('#optimization-codex-model')).to_have_value('fake-gpt-a')
                expect(page.locator('#optimization-codex-effort')).to_have_value('low')
                page.locator('#optimization-codex-model').select_option('fake-gpt-b')
                expect(page.locator('#optimization-codex-effort')).to_have_value('medium')
                page.locator('#optimization-codex-effort').select_option('high')
                expect(page.locator('#optimization-reasoning')).to_be_hidden()
                assert page.evaluate('() => PromptOptimization.Settings()') == {'max_attempts': 20}
                captured = []
                page.route('**/api/optimization/run', lambda route: (captured.append(route.request.post_data_json), route.fulfill(
                    status=200, content_type='application/json', body='{}')))
                with page.expect_response('**/api/optimization/run'):
                    page.get_by_role('button', name='Start new session', exact=True).click()
                page.wait_for_function('() => !PromptOptimization.Loading && !polling')
                assert captured[0]['prompt_writer'] == {'provider': 'codex', 'model': 'fake-gpt-b', 'effort': 'high'}
                assert 'generator_id' not in captured[0]
                assert captured[0]['settings'] == {'max_attempts': 20}
                page.unroute('**/api/optimization/run')
                page.evaluate('() => { PromptOptimization.PendingSessionIds = null; }')
                # A Codex dependency failure leaves native prompt writing available.
                page.unroute('**/api/optimization/codex-options')
                page.route('**/api/optimization/codex-options', lambda route: route.fulfill(
                    status=409, content_type='application/json', body='{"error":"Synthetic Codex sign-in missing"}'))
                page.locator('#optimization-refresh-models').click()
                expect(page.locator('#optimization-codex-status')).to_contain_text('Synthetic Codex sign-in missing')
                expect(page.locator('#optimization-start')).to_be_disabled()
                page.locator('#optimization-provider').select_option('local')
                expect(page.locator('#optimization-start')).to_be_enabled()
                expect(page.locator('#optimization-temperature_min')).to_be_visible()
                page.unroute('**/api/optimization/codex-options')
                page.route('**/api/optimization/codex-options', lambda route: route.fulfill(
                    status=200, content_type='application/json', body=json.dumps(codex_options)))
                # Returning to the tab scans again and retains valid selections.
                cohort['models'].append(native('local-b'))
                page.locator('nav button[data-page="overview"]').click()
                page.get_by_role('button', name='Prompt Optimization', exact=True).click()
                expect(page.locator('#optimization-generator option')).to_have_count(3)
                expect(page.locator('#optimization-origin-model option')).to_have_count(2)
                page.locator('#optimization-generator').select_option('local-b')
                page.locator('#optimization-origin-model').select_option('local-b')
                page.locator('nav button[data-page="overview"]').click()
                with page.expect_response('**/api/optimization/options'):
                    page.get_by_role('button', name='Prompt Optimization', exact=True).click()
                expect(page.locator('#optimization-generator')).to_have_value('local-b')
                expect(page.locator('#optimization-origin-model')).to_have_value('local-b')
                # A disappeared selection falls back to an available model.
                cohort['models'].pop()
                page.locator('nav button[data-page="overview"]').click()
                page.get_by_role('button', name='Prompt Optimization', exact=True).click()
                expect(page.locator('#optimization-generator')).to_have_value('local-a')
                expect(page.locator('#optimization-origin-model')).to_have_value('local-a')
                # A failed scan reports why; entering again retries normally.
                page.route('**/api/optimization/options', lambda route: route.fulfill(
                    status=409, content_type='application/json', body='{"error":"Fixture model scan unavailable"}'))
                page.locator('nav button[data-page="overview"]').click()
                page.get_by_role('button', name='Prompt Optimization', exact=True).click()
                expect(page.locator('#alert')).to_be_visible()
                expect(page.locator('#alert-text')).to_have_text('Fixture model scan unavailable')
                for id in ('optimization-generator', 'optimization-origin-model'):
                    expect(page.locator('#' + id)).to_be_disabled()
                    expect(page.locator('#' + id)).to_have_attribute('aria-busy', 'false')
                    expect(page.locator('#' + id)).to_contain_text('Unable to load models')
                    expect(page.locator('#' + id + '-loading')).to_be_hidden()
                expect(page.locator('#optimization-refresh-models')).to_be_enabled()
                expect(page.locator('#optimization-start')).to_be_disabled()
                page.locator('#alert .close-dialog').click()
                page.unroute('**/api/optimization/options')
                page.locator('nav button[data-page="overview"]').click()
                with page.expect_response('**/api/optimization/options'):
                    page.get_by_role('button', name='Prompt Optimization', exact=True).click()
                expect(page.locator('#optimization-generator')).to_have_value('local-a')
                # An empty successful scan is distinguishable from a pending or failed scan.
                page.route('**/api/optimization/options', lambda route: route.fulfill(
                    status=200, content_type='application/json', body=json.dumps({**cohort, 'models': [], 'default_generator': None})))
                page.locator('#optimization-refresh-models').click()
                expect(page.locator('#optimization-generator')).to_contain_text('No prompt-writing models available')
                expect(page.locator('#optimization-origin-model')).to_contain_text('No models available')
                expect(page.locator('#optimization-generator')).to_be_disabled()
                expect(page.locator('#optimization-origin-model')).to_be_disabled()
                expect(page.locator('#optimization-refresh-models')).to_be_enabled()
                expect(page.locator('#optimization-generator-loading')).to_be_hidden()
                page.unroute('**/api/optimization/options')
                page.locator('#optimization-refresh-models').click()
                expect(page.locator('#optimization-generator')).to_have_value('local-a')
                expect(page.locator('#optimization-origin-model')).to_have_value('local-a')
                expect(page.locator('#optimization-max_attempts')).to_have_value('20')
                expect(page.locator('#optimization-reasoning')).not_to_be_checked()
                expect(page.locator('#optimization-context_tokens')).to_have_count(0)
                expect(page.locator('#optimization-output_reserve')).to_have_count(0)
                assert 'context_tokens' not in page.evaluate('() => PromptOptimization.Settings()')
                assert 'output_reserve' not in page.evaluate('() => PromptOptimization.Settings()')
                page.get_by_role('button', name='Start new session', exact=True).click()
                expect(page.locator('#optimization-status')).to_contain_text('perfect', timeout=30000)
                expect(page.locator('#optimization-ranking')).to_contain_text('100.0%')
                assert len(created[0].trials) == 6
                page.locator('#optimization-history details').first.locator('summary').click()
                page.get_by_role('button', name='Exact generation request', exact=True).click()
                expect(page.locator('#optimization-evidence')).to_be_visible()
                expect(page.locator('#optimization-evidence-content')).to_contain_text('SYSTEM_MESSAGE:')
                page.locator('#optimization-evidence').get_by_role('button', name='Close', exact=True).click()
                page.locator('#optimization-max_attempts').fill('30')
                with page.expect_response('**/api/optimization/settings') as response:
                    page.get_by_role('button', name='Apply settings to selected session', exact=True).click()
                assert response.value.status == 200
                expect(page.locator('#optimization-status')).to_contain_text('1/30 generation attempts')
                saved = Store(root).list()[0]
                assert 'context_tokens' not in saved['settings'] and 'output_reserve' not in saved['settings']
                assert len(saved['configuration_history']) == 1
                with page.expect_response('**/api/optimization/run'):
                    page.get_by_role('button', name='Continue session', exact=True).click()
                if app.thread:
                    app.thread.join(10)
                    assert not app.thread.is_alive()
                page.wait_for_function('() => state && !state.busy')
                assert len(created) == 2 and created[1].trials == [] and created[1].requests == [], [(len(runtime.trials), len(runtime.requests)) for runtime in created]
                with page.expect_download() as download:
                    page.get_by_role('button', name='Export session', exact=True).click()
                archive = root / 'session.zip'
                download.value.save_as(archive)
                assert archive.stat().st_size > 0
                with page.expect_response('**/api/optimization/import') as response:
                    page.locator('#page-optimization input[type=file]').set_input_files(str(archive))
                assert response.value.status == 200
                page.wait_for_function('() => !PromptOptimization.Loading && !polling')
                expect(page.locator('#optimization-status')).to_contain_text('perfect')
                screenshot = os.environ.get('WORKBENCH_SCREENSHOT')
                if screenshot:
                    page.screenshot(path=screenshot, full_page=True)
                assert not errors, errors
                assert app.store.all() == []
                # A second session uses Codex through the actual HTTP/controller/engine path
                # and selects that new session instead of continuing to display the old one.
                old_session = saved['id']
                def simulated_codex(owner, session, save):
                    from types import SimpleNamespace
                    session.setdefault('codex_thread', {'id': 'synthetic-' + session['id'], 'host_identity': 'synthetic-worker'})
                    save()
                    generator = MockGenerator(created[-1])
                    return SimpleNamespace(propose=generator.propose, close=lambda: None, cancel=lambda: None, load_metadata={})
                with patch('optimization.codex.discover', return_value=codex_options), \
                     patch('optimization.codex.Generator', side_effect=simulated_codex):
                    page.locator('#optimization-provider').select_option('codex')
                    page.locator('#optimization-codex-model').select_option('fake-gpt-b')
                    page.locator('#optimization-codex-effort').select_option('high')
                    with page.expect_response('**/api/optimization/run') as started:
                        page.get_by_role('button', name='Start new session', exact=True).click()
                    assert started.value.status == 202
                    try:
                        expect(page.locator('#optimization-status')).to_contain_text('Writer: Codex fake-gpt-b · high', timeout=30000)
                    except AssertionError:
                        (ROOT/'.local/database-suite-optimization-failure.json').write_text(json.dumps({
                            'app_message':app.message,'failure':app.failure,
                            'saved_sessions':Store(root).list(),
                            'ui':page.evaluate('() => ({selected: PromptOptimization.Selected, pending: [...(PromptOptimization.PendingSessionIds || [])], state})')},default=str,indent=2),encoding='utf-8')
                        raise
                    expect(page.locator('#optimization-status')).to_contain_text('perfect', timeout=30000)
                    session_id = page.locator('#optimization-sessions').input_value()
                    assert session_id != old_session
                    codex_session = Store(root).load(session_id)
                    assert codex_session['prompt_writer'] == {'provider': 'codex', 'model': 'fake-gpt-b', 'effort': 'high'}
                    assert codex_session['codex_thread']['id'] == 'synthetic-' + session_id
                    assert len(created[-1].trials) == 6
                    page.wait_for_function('() => state && !state.busy')
                    with page.expect_response('**/api/optimization/run'):
                        page.get_by_role('button', name='Continue session', exact=True).click()
                    if app.thread:
                        app.thread.join(10)
                    page.wait_for_function('() => state && !state.busy')
                    assert created[-1].trials == [] and created[-1].requests == []
                    assert Store(root).load(session_id)['codex_thread']['id'] == codex_session['codex_thread']['id']
                assert not errors, errors
                browser.close()
        finally:
            app.control('stop')
            if app.thread:
                app.thread.join(10)
            server.shutdown()
            server.server_close()
            thread.join(5)
    print('PASS: Codex/local selectors, effort capabilities, amber loading indicators, exact provider payloads, dependency recovery, native and Codex HTTP/controller/engine sessions, new-session selection, full rankings, evidence, resume and portable export/import (simulated inference).')


if __name__ == '__main__':
    main()
