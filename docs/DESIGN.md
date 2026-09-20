# State-update benchmark: execution design

## Purpose and scope

Phase 1 tests `original JSON state + new natural-language information -> proposed update`. Phase 2 will test whether the SAME loaded model can also narrate a game turn before updating state. This first implementation is a small Phase 1 harness, not a claim that a model is a reliable game master.

The runner and inference server execute on the machine with the GPU. A laptop is for development, remote control and analysis. Tailscale carries remote-control traffic; official local performance runs call a loopback inference endpoint. On Unity, both processes belong inside the SAME Slurm GPU allocation, never on a login node. A GPU model name is an expectation to verify, not permission to allocate that GPU.

## What context means

A token is a piece of text. `context_tokens` is the configured token capacity available for the prompt and generated continuation. The state, conversation, instructions, chat-template overhead and output all consume that capacity. It is NOT the number of GPU cores, the model parameter count, or persistent game memory. Begin with 4,096 tokens for these two tiny fixtures. Increasing context can increase runtime memory requirements. Do not silently truncate an oversized input; record an error and use a separately identified larger-context experiment.

## Separate configuration files

* `models.json`: ONLY a JSON array of model variants. Each record names the original model, GGUF publisher/repository, exact filenames, quantization and `required_vram_gb`. No seeds, test suites or pipeline definitions here.
* `experiment.json`: context capacity, output limit, sampling settings, seeds, repetitions and selected pipeline names.
* `worker.example.json`: backend selection, local model paths/LM Studio keys, backend version and result location. A filled-in `worker.local.json` is ignored by Git.
* `fixtures/*.json`: input state, new information, expected final state and optional example patches. Ground truth NEVER goes into a model request.

`required_vram_gb` is a configured TOTAL device-capacity budget for a particular variant under the baseline text-only, single-request, 4K-context setup. Despite the familiar field name, use GiB (1,024^3 bytes), matching NVIDIA's MiB reporting. This is not GGUF download size and not a measured constant of the model. Initial budgets must be marked `estimated_unverified`; successful loading alone does not prove complete GPU residency. Actual free memory, backend, KV-cache settings and runtime buffers still matter. A higher-context run requires its own validated budget. Never silently switch to CPU offload or a smaller quantization to make an experiment finish.

## Initial comparisons

Implement the same two fixtures under a 2-by-2 comparison:

1. Direct generation of standard RFC 6902 JSON Patch.
2. Direct generation of semantic operations (`set`, `list_add`, `list_remove`).
3. Concise natural-language change analysis, THEN a separate JSON Patch call.
4. The same analysis step, THEN semantic operations.

Use the same source information and equivalent update instructions. Score the resulting state, not whether patch text exactly matches an example. An array append and an equivalent array replacement can be semantically correct. Report representation/format compliance separately. A malformed answer is a completed model failure, NOT a reason to keep retrying until a good answer hides the failure.

The one-shot full-state baseline, constrained field-by-field questions, verification/repair and controlled prefix-caching experiments are planned extensions. Do not label any of these implemented until code and tests exist. For decomposition, ask `Did X change?` before asking for a new value. False negatives at this gate are missed updates, even if later formatting is perfect.

## Two deliberately simple fixtures

### time_only

Initial time is `14:15`; location is `Kitchen`; Tom wears `["blue shirt", "jeans"]`; Susie wears `["red dress"]`. New information says exactly five minutes pass and nothing else changes. Expected: time becomes `14:20`; every other field is preserved.

### clothing_append

Use the same original state. New information says Tom puts a green jacket OVER his existing shirt, mentions wanting to go outside, but stays in the kitchen; no tracked time passes. Expected: append `green jacket` to Tom's clothing array; keep the shirt, jeans, location, time and every Susie field unchanged.

These are plumbing/smoke fixtures, not a sufficiently large research benchmark. They deliberately exercise a scalar, an array, nested addressing, preservation and a misleading mention. Expand only after the scorer passes tests for wrong and malformed responses as well as correct ones.

## Worker lifecycle

1. Acquire a local worker lock. Do not run two schedulers against the same GPU/server. A stale lock requires explicit operator inspection; never delete another live worker's lock automatically.
2. Before importing benchmark code, require a clean source checkout and `git pull --ff-only`. Stop on conflicts; never reset, stash or force-push. Launch the actual runner as a NEW Python process so the pulled code, rather than already-imported old code, runs.
3. Record source commit and a digest of executable code/prompts/configuration. A result-only Git commit must not invalidate previous cases.
4. Detect NVIDIA GPU name, UUID, VRAM and driver. Respect Slurm/CUDA device selection. Detect CPU, OS and available system information. Verify any expected GPU name. Never infer speed from VRAM capacity alone.
5. Validate JSON configuration and fixture ground truths. Build jobs from selected model variants, pipelines, fixture versions, sampling settings, seeds and repetitions.
6. Verify local model artifacts and record their SHA-256 hashes. Downloading large weights is an explicit preparation operation, not an unattended side effect of starting a benchmark. Keep GGUF files outside Git. All shards are required for split GGUFs.
7. Create a reproducible case identity from model artifact hashes, effective settings, pipeline/code/fixture digests and the hardware/software measurement environment. Keep timestamp and worker hostname OUT of that identity. Store them as provenance instead.
8. Find validated completed records for that identity. Correct, incorrect and invalid model answers all count as completed. Infrastructure errors have separate attempt records and a bounded retry policy. Corrupt/incomplete result files must not silently count as completed.
9. Group pending cases by model AND load configuration. Load once, verify the requested model is served, record load time, and run an untimed warm-up. Do not unload unrelated user models without explicit consent. If memory or runtime support is insufficient, record why; do not fabricate a result or downgrade the model.
10. Run cases serially for latency measurements. Time each inference call and the entire pipeline. Retain exact prompts, raw responses, parsing errors and finish reasons. Truncated output is a failure, not a complete patch.
11. Validate candidate updates, apply to a COPY of state, validate the final state and compare with ground truth. No model output may execute Python, shell commands or SQL. Never update the real game save while benchmarking.
12. Save each case atomically as an immutable JSON record. Keep failed attempts separately. A crash loses at most the current request, not the model's whole batch.
13. At safe boundaries, periodically commit/push result files. Perform Git/network work outside timed sections. If publishing fails, retain all local records and report the failure. Resume later without regenerating completed cases.
14. Unload only the model owned by this worker and continue to the next eligible variant. Generate summary JSON/CSV from immutable results rather than having multiple machines edit one global CSV.

