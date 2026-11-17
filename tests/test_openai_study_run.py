import io,json,tempfile,unittest
from pathlib import Path
from contextlib import redirect_stdout,redirect_stderr
from unittest.mock import patch,MagicMock
from workbench.openai_study_run import main
class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);self.key=root/'key';self.receipt=root/'receipt'
        self.key.write_text('fake-secret-not-a-real-key')
        self.receipt.write_text(json.dumps({'all_desktop_models_and_perchance_complete':True,'evidence':['verified receipt']}))
        self.args=['--key-file',str(self.key),'--budget-usd','100','--coverage-id','test','--desktop-legacy-completion-receipt',str(self.receipt)]
    def test_gate_before_key_or_network(self):
        self.receipt.write_text('{}');self.key.unlink()
        with patch('workbench.openai_study_run.OpenAITransport') as t,redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):main(self.args)
            t.assert_not_called()
    def test_over_cap_before_network(self):
        self.args[3]='101'
        with patch('workbench.openai_study_run.OpenAITransport') as t,redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):main(self.args)
            t.assert_not_called()
    def test_order_cap_and_sanitized_failure(self):
        with patch('workbench.openai_study_run.OpenAITransport') as t,patch('workbench.openai_study_run.BudgetLedger') as b,patch('workbench.openai_study_run.load_tests',return_value=[]),patch('workbench.openai_study_run.OpenAIStudyController') as c,redirect_stdout(io.StringIO()) as out:
            b.return_value.snapshot.return_value={'committed_usd':'2'}
            c.return_value.run.side_effect=RuntimeError('fake-secret-not-a-real-key')
            self.assertEqual(main(self.args),2)
            self.assertEqual(c.call_args.args[2],['gpt-6-luna','gpt-6.1-sol'])
            self.assertEqual(b.call_args.args[1],'100')
            self.assertNotIn('fake-secret',out.getvalue())
if __name__=='__main__':unittest.main()
