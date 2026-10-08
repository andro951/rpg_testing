# Validation report — native workbench

Date: 2026-09-21. Functional-code checkpoint: **`4f2f4acd9d7fb84f256b3a878387263ad3761be6`**.

## Local update — 2026-10-08: Perchance setup prompt before preflight

Preflight first checks whether Perchance is eligible and pending, then verifies Playwright and local browser launch. Missing or broken prerequisites open a Yes/No install popup. Yes installs and rechecks on the worker; No is recorded and excludes Perchance from one upcoming matching run while leaving its observations pending. The next run asks again if setup is still needed. Declines are never stored as permanent settings or benchmark outcomes. Setup is isolated from provider/inference identity.

Final validation: **461 tests ran in 550.305 seconds: 457 passed, four platform tests skipped.** The 19 focused setup/combined-run tests passed, including cancellation, failed installation, stale choices, changed browser health, one-run decline reuse and terminal resume. `tests/perchance_setup_browser_smoke.py` passed through actual Edge-to-loopback HTTP, exercising the popup before normal preflight, decline, next-run offer, approval, resume, broken browser, reload and cancellation. Its installer and inference are simulated; no fresh package/browser download or live Perchance inference was claimed. The existing Perchance Workbench browser smoke and native model-management browser smoke also passed with fixture-backed external services. A separate real local probe successfully imported Playwright and launched/closed Edge. The new popup browser smoke is included in CI, but CI was not run remotely in this session.

User-requested finished-repository retest: **461 tests ran in 496.353 seconds: 457 passed, four Bash checks skipped under the default PATH.** Installed Git Bash was subsequently found at `D:/Program Files/Git/bin/bash.exe`; adding its directory to the test process PATH allowed all four omitted checks to pass. The separate shell/restart test run passed all 12 tests without skips (eight repeat checks plus those four), so every one of the 461 unit/integration tests has executed successfully. **All 11 browser smoke scripts passed**, covering native setup/run/resume, model/VRAM management, targeted runs, Perchance worker/setup/run, report grouping, evidence, judgements and timing. The targeted browser test's obsolete 60-second expectation was corrected to assert the timeout from its selected definition; its helper import now supports both module and direct script invocation. Runtime code, deadlines and benchmark evidence were unchanged by that test correction. Logs are retained under `.local/all-tests-finished-unit-tests.log`, `.local/finished-shell-and-restart-tests.log` and `.local/finished-*-smoke.log`.

Python compile checks, JavaScript syntax and `git diff --check` passed. The inference fingerprint remains `56502881bc3c89f6b58c8f5e755b32f58cbd675274ed5363293b598aaddf9787`; the Perchance adapter/worker, saved results and test definitions are unchanged. Earlier dated validation checkpoints below retain their original results.

## Local update — 2026-10-08: direct private-network access

At the user's request, the Workbench no longer requires a browser pairing key. The UI opens directly on loopback or the enabled Tailscale address. Pairing controls, the login dialog, the pairing API and new key generation are removed. Tailnet access rules govern remote control; Host/Origin checks, loopback/Tailscale client checks, JSON request requirements and private-interface binding remain enforced. The launcher can use an existing old key only to restart a previously running worker into the new policy.

Validation: **449 unit tests ran in 536.480 seconds: 445 passed, four platform tests skipped.** JavaScript syntax validation and `git diff --check` passed. `tests/browser_smoke.py` passed through real Edge-to-loopback HTTP with a clean URL and no Authorization header, including simulated run/resume, deletion/rerun, export and removed pairing controls. `tests/browser_model_smoke.py` also passed through real Edge-to-loopback HTTP, including first-run model-folder setup and fixture-backed model/runtime management. Simulated tailnet tests cover the permitted address, absence of key requirements, and rejected outside-range clients/interfaces. These checks did not validate the user's physical laptop-to-desktop Tailscale/firewall route.

