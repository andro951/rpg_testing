# RPG state-update testing

A GPU-local benchmark worker for this task:

**Original JSON state + new natural-language information -> state update.**

The first release has two synthetic safe-for-work fixtures, four inference pipelines, two patch interpreters, deterministic scoring, automatic model switching, per-case resume, and optional GitHub result publishing. The full research design is in [docs/DESIGN.md](docs/DESIGN.md). This is a tested prototype, not yet a GPU-validated benchmark release.

## What “context” means

`context_tokens` is the amount of text the model can work with in a request, measured in tokens (pieces of text). It includes the instructions, original state, new information, any earlier analysis supplied to that request, and room for the answer. It is **not** the model's size and does not mean persistent memory of a game.

The first experiment uses **4,096 tokens**, with up to **512 output tokens per call**. These are intentionally small plumbing tests. Larger context settings can need more memory; this release rejects a context other than 4,096 until its VRAM budgets are reviewed. It never silently truncates the source to fit.

## Configuration

- [models.json](models.json) is **only an array of model variants**: model name, publisher, exact GGUF filenames, quantization, `required_vram_gb` and supporting metadata.
- [experiment.json](experiment.json) holds context length, generation settings, pipelines, seeds and repetitions.
- [worker.example.json](worker.example.json) is a desktop configuration template. Copy it to `worker.local.json`, which Git ignores.
- [worker.unity.example.json](worker.unity.example.json) is the corresponding llama.cpp template for an allocated Unity GPU node.
- [fixtures](fixtures) contains the two original states, source events, expected final states, and example patches. Expected answers are NEVER sent to the model.

`required_vram_gb` is a conservative **device-capacity budget for the declared 4K-context configuration**, not GGUF file size or a proven peak-memory measurement. All initial entries are marked `estimated_unverified`. To match NVIDIA reporting, the field uses GiB; publisher download sizes use decimal GB. Eight is the lowest target hardware tier, so small model entries also target an 8 GiB device even if they may run on less.

The included catalog contains Qwen3.5 2B, 4B and 9B variants for smaller cards; Qwen3.8-27B at Q3/Q4/Q6/Q8 for larger cards; Qwen3.5-35B-A3B Q4 as a mixture-of-experts comparison; and Qwen3.5-122B-A10B Q4 as a large-cluster reference. Exact files and source links are in the catalog. **The 122B Q4 model has two shards; both are required.** A large reference model is not the ground-truth judge.

## What the two fixtures do

**`time_only`:** exactly five minutes pass, changing `14:15` to `14:20`. Every other value must remain identical.

**`clothing_append`:** Tom puts a green jacket over his existing blue shirt, while keeping his jeans. He says he wants to go outside but does not move. Only his clothing array gains `green jacket`; time, location, other clothing, and Susie's data stay unchanged.

These test a scalar, a nested list, and preservation of unrelated state. They are smoke fixtures, NOT enough data for a research conclusion.

## Four pipelines

1. `direct_json_patch`: one response containing RFC 6902 JSON Patch.
2. `direct_semantic`: one response containing explicit `set`, `list_add`, or `list_remove` operations.
3. `analyze_json_patch`: natural-language changes first, then a separate JSON Patch response.
4. `analyze_semantic`: natural-language changes first, then semantic operations.

Both formats use JSON Pointer paths. Semantic `set` requires an existing target; `list_add` appends one element; `list_remove` requires exactly one matching element. Standard JSON Patch additionally supports its usual index-based list operations. The scorer applies the patch to a copy, validates the resulting state, and compares it to ground truth. Equivalent valid patches can receive the same correctness score.

Invalid JSON, a wrong answer, and a truncated answer are completed benchmark outcomes. They are not repeatedly sampled until one happens to pass. Transport failures have a separate bounded retry policy.

## 1. Install and test without a GPU

Use Python 3.10 or newer and Git. In the repository directory:

```text
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python run_worker.py --no-sync --mock --output .local/smoke
python run_worker.py --no-sync --mock --output .local/smoke
```

