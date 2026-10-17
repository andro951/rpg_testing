"""Per-job loopback port selection without starting an inference process."""
import unittest
from workbench.native import NativeBackend


class NativePortTests(unittest.TestCase):
    def test_default_and_independent_job_ports_are_used_by_transport_and_launch(self):
        for settings,port in (({},1235),({'inference_port':23151},23151),({'inference_port':23152},23152)):
            with self.subTest(port=port):
                backend=NativeBackend(settings,{})
                self.assertEqual(backend.transport.port,port)
                args=backend.launch_arguments('llama-server',{'paths':['model.gguf']},{'allocated_tokens':32768},'')
                self.assertEqual(args[args.index('--port')+1],str(port))
                self.assertEqual(args[args.index('--parallel')+1],'1')
                self.assertEqual(args[args.index('--ctx-size')+1],'32768')

    def test_invalid_ports_fail_before_transport_or_process_creation(self):
        for value in (True,None,1235.0,'1235',0,1023,65536):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'inference_port'):
                NativeBackend({'inference_port':value},{})
