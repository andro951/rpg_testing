# Planned changes — implementation ledger

The planning-only hold was lifted by Isaac's explicit implementation request. The browser-workbench overhaul has been implemented and tested as software. This file now tracks requirement coverage and outstanding environment validation. Earlier planning wording remains in Git history.

## Implemented

- **GUI-first operation:** Windows double-click launchers, browser control panel, separate simulated demo, no normal terminal commands or manual worker JSON.
- **Model discovery:** read recognized LM Studio current-folder settings, detect GGUFs/shards/metadata, inventory model keys, local paths, hardware and backend versions; UI fallback/empty-folder confirmation.
- **VRAM assignments:** models-only JSON catalog, dropdown and one-click conservative recommendation, unknown models shown as unassigned. Requirements remain estimates, not measured constants.
- **Adjacent-tier policy:** 8→12, 12→16, 16→24, 24→32, 32→40, 40→48, 48→80; 80 only at 80. An 11 GB GPU may run assigned 8 GB variants but not 12 GB variants. GPU identity remains distinct.
- **Self-contained test files:** generic step interpreter, per-step settings, source and ground truth separated, conditions, typed outputs, explicit bounded loops, declared scoring and repetitions. The new UI does not use experiment.json.
- **Cached workflows:** larger shared prefix and cache-on/off examples, conditional yes/no then value, native llama.cpp cache reset/reuse evidence; unsupported LM Studio cache control is blocked.
- **Verification/repair and narrative examples:** imported from the UI; same loaded model serves steps, separate temperatures, intermediates retained.
- **Pending-first preflight:** shared planner with real runs, completed cases need no installed model files, unit/smoke checks, artifact/software/path/hardware readiness, readable execution plan. No benchmark answers during preflight.
- **Manual fixes:** action-specific buttons, one explicit approval per repair, recheck afterward. Known downloads/server start/config save/corrupt-result deletion supported. No silent repair chain, driver change or destructive Git reset.
- **Automatic context:** no UI/test context or output-cap field; internal allocation and finite native limit recorded, native tokenizer guard, no arbitrary 512-token cap.
- **Results:** shallow per-model files, status first, atomic/checksummed writes, no completion tracker, wrong answers completed, errors/aborts pending, delete/rerun, corrupt evidence inspection/export.
- **Readiness probe:** after each model load and before measured cases; exact READY compliance recorded separately from liveness.
- **Logging:** in-memory diagnostics during measured workflows, writes/Git outside those intervals, separate logs directory, ZIP download with raw results and CSV/JSON summaries.
- **Remote controls:** authenticated private Tailscale browser UI with host-side browsing, normal controls, explicit enable/disable, pairing key. No public bind or inference across the laptop network path.
- **Pause/stop/resume:** pause after case, stop after model, cancel now, restart-safe authoritative result files, no extra GUI-only benchmark logic.
- **Git transport:** optional conservative source sync and result publication, narrow staging, no multi-worker distributed scheduler complexity.
- **Unity:** preparation profile check, generated Slurm script for supported OnDemand workflow, same batch controller within allocation, no login-node GPU run.

## Validation completed

Full committed-source CI passed 179 tests on Windows and 179 on Linux, plus a real Chromium browser workflow. See [TEST_REPORT.md](TEST_REPORT.md) for the exact commit/run and [WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md) for behavior.

## Still requires actual environment validation

1. Real GTX 1080 / installed Windows LM Studio smoke, actual model/runtime compatibility and active-directory settings recognition.
2. Real Tailscale route/firewall and initial graphical launcher behavior on the user's Windows 10 session.
3. Actual Unity permissions, storage, executable paths, scheduler constraints and allocated-GPU run.
4. Native cache evidence on the selected llama-server build.
5. Real latency/quality results. Demo output is not evidence of model performance.

## Explicit limitations / follow-on work

Peak-VRAM sampling and independent proof of full GPU residency are not implemented; output fields are unavailable/unverified. VRAM assignments/recommendations must not be described as measurements. Automatic context estimation is conservative, finite and not a promise that every generated continuation will fit. Backend-internal logging/defaults cannot all be controlled by the harness.

A preparation check on one machine cannot certify another machine's installation or future allocation. Dependencies, Git/account credentials, university access and a compatible native engine remain prerequisites; the UI does not silently install drivers or obtain authorization. Controlled cache tests are native-only. External LLM-as-judge orchestration is not part of this implementation. The two default fixtures and three examples are smoke tests, not a final scientific dataset.

The legacy CLI prototype remains only for historical compatibility; its older limits/settings are not used by the new browser workbench. Do not confuse those files with the new test_specs-based runner.
