"""Archived research definitions remain immutable regression fixtures, not active tests."""
import copy
from functools import lru_cache
from pathlib import Path
import shutil
import tempfile
from workbench.domain import code_fingerprint

REPO = Path(__file__).resolve().parents[1]
LEGACY_ROOT = REPO / 'archives/test-suite-2026-10-14'


def fixture_path(folder):
    return (LEGACY_ROOT if folder in ('test_specs', 'examples', 'examples/test_specs') else REPO) / folder


@lru_cache(maxsize=1)
def _legacy_sharing_for_runtime(workflow_fingerprint):
    """Re-review test-only message spans with today's implementation, not old identity."""
    from tools.build_prompt_sharing import build
    with tempfile.TemporaryDirectory(prefix='legacy-sharing-fixtures-') as directory:
        root = Path(directory)
        for folder in ('test_specs', 'examples/test_specs', 'reporting'):
            shutil.copytree(LEGACY_ROOT / folder, root / folder)
        catalog = build(root)
        if catalog['workflow_fingerprint'] != workflow_fingerprint:
            raise RuntimeError('Workflow changed during regression fixture preparation')
        return catalog


def legacy_sharing():
    # Never rewrite the saved archive or treat its past workflow as today's code.
    return copy.deepcopy(_legacy_sharing_for_runtime(code_fingerprint()))
