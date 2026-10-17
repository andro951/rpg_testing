"""Archived research definitions remain immutable regression fixtures, not active tests."""
from pathlib import Path
from workbench.domain import read_json

REPO = Path(__file__).resolve().parents[1]
LEGACY_ROOT = REPO / 'archives/test-suite-2026-10-14'


def fixture_path(folder):
    return (LEGACY_ROOT if folder in ('test_specs', 'examples', 'examples/test_specs') else REPO) / folder


def legacy_sharing():
    return read_json(LEGACY_ROOT / 'optimization/sharing.json')
