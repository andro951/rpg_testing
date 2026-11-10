"""Versioned offline validators, independent of model-generation identity."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from importlib import metadata
from pathlib import Path
import platform

from workbench.domain import digest

DOT_SEPARATORS_V2 = 'dot-separators-v2'
DOT_OUTER_ARRAYS_V1 = 'dot-outer-arrays-v1'
VALIDATORS = (DOT_SEPARATORS_V2, DOT_OUTER_ARRAYS_V1)


@dataclass(frozen=True)
class Validator:
    version: str
    adapter: object
    fingerprint: str
    source_hashes: dict
    jsonschema_version: str | None

    def applicable(self, representation):
        return representation == 'dot_patch_v1'

    def identity(self):
        return {'version': self.version, 'fingerprint': self.fingerprint,
                'scope': 'offline_validation_only', 'representations': ['dot_patch_v1'],
                'source_hashes': dict(self.source_hashes),
                'python_version': platform.python_version(),
                'jsonschema_version': self.jsonschema_version}


@lru_cache(maxsize=None)
def get_validator(version):
    if version not in VALIDATORS:
        raise ValueError('Unknown offline validator: ' + str(version))
    from . import dot_separators_v2
    adapter = dot_separators_v2
    if version == DOT_OUTER_ARRAYS_V1:
        from . import dot_outer_arrays_v1
        adapter = dot_outer_arrays_v1
    root = Path(__file__).resolve().parents[1]
    names = ('evaluation/validation.py', 'evaluation/dot_separators_v2.py',
             'evaluation/core.py', 'evaluation/__main__.py',
             'workbench/domain.py', 'workbench/scoring.py', 'workbench/value_paths.py',
             'workbench/workflows.py', 'workbench/dot_paths.py')
    if version == DOT_OUTER_ARRAYS_V1:
        names += ('evaluation/dot_outer_arrays_v1.py', 'normalization/__init__.py', 'normalization/outer_arrays.py')
    hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}
    try:
        schema_version = metadata.version('jsonschema')
    except metadata.PackageNotFoundError:
        schema_version = None
    fingerprint = digest({'validator': version, 'sources': hashes,
                          'python_version': platform.python_version(),
                          'jsonschema_version': schema_version})
    return Validator(version, adapter, fingerprint, hashes, schema_version)
