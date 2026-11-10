#!/bin/bash -l
#SBATCH --job-name=rpg-pathlist-9b-q4_k_m
#SBATCH --account=pi_hendawi_uri_edu
#SBATCH --partition=gpu
#SBATCH --qos=normal
#SBATCH --constraint=titanx&haswell
#SBATCH --gres=gpu:titan_x:1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=3
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --signal=B:USR1@60
#SBATCH --output=benchmark-%j.log
set -euo pipefail
cd /work/pi_hendawi_uri_edu/isaac_richards_uri_edu/research-path-list-v1-20261103/9b-q4_k_m
mkdir -p cache/xdg cache/cuda cache/hf cache/pip cache/tmp
export XDG_CACHE_HOME="$PWD/cache/xdg"
export CUDA_CACHE_PATH="$PWD/cache/cuda"
export HF_HOME="$PWD/cache/hf"
export HUGGINGFACE_HUB_CACHE="$PWD/cache/hf/hub"
export PIP_CACHE_DIR="$PWD/cache/pip"
export TMPDIR="$PWD/cache/tmp"
export LMOD_USER_CACHE_DIRECTORY="$PWD/cache/xdg/lmod"
module load cuda/12.8
export LD_LIBRARY_PATH="$CUDA_HOME/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONDONTWRITEBYTECODE=1
cd repo
../venv/bin/python -B -m unittest tests.test_required_scope tests.test_path_list -v > ../focused-tests.log 2>&1
cd ..
venv/bin/python -I -B -u unity_run.py &
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
