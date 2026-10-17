"""Offline CLI smoke: synthetic evidence replay and repeat/resume; no model calls."""
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.test_evaluation import ReplayTests
from workbench.domain import ResultStore, read_json


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        record = ReplayTests().record()
        path = ResultStore(root/'results').save(record)
        before = path.read_bytes()
        command = [sys.executable, '-m', 'evaluation', '--source', str(root/'results'), '--output', str(root/'assessments')]
        for _ in range(2):
            subprocess.run(command, check=True, timeout=30)
        summary = read_json(root/'assessments/summary.json')
        assert summary['outcomes'] == {'PASS': 1}
        assert not summary['problems']
        assert path.read_bytes() == before
    print('Evaluation CLI smoke passed twice; immutable synthetic evidence preserved.')


if __name__ == '__main__': main()
