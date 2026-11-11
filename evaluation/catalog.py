"""Explicit per-definition registrations and variant coverage, outside inference identity."""
import hashlib
from pathlib import Path
from workbench.domain import read_json


def definition_source_sha256(path):
    """Hash definition text as Git stores it: normalize CRLF to LF only.

    Do not parse/reserialize JSON or alter prompt strings, whitespace, BOMs or
    lone carriage returns. Historical registrations retain their saved hashes.
    """
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def catalog():
    return read_json(Path(__file__).with_name('catalog.json'))


def registration(test_id, variant_id):
    for definition in catalog()['definitions']:
        if definition['id'] == test_id:
            if variant_id not in definition['variants']:
                raise ValueError('Unregistered evaluator variant: ' + variant_id)
            return definition
    raise ValueError('Unregistered evaluator definition: ' + test_id)
