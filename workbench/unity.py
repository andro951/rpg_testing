"""Generate a transparent, reviewable Slurm job for Unity's Job Composer UI."""
from __future__ import annotations
# Names must be checked against the user's allowed partitions/allocation at submission.
PROFILES={'8':'2080','11':'2080ti','12':None,'16':'a4000','24':'l4','32':'v100-32g','40':'a100-40g','48':'l40s','80':'a100-80g'}

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
{constraint}set -euo pipefail
# Submit from the prepared repository using Unity OnDemand Job Composer.
# Confirm partition/constraint access first. Never run this on a login node.
: "${{SLURM_JOB_ID:?Submit through Slurm}}"
cd "${{SLURM_SUBMIT_DIR:?}}"
# Set these paths once in the worker UI before submission; they are saved locally.
# Install the compatible native llama-server and Python environment before allocation.
PYTHON="${{RPG_PYTHON:-.venv/bin/python}}"
"$PYTHON" launch_workbench.py --batch
'''
