"""Run-scoped browser setup consent, outside inference and observation identity."""
import copy
import importlib
import json
import os
import subprocess
import sys
import threading
import time
import uuid

from . import perchance
from .domain import device_tier
from . import inventory
from .judgements import load_tests
from .workflows import Cancelled


def process(app, args, timeout=300):
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    child = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **flags)
    deadline = time.monotonic() + timeout
    try:
        while True:
            if app.cancel_event.is_set():
                raise Cancelled('Stopped during Perchance browser setup')
            if time.monotonic() >= deadline:
                raise RuntimeError('Perchance browser setup exceeded its time limit')
            try:
                out, err = child.communicate(timeout=.2)
                return child.returncode, out, err
            except subprocess.TimeoutExpired:
                continue
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()


def health(app):
    if importlib.util.find_spec('playwright') is None:
        return {'ready': False, 'reason': 'The Playwright browser dependency is missing.'}
    browser = perchance.browser_executable(app.settings)
    if not browser:
        return {'ready': False, 'reason': 'A usable browser executable is missing.'}
    #The production connection uses a separately launched browser and CDP, not Playwright launch.
    from pathlib import Path
    script = ('import sys; sys.path.insert(0,sys.argv[2]); '
              'from workbench.perchance_connection import probe; probe(sys.argv[1])')
    try:
        code, out, err = process(app, [sys.executable, '-c', script, browser,
                                     str(Path(__file__).resolve().parents[1])], timeout=45)
    except (RuntimeError, OSError) as exc:
        return {'ready': False, 'reason': str(exc)}
    return {'ready': code == 0, 'reason': '' if code == 0 else (err or out or 'Browser launch failed')[-2000:]}


def install(app):
    app.set_progress('preflight', 'Installing Perchance browser dependency', 0, 0,
                     'Installing Playwright on the worker computer.')
    code, out, err = process(app, [sys.executable, '-m', 'pip', 'install', '--upgrade', '--force-reinstall', '-r',
                                 str(app.root / 'requirements-perchance.txt')])
    app.log('perchance_setup', out + err)
    if code:
        raise RuntimeError('Perchance dependency installation failed; inspect Logs.')
    importlib.invalidate_caches()
    status = health(app)
    if status['ready']:
        return status
    app.set_progress('preflight', 'Installing Perchance browser', 50, 0,
                     'Installing a managed Chromium browser on the worker computer.')
    code, out, err = process(app, [sys.executable, '-m', 'playwright', 'install', 'chromium'])
    app.log('perchance_setup', out + err)
    if code:
        raise RuntimeError('Perchance browser installation failed; inspect Logs.')
    code, out, err = process(app, [sys.executable, '-c',
                                 'from playwright.sync_api import sync_playwright; p=sync_playwright().start(); '
                                 'print(p.chromium.executable_path); p.stop()'])
    if code or not out.strip():
        raise RuntimeError('Cannot locate the installed Perchance browser: ' + err[-1000:])
    app.settings['perchance_browser'] = out.strip()
    app.save_settings()
    return health(app)


def prepare(app, preparation=None, selection=None, reuse=False):
    context = {'selection': copy.deepcopy(selection), 'preparation': copy.deepcopy(preparation)}
    previous = app.perchance_setup_decision
    if reuse and previous and previous['context'] == context and not previous['consumed'] and previous['status'] == 'declined':
        previous['consumed'] = True
        return
    app.perchance_setup_decision = {'id': uuid.uuid4().hex, 'context': context, 'consumed': reuse,
                                    'status': 'not_scheduled', 'reason': '', 'time': time.time()}
    decision = app.perchance_setup_decision
    if app.demo or (selection is not None and not perchance.selected(selection)):
        return
    app.set_progress('preflight', 'Checking whether Perchance is scheduled', 0, 0,
                     'Checking the 8 GB assignment before other preflight checks.')
    try:
        gpus = [{'name': preparation['gpu_name'], 'total_gib': preparation['vram_gb']}] if preparation else inventory.detect_gpus()
    except Exception:
        return  #The normal preflight reports hardware detection problems.
    if len(gpus) != 1 or device_tier(gpus[0]['total_gib'], gpus[0]['name']) != 8:
        return
    target = {'backend': 'perchance', 'vram_gb': 8, 'gpu_name': gpus[0]['name']}
    plan = perchance.plan(load_tests(app.root / 'test_specs'), app.settings, target, app.store,
                         selection or {'model_id': perchance.MODEL_ID})
    if not plan['pending']:
        decision['status'] = 'no_pending_work'
        return
    app.set_progress('preflight', 'Checking Perchance browser dependency', 0, 0,
                     'Verifying Playwright and browser launch before other preflight checks.')
    status = health(app)
    if status['ready']:
        decision['status'] = 'ready'
        return
    answered = threading.Event()
    decision['status'] = 'awaiting_choice'
    with app.lock:
        app.perchance_setup_answer = None
        app.perchance_setup_event = answered
        app.perchance_setup_prompt = {'id': decision['id'], 'reason': status['reason']}
    app.message = 'Perchance needs browser setup. Install it for this run, or skip Perchance this run.'
    app.set_progress('preflight', 'Waiting for Perchance installation choice', 0, 0, app.message)
    try:
        while not answered.wait(.2):
            if app.cancel_event.is_set():
                raise Cancelled('Stopped while awaiting Perchance installation choice')
        if app.cancel_event.is_set():
            raise Cancelled('Stopped while awaiting Perchance installation choice')
        accepted = app.perchance_setup_answer
    finally:
        with app.lock:
            app.perchance_setup_prompt = None
            app.perchance_setup_event = None
    decision.update(status='install_approved' if accepted else 'declined', approved=accepted, reason=status['reason'])
    app.log('perchance_setup_choice', json.dumps(decision, sort_keys=True))
    app.flush_logs()
    if not accepted:
        return
    try:
        status = install(app)
        if not status['ready']:
            raise RuntimeError('Perchance browser is still unusable after installation: ' + status['reason'])
        decision.update(status='installed', reason='')
    except Cancelled:
        raise
    except Exception as exc:
        decision.update(status='failed', reason=str(exc))
        app.log('perchance_setup', str(exc))


def answer(app, prompt_id, approved):
    if type(approved) is not bool:
        raise ValueError('Installation choice must be Yes or No')
    with app.lock:
        if not app.perchance_setup_prompt or app.perchance_setup_prompt['id'] != prompt_id or app.perchance_setup_event.is_set():
            raise ValueError('This installation prompt is no longer active')
        app.perchance_setup_answer = approved
        app.perchance_setup_event.set()


def skipped(app, selection, preparation):
    decision = app.perchance_setup_decision
    return bool(decision and decision['context'] == {'selection': selection, 'preparation': preparation}
                and decision['status'] in ('declined', 'failed'))