## GitHub transport and provenance

Use `main` for code, fixtures and catalog updates. Give each experiment worker a results branch such as `results/desktop-1080` or `results/unity-a100`, preferably checked out into a separate ignored Git worktree. This avoids pulling code changes into a process in mid-experiment and avoids simultaneous workers pushing conflicting updates to main. Pull/fetch before a job; pin code for the duration of that job. Fetch/merge result branches on the analysis computer when desired.

A branch is not a distributed lock. Two simultaneous jobs must not share a worker ID/results branch. Per-worker resume comes first; global cross-worker deduplication needs a real claim mechanism and is not implied by Git. Immutable result paths include case identity AND attempt/repetition identity so deliberate repeats do not overwrite one another.

This repository is public. Only synthetic safe-for-work fixtures and their outputs belong here. Do not publish real patient/student records, private game saves, credentials, access tokens, or explicit assets. Push only the generated result directory, never `git add .` on an arbitrary working tree. Model downloads and local environment files are ignored. Private/mature experiments need a separately reviewed storage/publication policy.

## Measurements and scoring

Primary: exact final-state match, correct required changes, missed changes, wrong values, unsupported changes, invalid format/schema rate. Unchanged fields must not inflate accuracy. For the initial scorer, arrays count as a field for change metrics; exact final-state comparison still checks contents and order. Preserve JSON types: `true` is not interchangeable with `1`. Preserve duplicate-list semantics explicitly rather than deleting an arbitrary match.

Performance: total pipeline seconds; per-call wall seconds; output/input token counts if supplied by the backend; model load time separately. Report unavailable TTFT, prompt processing, GPU peak or cache-hit measurements as null/unsupported, NEVER as zero or an inferred number. Non-streaming request duration divided by output tokens is not pure decode speed.

Before controlled caching experiments, distinguish warm weights from a warm prompt cache. Reusing a conversation does not prove KV reuse. Independent branches can reuse only an exactly matching prefix supported by the backend. Cache hits, cache policy and any reset operation must be observed or explicitly recorded as unknown. Cache memory is part of the memory budget.

## Unity deployment

Synchronize code and download models before consuming a scheduled GPU slot where practical. Submit a Slurm job with the cluster-approved partition, GPU constraint, RAM and wall time. Inside the allocation, start a supported llama.cpp server bound to 127.0.0.1, then the runner. Preserve CUDA_VISIBLE_DEVICES. Save into persistent group storage, not ephemeral node-local storage. On impending termination, finish/save what is possible, stop issuing requests and resume from recorded cases next allocation. Node/GPU availability and software-module versions must be checked against Unity docs rather than guessed.

## Testing and rollout

Unit tests cover configuration validation, strict state comparison, both patch representations, atomic application, prompt/ground-truth separation, result identities, resume, corruption, hardware selection and backend command construction. An offline mock backend exercises scheduling and failures without claiming model quality. An HTTP smoke test exercises the actual client against a localhost stub. Git tests use temporary local bare repositories, not the user's real remote.

First run the unit suite, then an offline smoke run, then repeat that smoke run and verify zero new inference calls. Next run ONE small downloaded model through both fixtures on the desktop. Only after load settings, output parsing and hardware logs are inspected should the worker advance through the larger catalog. A GPU run cannot be certified by passing mocked tests.

## Primary references

Verified 2026-09-20:
- LM Studio model load/unload CLI: https://lmstudio.ai/docs/cli/local-models/load
- LM Studio model listing: https://lmstudio.ai/docs/cli/local-models/ls
- LM Studio REST load metadata: https://lmstudio.ai/docs/developer/rest/load
- Qwen3.8-27B official model: https://huggingface.co/Qwen/Qwen3.8-27B
- Qwen3.8 GGUF variants: https://huggingface.co/bartowski/Qwen3.8-27B-GGUF
- Qwen3.5-122B-A10B official model: https://huggingface.co/Qwen/Qwen3.5-122B-A10B
- 122B split GGUF files: https://huggingface.co/lmstudio-community/Qwen3.5-122B-A10B-GGUF/tree/main

Model availability is verified from those publishers; VRAM budgets are engineering estimates pending measurements. No model is an error-free ground-truth judge merely because it is the largest reference.
