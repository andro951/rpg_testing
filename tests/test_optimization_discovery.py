"""Real model scanning through the optimizer HTTP boundary; no inference."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from tests.test_workbench_inventory import fake_gguf
from workbench.controller import Controller
from workbench.domain import write_json
from workbench.server import WorkbenchServer


class OptimizationDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'repository'
        self.models = Path(temporary.name) / 'saved models folder'
        self.models.mkdir()
        configured = Controller(self.root)
        configured.configure({'model_root': str(self.models), 'sync_source': False})
        # Reload the JSON setting exactly as a newly started host does.
        self.app = Controller(self.root)
        self.assertIsInstance(self.app.settings['model_root'], str)
        for mock in (
            patch('optimization.runtime.inventory.detect_gpus', return_value=[{'name': 'Fixture GPU', 'total_gib': 16}]),
            patch('optimization.runtime.inventory.executable', return_value='fixture-llama-server'),
            patch.object(self.app, 'backend_version', return_value='fixture-runtime'),
        ):
            mock.start()
            self.addCleanup(mock.stop)
        self.server = WorkbenchServer(('127.0.0.1', 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def options(self):
        url = f'http://127.0.0.1:{self.server.server_port}/api/optimization/options'
        try:
            response = urllib.request.urlopen(url, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def add_models(self, *sizes):
        catalog = []
        for size in sizes:
            filename = f'Qwen3.5-{size}B-Q4_K_M.gguf'
            if not (self.models / filename).exists():
                fake_gguf(self.models / filename, f'Qwen3.5-{size}B')
            catalog.append({'id': f'qwen-{size}b', 'files': [filename], 'required_vram_gb': 8 if size == 9 else 16})
        write_json(self.root / 'models.json', catalog)

    def test_saved_string_folder_returns_real_scanned_models_over_http(self):
        self.add_models(9, 27)
        before = {p.name: p.read_bytes() for p in self.models.glob('*.gguf')}
        status, options = self.options()
        self.assertEqual(status, 200, options)
        self.assertEqual({m['id'] for m in options['models']}, {'qwen-9b', 'qwen-27b'})
        self.assertEqual(options['default_generator'], 'qwen-27b')
        self.assertEqual(options['excluded'], [])
        self.assertFalse(options['simulated'])
        for model in options['models']:
            self.assertEqual(model['metadata']['qwen.context_length'], 32768)
            self.assertEqual(model['provider'], 'native')
            self.assertTrue(model['identity'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.models.glob('*.gguf')})
        self.assertEqual(len(self.app.registry), 2)

    def test_repeated_options_rescans_updated_catalog_and_keeps_existing_identity(self):
        self.add_models(9)
        status, first = self.options()
        self.assertEqual(status, 200, first)
        self.add_models(9, 27)
        status, second = self.options()
        self.assertEqual(status, 200, second)
        self.assertEqual(len(second['models']), 2)
        existing = next(m for m in second['models'] if m['id'] == 'qwen-9b')
        self.assertEqual(first['models'][0]['identity'], existing['identity'])
        # The unchanged artifact's identity should remain stable on a plain rescan.
        status, third = self.options()
        self.assertEqual(status, 200, third)
        self.assertEqual(second['models'], third['models'])
        self.assertEqual(third['default_generator'], 'qwen-27b')

    def test_missing_or_file_folder_returns_actionable_http_error(self):
        file = self.models / 'not-a-directory.txt'
        file.write_text('synthetic fixture', encoding='utf-8')
        for folder in (self.models / 'missing', file):
            with self.subTest(folder=folder):
                self.app.settings['model_root'] = str(folder)
                status, response = self.options()
                self.assertEqual(status, 400, response)
                self.assertIn('Choose an existing folder in Worker setup', response['error'])
        self.assertFalse((self.models / 'missing').exists())

    def test_unconfigured_folder_returns_setup_instruction(self):
        self.app.settings['model_root'] = ''
        status, response = self.options()
        self.assertEqual(status, 400, response)
        self.assertIn('Choose the host models folder', response['error'])


if __name__ == '__main__':
    unittest.main()
