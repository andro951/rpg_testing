"""Frozen 21-case inputs for fixture-specific regression tests.

These wrappers exercise the current implementation against archived source data;
production discovery never imports this module or restores retired cases.
"""
from functools import partial
from pathlib import Path
from prompt_builder import builder

ROOT = Path(__file__).resolve().parents[2] / 'archives/suite-before-240-2026-11-15/prompt_builder/templates'
build = partial(builder.build, root=ROOT)
compile_test = partial(builder.compile_test, root=ROOT)
def discover(root=ROOT):
    return builder.discover(root)

def load_case(name, root=ROOT):
    return builder.load_case(name, root)

def prompt(case, input_format, output_format, root=ROOT, **kwargs):
    return builder.prompt(case, input_format, output_format, root, **kwargs)

def install(output, repository=None, **kwargs):
    # Use a copied test repository's sources when present, preserving stale-source
    # and tamper checks; otherwise match the frozen inputs used by build().
    if 'root' not in kwargs and (repository is None or not (Path(repository) / 'prompt_builder/templates').exists()):
        kwargs['root'] = ROOT
    return builder.install(output, repository, **kwargs)
