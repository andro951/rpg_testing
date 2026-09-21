"""Generate a transparent, reviewable Slurm job for Unity's Job Composer UI."""
from __future__ import annotations
# Names must be checked against the user's allowed partitions/allocation at submission.
PROFILES={'8':'2080','11':'2080ti','12':'titanx','16':'a4000','24':'l4','32':'v100&vram32','40':'a100&vram40','48':'l40s','80':'a100-80g'}

def make_script(tier='16'):
    if tier not in PROFILES:raise ValueError('Unknown GPU tier')
    gpu=PROFILES[tier]
    constraint=f'#SBATCH --constraint={gpu}\n' if gpu else '# No verified 12 GB target is assumed; select an eligible node in Job Composer.\n'
    ram=max(32,int(tier)*2)
    return f'''#!/bin/bash
#SBATCH --job-name=rpg-testing
#SBATCH --partition=gpu
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem={ram}G
#SBATCH --time=02:00:00
#SBATCH --signal=B:USR1@60
{constraint}set -euo pipefail
# Submit from the prepared repository using Unity OnDemand Job Composer.
# Confirm partition/constraint access first. Never run this on a login node.
: "${{SLURM_JOB_ID:?Submit through Slurm}}"
cd "${{SLURM_SUBMIT_DIR:?}}"
# Set these paths once in the worker UI before submission; they are saved locally.
# Install the compatible native llama-server and Python environment before allocation.
PYTHON="${{RPG_PYTHON:-.venv-workbench/bin/python}}"
"$PYTHON" launch_workbench.py --batch &
worker_pid=$!
trap 'kill -USR1 "$worker_pid" 2>/dev/null || true' USR1
trap 'kill -TERM "$worker_pid" 2>/dev/null || true' TERM INT
set +e
while kill -0 "$worker_pid" 2>/dev/null; do
    wait "$worker_pid"
    rc=$?
    if ! kill -0 "$worker_pid" 2>/dev/null; then exit "$rc"; fi
done
wait "$worker_pid"
exit $?
'''
