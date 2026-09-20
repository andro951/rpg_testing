# Validation report — 2026-09-20

## Executed here

Environment: Linux x86-64, Python 3.13.5, jsonschema 4.26.0. No NVIDIA GPU utility and no LM Studio CLI were present.

`python -m unittest discover -s tests -v`

**50 tests passed** in the final direct invocation. The bootstrap also ran the same suite successfully before each of the two final smoke runs.

Coverage by component:

- Core: strict JSON parsing, duplicate/non-finite rejection, JSON-type-aware comparison, all six JSON Patch operations, semantic list/set operations, pointer escapes, bounds, atomic application, schema validation, expected-state equivalence, missed/wrong/unsupported edits, unchanged fields, configuration validation, exclusion of ground truth from prompts, immutable result checksums and corrupt-file handling.
- Runtime: all four pipelines; grouping by model; per-case resume; wrong answers counted as completed; bounded infrastructure retries; truncated output; preservation of an analysis response when a later request fails; experiment identities; artifact shard matching and hashing; CUDA-visible GPU selection; single-GPU LM Studio guard; preservation of the scheduler-provided CUDA visibility in the child server; load-command construction; mocked LM Studio lifecycle and refusal to unload an unrelated model; actual localhost HTTP client/stub exchange; context/endpoint/settings guards; bootstrap lock behavior.
- Git: temporary local bare repositories test fast-forward sync, dirty-checkout refusal, separate result branches/worktrees, result push/reopen, protection against unrelated staged files, and worker-ID validation. These tests do not touch the user's remote repository.
- Analysis: checksum validation, exclusion of simulated records by default, deduplication of copied records, refusal of distinct completions sharing an identity, separate infrastructure-error accounting, JSON/CSV export, and empty/missing-input handling.
- Unity script: Bash syntax and refusal to run outside a Slurm allocation. No actual Unity job was submitted.

## End-to-end offline smoke

Commands:

```text
python run_worker.py --no-sync --mock --output .local/release-smoke
python run_worker.py --no-sync --mock --output .local/release-smoke
python -m rpgbench.analyze .local/release-smoke --include-simulated --output .local/release-smoke-analysis
```

First run: **24 new completed cases**, three model-load groups, zero infrastructure errors.

Second run: **24 already-complete cases**, zero new cases, zero model loads. A unit assertion separately confirms zero additional mock inference calls during resume.

Exporter: 24 completed cases, zero infrastructure-error attempts, zero unresolved cases; generated `summary.json` and `cases.csv`.

These cases are **SIMULATED**. They validate control flow and scoring plumbing. The mock returns predetermined fixture-compatible answers. Its correctness rate says nothing about Qwen or any real model.

## Not established by these tests

No actual model weights were downloaded or run. This environment could not exercise the GTX 1080, Windows LM Studio runtime, or a Unity GPU allocation. Live model loading, backend-specific reasoning controls, actual VRAM use, complete GPU residency, caching behavior, and real throughput/latency still require the first hardware smoke run.

All `required_vram_gb` entries remain `estimated_unverified`. File names and published download sizes were checked against their model repositories, but an available GGUF file is not proof that a particular installed runtime supports its architecture.

There is no claim of exhaustive test coverage or proof of correctness. New adapters, prompts, schema types, cache controls and repair loops need their own tests before being considered implemented.
