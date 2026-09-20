#!/usr/bin/env bash
# Submit with sbatch --partition=... --constraint=... --gpus=1 --mem=... --time=...
# Provision Python, llama.cpp and model weights BEFORE requesting the GPU.
set -euo pipefail
: "${SLURM_JOB_ID:?This script must run inside a Slurm allocation, not on a login node}"
: "${SLURM_SUBMIT_DIR:?Missing Slurm submit directory}"
: "${RPG_WORKER_ID:?Set a stable, unique RPG_WORKER_ID such as unity-a4000}"
cd "${RPG_REPO_DIR:-$SLURM_SUBMIT_DIR}"
export PYTHONUNBUFFERED=1
"${RPG_PYTHON:-python3}" run_worker.py \
  --worker "${RPG_WORKER_CONFIG:-worker.local.json}" \
  --worker-id "$RPG_WORKER_ID" --publish "$@"
