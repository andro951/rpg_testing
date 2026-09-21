# Current architecture

This document supersedes the initial CLI-only design. The detailed behavioral specification is [WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md), with requirement coverage in [PLANNED_CHANGES.md](PLANNED_CHANGES.md) and executed validation in [TEST_REPORT.md](TEST_REPORT.md).

## Execution boundary

The GPU host owns the browser-control service, model backend and test runner. The laptop sends authenticated control requests over Tailscale, not timed inference requests. Unity runs the same controller inside a supported Slurm allocation. Models and runtime files are never stored in Git.

## Components

- `launch_workbench.py`, `bootstrap.pyw`, graphical launchers: setup consent, process supervision, host locking and browser opening.
- `workbench/server.py`, `web/`: authenticated API and UI, manual fixes, models/test editor, status, results/log export, host-side browsing and private remote binding.
- `controller.py`, `preflight.py`, `planning.py`: explicit lifecycle, pending-first preparation, shared scheduling, model grouping, manual repair and pause/cancel.
- `inventory.py`, `downloads.py`: active-folder discovery, GGUF metadata/shards/fingerprints, automatic context planning, explicit verified downloads.
- `domain.py`, `workflows.py`, `scoring.py`: self-contained test validation, deterministic identities, steps/branches/loops, typed outputs, patch interpretation and final-state scoring.
- `backends.py`: local streaming model clients, same-model sequential calls, native cache controls and readiness probes.
- `gitops.py`, `analysis.py`: conservative source/results transport and descriptive summaries.

## Data contracts

`models.json` contains only model variants and assigned VRAM tiers. `test_specs/*.json` contains complete experiments including inputs, workflow variants, settings and oracles. Local operational settings are created by the UI. There is no manually maintained completion database.

Each case result has status first and a checksum. Identity incorporates model artifacts, test/variant/repetition, relevant implementation and hardware/software target. Completed incorrect answers remain completed. Deleting a result schedules it again. Errors/aborts remain pending. Artifact metadata is separate provenance, not completion state.

## Measurement contract

The workflow timer covers all its requests and declared orchestration. Application disk writes, scoring and Git transfers are outside that interval. Raw prompts, responses, finish reasons, settings and available backend counters are retained. Cache evidence is required for controlled cache comparisons. Unknown metrics stay unknown.

No user output/context cap is exposed. Internal finite context is allocated automatically and recorded. Native tokenizer guards reject oversized requests without silently trimming them. No promise of infinite output or automatic full GPU residency is made.

## Scope

The two default fixtures are time-only updating and clothing-array append with unchanged location. Examples add cache-on/off questions, bounded repair and narration→update. These demonstrate mechanics and must be expanded before drawing research conclusions. Real-GPU validation remains necessary; passing UI/mock tests is not proof of inference performance.
