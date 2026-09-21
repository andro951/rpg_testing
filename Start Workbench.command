#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ -x .venv-workbench/bin/python ]; then
    exec .venv-workbench/bin/python bootstrap.pyw
fi
exec python3 bootstrap.pyw