The inference fingerprint remains `56502881bc3c89f6b58c8f5e755b32f58cbd675274ed5363293b598aaddf9787`. This control-UI change does not change benchmark case identity or rewrite saved inference evidence. The older checkpoint and CI results below describe the earlier pairing-based version.

## GitHub Actions: completed successfully

Run **35612367369**, attempt 2, completed with overall **success**:

- Linux unit/integration suite: **264 tests passed**, job **106345858827**.
- Windows unit/integration suite: **258 tests passed**, job **106345858853**. The job used Windows Server 2025 and CPython 3.12.10, not the user's Windows 10 desktop.
- Chromium browser job **106345858835**: both `tests/browser_smoke.py` and `tests/browser_model_smoke.py` passed through actual browser-to-localhost HTTP.

Run details: https://github.com/andro951/rpg_testing/actions/runs/35612367369

The Windows and Ubuntu jobs both completed the 264-test suite successfully. Tests include the retained historical CLI checks as well as the active native workbench. Passing them does not imply that the legacy CLI is the recommended interface.

## Also executed locally

The final local `python -m unittest discover -s tests` invocation passed **264 tests**. JavaScript syntax validation passed. Both Chromium workflows passed locally with the network-restricted browser's HTTP bridge enabled; those local bridge runs do not count as direct browser-network validation. The GitHub Actions browser job supplies that separate validation.

Screenshots were inspected for the main workbench, model browser and responsive layout. The displayed models/results in those screenshots are explicitly simulated or fixture-backed, not real model-performance data.

## What the tests cover

**Unattended execution:** all primary models precede deferred recovery; deferred models are sorted smallest first; CPU-placement and GPU-memory failures unload/skip without prompts; unrelated runtime errors do not become endless retries; hybrid trials are bounded; hybrid records remain separate; full-GPU recovery keeps its original failed-attempt evidence; deletion resumes only the needed work; incorrect model answers are not rerolled; user cancellation prevents entry into recovery.

**Context and caching:** generous source/shared-prefix estimates, actual native token-guard contracts, context expansion with prior attempt preservation, native finite capacity, cache-off erasure, cache-on reuse counters, and invalid/missing cache evidence not reported as a valid speed comparison. These tests use deterministic backend fixtures; no actual model cache was measured.

**Native process lifecycle:** a real child-process HTTP/SSE stub exercises readiness, model identity, generation, partial CPU-placement rejection, watchdog cancellation, and unloading/termination. The child is a Python test fixture, not a llama.cpp binary or a language model.

**Model management and storage:** unset initial models directory, explicit folder approval, legacy-setting migration requiring new consent, empty-folder confirmation, existing GGUFs not copied, normalized Windows paths, repository/revision disambiguation, resumable download ranges, checksums, shard grouping, stale selections, simulated-mode download refusal and selected-directory-only model writes.

**Runtime installation:** official asset metadata filtering, manual selection, digest checks, archive path traversal and link rules, extraction budget, local installation manifest and tamper checks. The test runtime archive contains harmless fixture bytes; no downloaded executable is launched by these tests.

**UI/control plane:** authenticated pairing, Host/Origin checks, private-interface binding, native host folder/file picker wiring, first-run and empty-folder dialogs, a deliberately slow background model scan that remains navigable, Hub search/quantization selection, retained checkbox/dropdown state, manual download approval, runtime selection/installation wiring, preflight, run, resume, deletion/rerun, test example import/editor, evidence inspection/export, comparison and responsive layout.

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


## Folder-selection regression fixed

User evidence from the first Windows smoke attempt contained only the startup log, which means the failure happened before any benchmark/result activity. The folder chooser was redesigned: the web-built host browser was removed from the UI, local selection now uses the host operating system dialog, saving a model path no longer performs a recursive scan inside the settings lock, and scanning runs as its own background operation. Browser coverage intentionally delays the scan and verifies that **Installed models** is already usable with a `SCANNING` state and no modal “wait” error.
