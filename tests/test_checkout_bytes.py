"""Manifest evidence and generated grammar identities survive Windows checkout."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CheckoutBytesTests(unittest.TestCase):
    def assert_checkout_preserves(self, sources):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            subprocess.run(['git', 'init', '--quiet', str(root)], check=True, capture_output=True)
            (root/'.gitattributes').write_bytes((ROOT/'.gitattributes').read_bytes())
            # Positive control proves this really exercises Windows-style text
            # conversion, even when the regression runs on a Linux worker.
            control = 'ordinary-checkout-control.txt'
            files = {**sources, control: b'ordinary text\nsecond line\n'}
            for name, content in files.items():
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            git = ['git', '-C', str(root), '-c', 'core.autocrlf=true',
                   '-c', 'core.eol=crlf', '-c', 'core.safecrlf=false']
            subprocess.run([*git, 'add', '--', '.gitattributes', *files],
                           check=True, capture_output=True)
            for name in files:
                (root/name).unlink()
            subprocess.run([*git, 'checkout-index', '--force', '--', *files],
                           check=True, capture_output=True)
            self.assertEqual((root/control).read_bytes(), b'ordinary text\r\nsecond line\r\n')
            for name, expected in sources.items():
                with self.subTest(file=name):
                    self.assertEqual((root/name).read_bytes(), expected)

    def test_archived_evidence_checkout_preserves_exact_captured_bytes(self):
        archive = Path('archives/pre-template-builder')
        source_manifest = json.loads((ROOT/archive/'regression-test-sources/manifest.json').read_text())
        paths = [archive/'regression-test-sources'/entry['file'] for entry in source_manifest['files']]
        prompt = json.loads((ROOT/archive/'prompts/patch-suite/manifest.json').read_text())['prompts'][0]
        paths.extend(archive/prompt[key] for key in ('file', 'review_file'))
        sources = {path.as_posix(): (ROOT/path).read_bytes() for path in paths}
        # Exact archives must not even normalize an intentionally mixed-ending
        # captured text file while adding it to Git's index.
        sources[(archive/'checkout-regression/mixed.txt').as_posix()] = b'one\r\ntwo\nthree\r\n'
        self.assert_checkout_preserves(sources)

    def test_grammar_sources_checkout_keep_generated_hash_bytes(self):
        sources = {}
        for directory in ('intent_parser', 'intent-parser-js', 'intent-parser-csharp'):
            paths = sorted((ROOT/directory).glob('*.grammar'))
            self.assertEqual(len(paths), 3)
            for path in paths:
                sources[path.relative_to(ROOT).as_posix()] = path.read_bytes()
        self.assert_checkout_preserves(sources)


if __name__ == '__main__':
    unittest.main()
