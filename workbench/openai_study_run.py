"""Explicit isolated GPT study entry point. Never starts from application boot."""
from __future__ import annotations
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from .api_budget import BudgetLedger
from .domain import load_tests
from .openai_api import OpenAITransport
from .openai_study import OpenAIStudyController


def main(argv=None):
    parser=argparse.ArgumentParser(description='Run authorized isolated GPT study with a combined hard USD cap')
    parser.add_argument('--key-file',type=Path,required=True)
    parser.add_argument('--budget-usd',required=True)
    parser.add_argument('--coverage-id',required=True)
    parser.add_argument('--desktop-legacy-completion-receipt',type=Path,required=True)
    parser.add_argument('--effort',choices=['low','medium','high','xhigh','max'],default='medium')
    args=parser.parse_args(argv)
    try:
        if not Decimal('0')<Decimal(args.budget_usd)<=Decimal('100'):
            parser.error('This study is approved for at most USD100 combined')
    except InvalidOperation:
        parser.error('Invalid USD budget')
    root=Path(__file__).resolve().parent.parent
    # This durable external receipt is written only by the verified-completion
    # coordinator after checking every required desktop local model + Perchance.
    receipt=json.loads(args.desktop_legacy_completion_receipt.read_text(encoding='utf-8'))
    if receipt.get('all_desktop_models_and_perchance_complete') is not True or not receipt.get('evidence'):
        parser.error('Verified desktop legacy-completion receipt required')
    key=args.key_file.read_text(encoding='utf-8-sig').strip()
    if not key or '\n' in key or '\r' in key:
        parser.error('Key file must contain only the API key')
    transport=OpenAITransport(key)
    ledger=BudgetLedger(root/'.local'/'openai-study'/'combined-budget.json',args.budget_usd)
    controller=OpenAIStudyController(root,load_tests(root/'test_specs'),
        ['gpt-6-luna','gpt-6.1-sol'],args.effort,ledger,transport,
        coverage_id=args.coverage_id,approved_controls=True)
    try:
        outcome=controller.run()
    except Exception as exc:
        # Sanitized output only; raw evidence remains in authenticated result files.
        print(json.dumps({'status':'stopped','reason_type':type(exc).__name__,
                          'budget':ledger.snapshot()['committed_usd']}),flush=True)
        return 2
    print(json.dumps({**outcome,'committed_usd':ledger.snapshot()['committed_usd']}),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