The first mock run should complete **24 cases**: three eligible model catalog entries x two fixtures x four pipelines. The second should report **24 already complete and zero new model loads/calls**. The mock is a deterministic test double, NOT a real model. Its results are explicitly marked simulated and cannot be published using `--mock --publish`.

Preview the scheduler without inference:

```text
python run_worker.py --no-sync --plan --vram-gb 16
```

`--vram-gb` applies only to planning or mock runs. Real runs detect the physical GPU and do not trust a supplied label.

## 2. Set up the desktop once

1. Ensure LM Studio and its llama.cpp runtime support the downloaded model. This adapter needs the current `/api/v1/models` API and the `lms` CLI. An old installation may need an update. Run `lms --help` and `lms ls --json` in the same terminal you will use for Python.
2. Download a catalog GGUF in LM Studio. Start with `Qwen3.5-2B-Q8_0.gguf`, not every model in the catalog. Models are NOT downloaded automatically by the worker.
3. Copy `worker.example.json` to `worker.local.json`. Fill in the exact key from `lms ls --json`, absolute paths to the corresponding GGUF files, and the installed LM Studio AND engine runtime build in `backend_version`.
4. Keep the API bound to localhost. If API authentication is enabled, set `RPG_MODEL_API_KEY` in the process environment, never in a committed file. Unload existing models yourself before starting a dedicated worker run; the worker deliberately refuses to evict unrelated models.
5. Use LM Studio's normal settings for the first smoke attempt and record any manual settings alongside the runtime build. Inspect the raw response before treating it as a controlled study. Reasoning modes, prompt templates, KV-cache placement and other backend defaults are NOT fully normalized by this first version.

The managed LM Studio adapter currently requires a host with **one NVIDIA GPU**. It does not pretend that selecting a GPU in Python controls an already-running multi-GPU LM Studio daemon. The llama.cpp adapter selects the assigned device for its child process.

## 3. Run the first actual model test

Commit/push source changes first. Then, on the desktop:

```text
python run_worker.py --worker worker.local.json --worker-id desktop-1080 --model qwen35-2b-q8_0
```

This pulls source with `git pull --ff-only`, runs the unit suite, detects the GTX 1080, hashes the local model, loads it, runs the two fixtures under all four pipelines, and records eight outcomes. Run the same command again to verify resume. These are real outcomes only when you run the command against your actual server; no such GPU run was available during development of this release.

To process **all locally configured, eligible models**, omit `--model`:

```text
python run_worker.py --worker worker.local.json --worker-id desktop-1080 --publish
```

The worker groups all pending cases by model, loads it once, warms it up, runs its cases, unloads only its own model, then advances. Unconfigured/download-missing or under-budget model entries are reported as skipped. A load failure is recorded separately; it never silently substitutes a different model, quantization or CPU-offload configuration.

A source checkout with uncommitted changes stops before the pull. No automatic reset, stash or force-push occurs. `--no-sync` is an explicit development/offline option. The `.local/worker.lock` prevents simultaneous workers in one checkout; after a hard crash, inspect the running processes before manually removing a stale lock.

## 4. GitHub results and analysis

`--publish` creates a **worker-specific results branch**, e.g. `results/desktop-1080`, using an ignored worktree. It checkpoints after requests at roughly three-minute intervals, and at completion. Publishing never occurs inside a measured inference call. Results are saved locally immediately, not only when Git succeeds.

Code stays pinned throughout the run. Results-only commits do not change case identities. Different workers use different result branches. Git is transport, NOT a distributed job-lock service: do not run concurrent jobs with the same worker ID, and use one worker checkout per GPU job. Automatic resume is per worker results directory; cross-worker claims/global deduplication are not implemented.

On the laptop, fetch a results branch without changing your code branch:

```text
git fetch origin
git worktree add --detach ../rpg-results-desktop origin/results/desktop-1080
python -m rpgbench.analyze ../rpg-results-desktop/results/desktop-1080 --output .local/analysis-desktop
```

