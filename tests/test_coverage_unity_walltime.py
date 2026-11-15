"""Run-scoped Slurm walltime is allocation metadata, never trial semantics."""
import base64
import copy
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest

from optimization.coverage_unity import allocation_walltime, bundle


class UnityWalltimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.app = SimpleNamespace(root=Path(temporary.name), settings={'backend': 'llamacpp'})
        self.worker = {'model_id': 'synthetic', 'model': {'id': 'synthetic'},
                       'model_path': '/models/synthetic.gguf', 'runtime_path': '/runtime/server',
                       'python': '/runtime/python', 'constraint': 'gpu', 'qos': 'normal',
                       'remote_base': '/runs', 'ssh': ['ssh', 'authorized-host'],
                       'inference_port': 24501, 'kind': 'unity'}
        self.state = {'id': 'synthetic-batch', 'suite_digest': 'frozen-suite',
                      'scope': {'workflow': 'unchanged', 'definitions': ['frozen']},
                      'workers': [self.worker]}

    def unpack(self, packet):
        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(packet['archive'])), mode='r:gz') as archive:
            return (archive.extractfile('coverage.sbatch').read().decode(),
                    json.load(archive.extractfile('.local/workbench/settings.json')),
                    json.load(archive.extractfile('models.json')))

    def test_default_stays_four_hours_and_preserves_legacy_manifest_shape(self):
        packet = bundle(self.app, self.state, self.worker)
        script, _, _ = self.unpack(packet)
        self.assertIn('#SBATCH --time=04:00:00\n', script)
        self.assertNotIn('allocation', packet['manifest'])
        self.assertEqual(allocation_walltime(), '04:00:00')

    def test_override_changes_allocation_only_and_records_durable_provenance(self):
        before = copy.deepcopy((self.state, self.worker, self.app.settings))
        baseline = bundle(self.app, self.state, self.worker)
        override = {**self.worker, 'walltime': '120:00:00'}
        changed = bundle(self.app, self.state, override)
        old_script, old_settings, old_models = self.unpack(baseline)
        new_script, new_settings, new_models = self.unpack(changed)
        self.assertEqual(new_script, old_script.replace('--time=04:00:00', '--time=5-00:00:00'))
        self.assertEqual(old_settings, new_settings)
        self.assertEqual(old_models, new_models)
        self.assertEqual(changed['manifest']['allocation'], {'walltime': '5-00:00:00'})
        self.assertEqual({k: v for k, v in changed['manifest'].items() if k != 'allocation'}, baseline['manifest'])
        self.assertEqual(changed['token'], baseline['token'])
        self.assertEqual(changed['root'], baseline['root'])
        self.assertEqual((self.state, self.worker, self.app.settings), before)

    def test_valid_explicit_limits(self):
        for raw, expected in [('00:00:01', '00:00:01'), ('23:59:59', '23:59:59'),
                              ('24:00:00', '1-00:00:00'), ('1-03:04:05', '1-03:04:05'),
                              ('5-00:00:00', '5-00:00:00')]:
            with self.subTest(raw=raw):
                self.assertEqual(allocation_walltime(raw), expected)

    def test_invalid_or_excessive_limits_fail_before_bundle_submission(self):
        for raw in [None, 4, True, '', '4:00:00', '00:00:00', '00:60:00', '00:00:60',
                    '1-24:00:00', '5-00:00:01', '121:00:00', '6-00:00:00',
                    '-1:00:00', '04:00:00\n#SBATCH --gpus=8', ' 04:00:00', 'infinite']:
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'walltime'):
                bundle(self.app, self.state, {**self.worker, 'walltime': raw})


if __name__ == '__main__':
    unittest.main()
