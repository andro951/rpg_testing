# Validation report — native workbench

Date: 2026-09-21. Functional-code checkpoint: **`c2a7436f042300c3d739f1aa87e210051c7afd6e`**. Documentation updates after that checkpoint do not change the tested application code.

## GitHub Actions: completed successfully

Run **35603778392** completed with overall **success**:

- Linux unit/integration suite: **258 tests passed**, job **106345858827**.
- Windows unit/integration suite: **258 tests passed**, job **106345858853**. The job used Windows Server 2025 and CPython 3.12.10, not the user's Windows 10 desktop.
- Chromium browser job **106345858835**: both `tests/browser_smoke.py` and `tests/browser_model_smoke.py` passed through actual browser-to-localhost HTTP.

Run details: https://github.com/andro951/rpg_testing/actions/runs/35603778392

The Windows log explicitly reports `Ran 258 tests in 44.334s` and `OK`. Tests include the retained historical CLI checks as well as the active native workbench. Passing them does not imply that the legacy CLI is the recommended interface.

## Also executed locally

The final local `python -m unittest discover -s tests` invocation passed **258 tests**. JavaScript syntax validation passed. Both Chromium workflows passed locally with the network-restricted browser's HTTP bridge enabled; those local bridge runs do not count as direct browser-network validation. The GitHub Actions browser job supplies that separate validation.

Screenshots were inspected for the main workbench, model browser and responsive layout. The displayed models/results in those screenshots are explicitly simulated or fixture-backed, not real model-performance data.

## What the tests cover

**Unattended execution:** all primary models precede deferred recovery; deferred models are sorted smallest first; CPU-placement and GPU-memory failures unload/skip without prompts; unrelated runtime errors do not become endless retries; hybrid trials are bounded; hybrid records remain separate; full-GPU recovery keeps its original failed-attempt evidence; deletion resumes only the needed work; incorrect model answers are not rerolled; user cancellation prevents entry into recovery.

**Context and caching:** generous source/shared-prefix estimates, actual native token-guard contracts, context expansion with prior attempt preservation, native finite capacity, cache-off erasure, cache-on reuse counters, and invalid/missing cache evidence not reported as a valid speed comparison. These tests use deterministic backend fixtures; no actual model cache was measured.

**Native process lifecycle:** a real child-process HTTP/SSE stub exercises readiness, model identity, generation, partial CPU-placement rejection, watchdog cancellation, and unloading/termination. The child is a Python test fixture, not a llama.cpp binary or a language model.

**Model management and storage:** unset initial models directory, explicit folder approval, legacy-setting migration requiring new consent, empty-folder confirmation, existing GGUFs not copied, normalized Windows paths, repository/revision disambiguation, resumable download ranges, checksums, shard grouping, stale selections, simulated-mode download refusal and selected-directory-only model writes.

**Runtime installation:** official asset metadata filtering, manual selection, digest checks, archive path traversal and link rules, extraction budget, local installation manifest and tamper checks. The test runtime archive contains harmless fixture bytes; no downloaded executable is launched by these tests.

**UI/control plane:** authenticated pairing, Host/Origin checks, private-interface binding, host folder browser, first-run and empty-folder dialogs, Hub search/quantization selection, retained checkbox/dropdown state, manual download approval, runtime selection/installation wiring, preflight, run, resume, deletion/rerun, test example import/editor, evidence inspection/export, comparison and responsive layout.

**Results and logging:** strict JSON/schema/patch validation, final-state scoring, ground truth excluded from requests, atomic/checksummed result files, previous attempt history, corruption handling, distinct artifact/test/protocol grouping, in-memory logging during timed workflows, NVML mock sampling, unavailable counters and sample scope.

**Source updates and Unity scaffolding:** explicit Run intent consumed once after update, bounded restart chains, stale-intent rejection, user-stop cancellation, host locks, safe Git operations, generated Slurm shell syntax and allocation guards. Scheduler signaling is represented in the scripts and launcher; no Unity job was submitted.

## Failures found and fixed in this pass

Earlier checkpoints did not pass every check. Fixes included the old browser test's assumption that importing a larger cache test could never change other case identities, Windows 8.3/long-path comparisons, normalized empty-folder confirmation, unsafe original ZIP names obscured by Windows normalization, and a test accidentally using an unconfigured WSL Bash shim instead of a working shell.

The final green run includes the fixes. The Windows logs still contain a closed-socket `ResourceWarning` and action-runtime deprecation warnings; this report does not claim warning-free execution or formal proof that every resource edge case is eliminated.

## Not validated here

- Actual inference on the user's GTX 1080, Windows 10 driver or chosen official llama.cpp build.
- Live large-model downloads, gated/private access and publisher licensing decisions.
- Actual NVML samples, full native-model latency, semantic quality or cache-hit measurements.
- Independent physical GPU residency or Windows paging behavior. The implemented gate uses backend-reported layer/KV placement; NVML reports sampled total-device usage, not exact per-model allocation.
- The user's real laptop-to-desktop Tailscale/firewall connection.
- Actual Unity storage, permissions, partitions, GPU allocation or scheduler signal delivery.

These are environment-validation limits, not evidence that the integrated UI and two-pass scheduler are still unwired. The application is ready for a real hardware smoke run; software tests do not guarantee the selected model/runtime/driver combination will work.