The exporter writes `summary.json` and `cases.csv`. It ignores simulated results by default, validates result checksums, removes identical copied records, separates infrastructure failures, and refuses multiple distinct completed records with the same experiment identity. Give intentional repeats different `repetitions` in the experiment.

For the offline smoke output only:

```text
python -m rpgbench.analyze .local/smoke --include-simulated --output .local/smoke-analysis
```

This repository is public. The publication feature is for these synthetic SFW fixtures and benchmark outputs. Do not point it at private saves, real medical/student records, API credentials, or explicit content. Weight files never belong in Git.

## 5. Unity

The harness runs on a Slurm **compute node**, beside its own llama.cpp server. It does not run GPU inference on the login node and does not start a Tailscale tunnel on Unity. Use the university's supported SSH/OnDemand access for control.

Before submitting: clone/pull the repo, create a Python environment, install requirements, install/build a compatible `llama-server`, and download the intended model shards to persistent project storage. Copy `worker.unity.example.json` to `worker.local.json` and fill in real paths, exact backend build, and any expected GPU name.

Example submission from the repository after confirming access to the requested partition/device:

```bash
export RPG_WORKER_ID=unity-a4000
export RPG_PYTHON=/absolute/path/to/venv/bin/python
sbatch --partition=gpu --constraint=a4000 --gpus=1 --mem=32G --time=01:00:00 scripts/unity_job.sh
```

For the 122B reference, request an appropriate 80 GiB allocation and enough host RAM, not that A4000 example. Unity documents `a100-80g` as a device constraint, but availability and authorization are scheduler matters. Do not assume the partition contains every GPU. Set the worker's `llama_server_executable` to a build compatible with the allocated GPU and loaded CUDA modules. This release does not provision those packages for you.

The script requires a Slurm job ID, preserves the allocation, and calls the same worker. A preempted/killed job keeps completed case files; a request interrupted before saving is rerun. Graceful scheduler-signal draining is a planned addition, not claimed here. If compute nodes lack outbound Git access, synchronize before allocation, pass `--no-sync`, and transfer/publish results afterward from an allowed host.

## Measurements and limitations

Implemented: strict final-state match; field-change correctness; missed/unsupported changes; wrong values; invalid output; per-call wall time; whole-pipeline time; load time separately; backend-reported token counts; raw requests/responses; model file hashes; GPU identity/VRAM/driver; OS/CPU/software metadata; bounded transport retry; atomic per-case results; Git checkpoints; JSON/CSV exports.

Not yet verified/measured: actual peak VRAM, proof of full GPU residency, streaming time-to-first-token, isolated prefill/decode speed, controlled cache hits, and normalized model-specific reasoning/template settings. Unavailable metrics are null/explicitly unknown, never invented from total request duration. The first measurements are smoke data, not final latency comparisons.

Planned research additions: narrative generation, conditional field-by-field questions, grammar-constrained decoding, independent verification/repair, controlled prefix-cache on/off comparisons, bigger fixtures and more repetitions. The first four pipelines are unrestricted text generation followed by strict parsing; they do not yet enforce JSON while decoding.

See [docs/TEST_REPORT.md](docs/TEST_REPORT.md) for what was actually executed and [docs/DESIGN.md](docs/DESIGN.md) for the complete plan.

## Primary documentation

- [LM Studio loading/estimation CLI](https://lmstudio.ai/docs/cli/local-models/load)
- [LM Studio local model keys](https://lmstudio.ai/docs/cli/local-models/ls)
- [LM Studio model inventory API](https://lmstudio.ai/docs/developer/rest/list)
- [LM Studio chat-completions API](https://lmstudio.ai/docs/developer/openai-compat/chat-completions)
- [Unity GPU allocation and constraints](https://docs.unity.uri.edu/documentation/tools/gpus/)
- [RFC 6902 JSON Patch](https://www.rfc-editor.org/rfc/rfc6902)

Model publisher URLs and the verification date are recorded per entry in `models.json`.
