# Current native-workbench architecture

The GPU host owns the controller, native inference process and scheduler. A browser on that host or a paired laptop sends only control requests. The active application has no LM Studio backend.

## Components

- `bootstrap.pyw`, `launch_workbench.py`, graphical launchers: dependency consent, isolated environment, host locking, process supervision and optional browser opening.
- `restarts.py`: short-lived, bounded resume intent for an already-requested Run after source updates; not a completion tracker.
- `server.py`, `web/`: authenticated control API, setup, first-folder consent, Hub/runtime browser, models, test editor, progress, comparison and evidence export.
- `hub.py`, `model_manager.py`, `downloads.py`: pinned remote metadata, quant grouping/recommendations, explicit downloads, resume and verification in the chosen model directory.
- `runtimes.py`: explicit official release selection, safe extraction and installation manifests under the repository.
- `controller.py`, `preflight.py`, `planning.py`: pending-first readiness, operational settings, tier policy and shared execution plan.
- `scheduler.py`, `execution_policy.py`: full-GPU first, memory-failure deferral, smallest-first recovery, bounded hybrid/context trials and recorded skip outcomes.
- `native.py`, `backends.py`: owned native process, API key, loopback transport, explicit GPU placement controls, streaming, cache reset/evidence and watchdogs. Demo is a distinct test double.
- `inventory.py`: explicit-root GGUF metadata/shards, fingerprinting, hardware detection and automatic context recipe.
- `telemetry.py`: bounded in-memory NVML device sampling; unavailable counters remain unavailable.
- `domain.py`, `workflows.py`, `scoring.py`: test contracts, IDs, result persistence, source-only prompt construction, branches/loops, strict patch application and final-state scoring.
- `gitops.py`, `analysis.py`, `unity.py`: narrow Git transport, version/class-separated descriptive summaries and reviewable Slurm job generation.

## Data and ownership

`models.json` contains model metadata and assigned VRAM tiers. `test_specs/*.json` contains experiment inputs, variants, per-step settings, conditions and scoring oracles. Model bytes reside only in the explicitly selected folder; other application data remains within the repository. The artifact registry caches provenance, not completion.

One terminal result file represents a case identity. Primary and hybrid classes use separate identities. Status and checksum distinguish finished answers, terminal execution skips and interrupted attempts. A wrong answer is finished; a retry is never selected because the answer was poor. Deletion deliberately reopens work.

The planner can identify finished cases without reading deleted model weights. A memory skip with unfinished recovery remains pending recovery work. Actual hardware/software, selected variant, source/oracle, artifact hashes, workflow code and context policy prevent invalid cross-version reuse.

## Measurement boundary

Workflow timing covers its model requests and declared orchestration. Scoring, result writes, logs and Git occur afterward. Telemetry uses NVML calls without per-sample subprocesses or disk writes. Backend cache counters and placement logs are retained as evidence, not treated as infallible physical-residency proof. Unknown metrics stay unknown.

Context is finite and allocated automatically with generous headroom. Exhaustion triggers bounded, recorded retry and may require another model load. Fitting is disabled; a backend cannot silently replace a full-GPU benchmark with hybrid execution. Recovery preserves its actual context, placement and class.

## Unattended contract

After Run passes setup preflight, execution never requests interactive remediation. Full-GPU failures are recorded and unloaded. Memory-related skips are revisited only after primary work, with bounded hybrid alternatives. Cancellation and scheduler signals stop owned work. File/disk failures can still stop the application because results cannot be trusted without durable storage; the program does not pretend such a failure is a model-quality score.

See WORKBENCH_GUIDE.md for user operation and TEST_REPORT.md for the validation boundary. Existing research fixtures and roadmap documents are preserved; the default three fixtures are a starting dataset, not a validated comprehensive RPG benchmark.
