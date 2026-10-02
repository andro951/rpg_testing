# Confirmed bugs and repair tests

## B01 â€” P1: strict chat-template alternation detection never matches ordinary wording

Evidence: workbench/native.py:44 uses a raw regex with double-backslash s instead of the whitespace escape. A template containing "Conversation roles must alternate user/assistant/..." with supports_system_role=True returned the original system/user/user messages and no adaptation in evidence/probes.json. Legacy workflows commonly supply adjacent user messages.

Impact: strict templates can reject valid harness tasks; the failure is a harness compatibility failure rather than model quality. An affected model can lose its whole group to a terminal runtime skip.

Fix: correct regex escaping and test a system-capable strict-alternation template independently of the no-system-role path. Verify apply-template and completion receive legal roles, and record original/adapted messages. Existing streaming test only enters adaptation through supports_system_role=False and misses this branch.

## B02 â€” P1: seed diagnostics have no total deadline

Evidence: Session.load at scheduler.py:94-106 invokes seed_reproducibility_check after NativeBackend.load returns. native.py:186 confines budget(load_timeout) to load/readiness; seedcheck.run_seed_check makes three open-ended generate calls without budget. Case budget exists only in Session.run_cases. Transport's 60-second socket timeout is an inactivity/per-I/O limit, not a total generation deadline.

Impact: a model streaming indefinitely/slowly through its large context can hold the queue in the diagnostic phase far longer than the advertised safety deadlines. Automatic model-failure handling never reaches later models until generation finishes or another limit trips.

Fix: give the entire diagnostic an explicit bounded infrastructure watchdog and preserve partial diagnostic evidence; cancel/reset or reload the owned backend on expiry before proceeding. Test a continuing SSE stream that never sends finish_reason and verify bounded completion/cleanup/advance. Do not treat a diagnostic timeout as a semantic reroll.

## B03 â€” P1: timeout-only compatibility drops unfinished recovery

Evidence: planning.py:159-168 admits completed AND skipped records and treats every non-timeout record as done. pending_plan's compatibility branch at :213-219 does not apply the recovery_eligible/fallback completion logic from the exact-ID branch at :204-207. Reproduction: save a full_gpu skipped gpu_memory record with recovery_eligible=True and no fallback; same timeout gives pending=1/recovery_only=True; increase timeout 60->61 and pending becomes 0/complete=1.

Impact: a harmless watchdog edit can silently suppress the recovery benchmark. No real answer or completed hybrid record exists, but the UI reports completion.

Fix: reuse historical skip semantics using the historical primary ID and its fallback identity. Keep recovery pending until fallback terminal completion exists. Test timeout increase/decrease, absent/completed/deleted fallback, successful full-GPU history and terminal nonrecoverable skips. Preserve old evidence without forging a completion.

## B04 â€” P2: adapted prompt separators are literal backslash-n text

Evidence: native.py:54-60 joins message bodies with double-escaped newlines. Probe produces Rules\n\nState\n\nPatch with no actual LF. tests/test_workbench_streaming.py:104 also expects literal escapes, so it confirms implementation instead of intended prompt layout.

Impact: models that need role adaptation receive changed formatting and broken visible section boundaries. This introduces an avoidable prompt confound across templates.

Fix: use actual newline separators and update the contract test to assert readable body boundaries. Record adaptation in evidence and version the changed measurement implementation; do not overwrite previous benchmark outputs.

## B05 â€” P2: model-browser smoke reads preflight state before repair completes

Evidence: tests/browser_model_smoke.py:136-138 waits for llama_path in the rendered runtime label, then immediately reads app.report. install_runtime clears report before the fix operation reruns check. Local Edge run reached that gap and failed with NoneType subscripting at :138.

Impact: asynchronous runtime repair can be reported as a failing smoke even though installation is progressing correctly; CI/browser confidence becomes timing-dependent.

Fix: wait for the repair operation to be idle and a new report to exist, with explicit readiness/issue assertions. Test with delayed post-install preflight. This is a confirmed test synchronization defect; it does not prove a runtime-install application failure.

## B06 — P2: source sync inherits a global rebase policy

Evidence: workbench/gitops.py:31 invokes git pull --ff-only without explicitly disabling rebase. This desktop has pull.rebase=true in its user Git configuration. The full suite failed test_dirty_nonconflicting_pull_preserves_local_edit with "cannot pull with rebase: You have unstaged changes"; the conflict test also failed its expected conflict message. A process-scoped pull.rebase=false override makes the dedicated Git I/O tests pass without changing source or user Git settings.

Impact: normal local edits that should survive a nonconflicting fast-forward block Run when optional default-on source sync executes. The application's stated merge-only policy is not independent of host Git configuration.

Fix: explicitly select no-rebase fast-forward behavior for source pulls. Add regression coverage with inherited pull.rebase=true and ensure no global config is modified. Preserve conflicting edits and divergence refusal; do not automatically stash/reset.
