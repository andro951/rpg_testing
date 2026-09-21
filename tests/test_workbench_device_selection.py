import unittest
from workbench.native import select_device
from workbench.execution_policy import RunFailure

class NativeDeviceTests(unittest.TestCase):
    def test_explicit_device_selection(self):
        report='Vulkan0: Intel Iris Xe\nVulkan1: NVIDIA GeForce GTX 1080\nCUDA0: NVIDIA GeForce GTX 1080'
        self.assertEqual(select_device(report,'NVIDIA GeForce GTX 1080'),'CUDA0')
        self.assertEqual(select_device(report.split('\nCUDA0')[0],'NVIDIA GeForce GTX 1080'),'Vulkan1')
    def test_ambiguous_or_wrong_gpu_is_not_selected(self):
        for text in ('Vulkan0: Intel Iris','CUDA0: A100\nCUDA1: A100'):
            with self.assertRaises(RunFailure):select_device(text,'A100')

if __name__=='__main__':unittest.main()
