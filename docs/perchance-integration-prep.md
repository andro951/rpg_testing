> October 8 update: ordinary repetitions now run independently; seed forwarding remains unverified. The original preparation below predates this change. Current requirements: [capability policy](perchance-capability-policy.md).

# Perchance integration preparation and acceptance review

## October 8, 2026: browser setup consent before preflight

User-directed amendment: dependency setup is now the first preflight stage. Determine whether the scope has pending Perchance observations on an eligible 8 GB worker, then check the dependency and launch a temporary headless local browser without visiting Perchance. This replaces the earlier no-browser dependency check. Missing/broken setup opens a server-owned Yes/No popup, including through remote control. Yes installs into the worker Python environment, supplies managed Chromium when needed, verifies launch, and continues. No is recorded in logs and the preflight report, excludes Perchance from one upcoming matching run, and leaves all remote observations pending. Every subsequent run checks again; there is no permanent opt-out. A cancelled prompt is never treated as an answer.

Preparation/implementation review: keep setup in `perchance_setup.py` and controller/UI orchestration, outside adapter and workflow fingerprints. Preserve provider conditions, terminal resume, the fixed 8 GB scheduling assignment and 300-second deadline. Check completed/excluded scopes before any install offer. Failed installation blocks inference with explicit evidence. Recheck healthy preflight dependencies when Run starts, since an executable/package may have changed. Keep interactive remediation before inference, never between benchmark cases. Tests cover declined preflight-to-run reuse, next-run prompts, direct and targeted runs, installation/recheck failures, stale answers, cancellation, changed browser health, and simulated run/resume. Browser smoke uses real local HTTP and a real browser with simulated installation/inference; a separate real local probe verifies Playwright/Edge launch. No live Perchance generation is performed by these checks.

Prepared October 1, 2026, before implementation. Authority: user requested a copy of the EmberAdventures harness adapted as a selectable Perchance Text Generator, fixed to 8 GB workers, with one observation per effective condition when controls are unavailable. See perchance-capability-policy.md and AGENTS.md. Preparation was source-reviewed before implementation; the final acceptance review appears below.

## Source and boundaries

Copy only the text bridge behavior from EmberAdventures/tools/perchance-ai-text-harness: browser/frame discovery, plugin resolution, serialized text jobs and streamed evidence. Implement a separate worker namespace in tools/perchance-text/worker.js. Remove images, story/playtest code, disk queues, response trimming and retry behavior. Attribute the source in the copied component's README. Original EmberAdventures files, profiles, CDP port 9222, saved Perchance pages, existing results and test specs must remain untouched.

The user clarified to modify a copy of the existing harness. Default bootstrap URL is its existing https://perchance.org/056uh2nc6k. Open an owned browser context, locate the existing plugin frame and inject the separate text-only worker in memory. This avoids requiring publication/editor changes. The hosted bootstrap may import an image plugin, but the copied worker contains no image imports, UI or generation calls. Ship optional text-only left/bottom pane guidance for a future dedicated page.

First implementation supports an installed Windows Edge/Chrome browser, or an explicitly configured browser executable on Linux. Unity requires a browser installation, display for headed execution and Internet access; do not claim native Unity setup is automatic. Browser settings are machine-local. No downloads during preflight or a benchmark run. Python Playwright is an optional provider dependency installed through an explicit setup action or documented command. Startup failures must explain missing dependency/browser instead of invoking installers.

## Integration design

Keep all eleven inference-fingerprinted modules byte-for-byte unchanged. Dispatch Perchance in Controller and separate modules before native preflight/session construction. Keep native catalog() and models.json GGUF-only; append a built-in remote choice to run_options and expose separate service settings. Virtual models must never enter scan/reconcile/download/VRAM reassignment logic.

Perchance requires explicit selection of its model ID. Existing Run all and native all-model comparisons stay native-only and identify that scope in the UI. The service choice is always available outside demo mode and has fixed required_vram_gb=8. Live preflight requires exactly one detected NVIDIA GPU with nominal tier 8, rejects 11/12 and larger tiers, but bypasses GGUF, native runtime, context allocation, seed probes and GPU-fit/CPU-recovery paths. Preparation-only checks cannot certify the future machine. Preflight opens no browser and performs no inference. No GPU-memory measurements are attributed to remote inference.

A pure capability-aware planner generates stable remote observation IDs using effective workflow identity, adapter/worker version, service URL, capability policy and original scoring requirements. It groups before execution, excludes unsupported sampling/cache/constrained-decoding controls from applied identity, collapses repetitions to one, and retains all aliases with original definitions/requested settings. Exclude timeout from identity and retain it only as execution metadata. Include prompt style, source, ordered steps, branches/loops, output instructions, checks/oracles and supported options in grouping. Do not merge different tasks or score requirements. Representative selection must be deterministic and independent of requested subset order or results. A request for an alias computes the same observation as a full-suite plan. Completed observations can be reused without rerunning; mappings can grow separately without mutating old evidence.

Write a versioned plan/mapping artifact under .local/workbench/perchance-plans before any calls; include it in evidence ZIP exports. Only one observation file goes into results/perchance-text-generator per effective group. Aliases carry no duplicated scores. Result files retain requested and effective definitions, complete mapping, requested versus applied controls, unavailable dimensions, capability snapshot, exact role messages and serialized instruction, stream chunks, stop/error status, partials and timings. Ordinary-text schema answers are parsed/validated locally; never advertise constrained decoding. Cache claims are not applicable. Native execute/evaluate scoring can be reused through copied definitions and null applied sampling metadata; raw requested sampling remains separately recorded. Reused seed fields must not be misrepresented as applied remote seeds.

Run one sequential owned browser session per selected batch. Preserve the entire workflow, including branches and bounded loops. Per-case deadline spans all calls. Cancellation is signaled across threads but browser operations remain on their owning thread. Poll worker snapshots; capture streamed partials before cancellation; use plugin stop if present and close/reload the owned page on timeout/cancel before another call. Ignore late completions via job IDs. Never reroll wrong answers or timed-out observations. Infrastructure failures remain error records with prior attempts preserved on explicit subsequent runs. Resume skips completed observations, including timeouts, even if their alias has another nominal seed. Pause/stop controls operate between cases or cancel the active call safely. Browser startup is outside timed workflows; batch shutdown closes only owned resources.

Classify execution as remote_service with provider provenance. Unknown service model identity, defaults, weights, GPU memory, token counts, seed/cache verification and prompt/generation timing remain unavailable. Record monotonic request/pipeline/first-visible-text timing where observed and the prompt serializer version. No token-count cap, automatic reply cleanup, synthetic EOS, hidden seed checks, automatic publishing or semantic retries.

## UI and analysis

Add the model to existing individual/one-model selections. Explain fixed 8 GB service scheduling, remote requests and collapse counts in preflight. Add URL/browser settings with native DOM controls; preserve existing UI structure and unrelated styling. Remote-only users can avoid model-folder onboarding without choosing a GGUF folder.

The results table retains one remote observation and its mapping/metadata in Inspect. Export requested case count, independent observed count, aliases, not-applicable claims and error/timeout statuses; plans retain pending work. Extend offline report labeling/counts and keep remote_service cohorts distinct from local GPU cohorts. Report applied controls separately from requests; never show requested temperature zero as applied or missing measurements as zero. Collapse per-repetition expectations without marking aliases as missing independent samples.

## Preparation review

- Reviewed source: native catalog validator requires GGUF filenames; native preflight requires model/runtime/GPU checks and scheduler labels full_gpu. Separate dispatch preserves inference IDs.
- Reviewed capability rule: all 387 active requested cases use text/default cache; 100 variants have three seeded repetitions. Reduce repetitions but preserve distinct effective prompts/tasks. Cache/schema examples require baseline applicability rather than fake feature qualification.
- Reviewed harness defects: trim() changes raw responses, Promise.race does not cancel generation, error partials may appear successful and option objects do not prove sampler control.
- Reviewed portability/lifecycle: owned contexts avoid sharing active EmberAdventures profiles/browsers. Site readiness and real-plugin behavior require a separate live smoke beyond mocks.
- Reviewed identity/reporting: all eleven fingerprint modules remain unchanged; separate provider identity/mapping/classes preserve native observations.
- Resolved defaults: copy the main EmberAdventures harness and use its existing hosted bootstrap. Windows first; configured Linux executable supported, Linux/Unity end-to-end verification separately reported.

## Acceptance checklist and implementation review

Each item requires code/test evidence and final status; a planned item is not implemented merely because this document describes it.

1. Selectable service and fixed 8 GB eligibility; no GGUF reassignment/download path.
2. Read-only remote preflight checks dependency/browser/storage and rejects larger tiers without blocking native runs.
3. Group unsupported controls/repetitions once; preserve distinct prompts, states, representations, workflows and scoring; retain deadlines as execution metadata; stable subset/full-suite identity.
4. Durable mapping before generation; resume skips terminal representatives; aliases never clone scores or independent observations.
5. Text-only worker preserves whitespace/streams/raw result/stop/error evidence and safe job ownership; no images or hidden retries.
6. Deadline/cancel preserves partials, stops/resets before next call and closes only owned resources; respect pause/resume/stop-after-model.
7. Plain-text grading and local schema validation with controls/feature claims explicitly unavailable.
8. Setup/choice/collapse UI without irrelevant onboarding; result/export/report counts actual observations.
9. Preserve native backend/spec/results, inference fingerprint and case IDs.
10. Unit tests cover failures/corruption, grouping, schema/cache, resume, timing/cancel/late completion, settings and native regression. Browser smokes exercise worker and Workbench/Inspect/export; one-prompt real smoke separately verifies live service.
11. Full unittest discovery, preservation audit, JS syntax and relevant browser smokes pass; document unavailable live/platform tests rather than substituting mocks.

## Final implementation review — October 1, 2026

The final code was checked against every acceptance item. Two design details were refined: client GPU/OS remain provenance but are excluded from remote observation identity because they do not control the remote model; the owned browser window uses a dedicated private persistent profile so manual site verification survives shutdown. Neither shares the EmberAdventures browser/profile or edits the saved page.

| Item | Implementation and evidence | Status |
| --- | --- | --- |
| 1 | Controller.selection_models appends the built-in service; native catalog stays GGUF-only. Unit tests cover fixed tier, prohibited reassignment and absent model files. | Passed locally |
| 2 | Separate preflight checks exactly one 8 GB GPU, SDK, browser and storage. Unit tests cover 8/11/12/16 GB, preparation-only, missing prerequisites and corruption; no browser opens. | Passed locally |
| 3 | Pure planner removes unavailable controls, normalizes defaults, groups before execution and sorts representatives. Tests distinguish prompts/states/presentation/schema/scoring/workflows; deadline changes keep identity stable; subset identity is stable and client hardware cannot create duplicate trials. | Passed locally |
| 4 | Mapping precedes browser startup. Terminal wrong answers/timeouts are reused; infrastructure attempts are retained. Unit/browser tests run once then resume without another call. ZIP contains mappings. | Passed locally |
| 5 | Separate worker preserves whitespace/chunks/errors and stops owned jobs. Browser smoke tests late completion, cancellation, subsequent jobs and error partials. Original harness untouched. | Passed with simulated plugin |
| 6 | Whole-case deadline, partial capture, thread ownership and page reset/close. Tests cover timeout/cancel/cleanup, conditions/assignments/loops and finishing the provider on stop-after-model. Pause remains between cases. | Passed locally; real cancellation unverified |
| 7 | Native message builder, parsing, scoring and schema validation reused without changing fingerprint modules. Tests cover schema baseline, multi-step workflow and unavailable cache/sampling/seed claims. | Passed locally |
| 8 | Explicit optional dependency/connection actions, URL/browser settings and remote-only onboarding. Browser test exercises selection/check/run/resume/Inspect/setup; ZIP and offline report count aliases separately. | Passed with simulated transport |
| 9 | Preservation audit: all 11 files unchanged, fingerprint de9b98611a020972925a3a7f1a1cbb962e39bffbcaceb78d229610d4a2436d6d, zero invalidated native cases, unchanged existing prompts/context recipe and no evidence mutations. | Passed |
| 10 | 16 provider unit tests and 9 reporting tests pass. Worker, Workbench and offline-report browser smokes pass. Unit prerequisite mocks support browser-free CI. | Passed locally; CI execution pending |
| 11 | JS syntax, Git whitespace and preservation checks pass. Final full unittest discovery result recorded below. | Passed locally |

The real-service smoke opened the existing hosted worker in a separate owned browser. Perchance returned a security-verification page; a Cloudflare challenge hostname failed DNS resolution and the plugin never became available. No generation request ran and no real remote benchmark result was saved. This is blocked live validation, not successful inference. Use Worker setup → Verify Perchance connection for manual verification in the owned window. No challenge bypass was attempted. Windows Edge transport is tested; Linux/Unity end-to-end execution remains unverified.

A read-only preview maps 387 requested cases to 160 distinct effective observations, with 227 collapsed cases and zero completed Perchance observations. Genuine multiple workflow calls remain within each observation. These are planned counts, not study data. Source changes remain uncommitted.

Earlier discovery runs exposed the existing full-suite demo test's 30-second Windows wait limit and cleanup file-lock errors after that timeout. Its bounded wait was increased to 120 seconds without changing inference. Early provider-test defects were corrected and targeted tests rerun; only the final discovery result below is the acceptance result. A process-only pull.rebase=false Git override satisfied existing merge-oriented fixtures without changing the user's global configuration.

Final regression result: `python -m unittest discover -s tests -v` ran 399 tests in 571.754 seconds: OK, 4 skipped (Windows host has no working Bash). The 25 targeted provider/reporting tests passed, and worker/Workbench/offline-report browser smokes plus the existing native VRAM-assignment browser smoke passed. Read-only preflight with the installed private project environment detected NVIDIA GeForce GTX 1070 at the 8 GB tier and returned ready with no issues and 160 pending observations. This certifies local prerequisites, not Perchance site access or real inference.

## Run-all update — October 2, 2026

User-directed changes: local tests/examples now use 120 seconds; the provider planner applies a fixed 300-second whole-workflow deadline while retaining the requested local deadline in alias metadata. Overview Run all on an actual 8 GB tier validates both phases, displays Perchance last, and runs it after all native GPU/recovery passes. Larger workers, demo mode and explicitly targeted local/all-local selections exclude this automatic phase. Cancel/stop-after-model must prevent starting the remote phase. Completed native work must not block pending remote baselines.

The 58-definition catalog has 357 requested cases and maps to 160 independent Perchance observations (197 aliases collapsed). This is a read-only preview, not a live benchmark run. Native fingerprint 56502881bc3c89f6b58c8f5e755b32f58cbd675274ed5363293b598aaddf9787 remains unchanged, and saved case IDs from all four local models remain valid after deadline reduction. Existing evidence was not rewritten.

Review: controller composes preflight counts without inserting remote jobs into the native scheduler; the native scheduler finishes recovery and closes its model before the provider starts. Provider append mode retains overall progress and local completion/error counters. The new combined-run unit tests cover order, complete-local/pending-remote resume, exact-tier exclusion, targeted scopes, missing dependencies, cancellation/stop and provider deadline identity. The real browser/HTTP smoke covers Overview Run all with no local work and subsequent targeted resume using simulated provider transport. Live service generation is not started by these checks.

Run-all update validation: full unittest discovery ran 416 tests in 575.147 seconds, OK with 4 Bash-related Windows skips. The 59 focused checks and combined Overview/targeted-resume browser smoke passed with simulated transport. JavaScript syntax and Git whitespace checks passed. No real benchmarks were started and existing saved results were preserved.

## Connection update — October 8, 2026

User-supplied EmberAdventures comparison evidence demonstrated that both the original RPG worker and the exact `USER:\n` serialized instruction work in a normal Edge session attached through CDP. The previous independently Playwright-launched RPG session stalled with no text. This isolates the working connection approach without proving which browser/profile/verification detail caused the prior restriction.

The Workbench now selects `ControlledBrowserBackend` in `workbench/perchance_connection.py` for standalone and appended remote phases. It launches normal visible Edge/Chrome separately, attaches on loopback CDP (default 9223), uses a dedicated `perchance-controlled-profile`, reuses the hosted page between requests, and disconnects after operations while leaving the browser open. The inference adapter/worker are unchanged so existing observation IDs and timeout-independent completion remain valid. Connection provenance is recorded separately in the response environment. The setup health check now exercises normal browser/CDP against `about:blank`, without generating or contacting Perchance. Explicit connection verification reports plugin availability only.

Review against the preparation requirements: the 300-second workflow deadline, serializer, unsupported-control collapse, exact 8 GB scheduling, native-first ordering, stop/cancel, raw chunks, previous infrastructure attempts and no hidden retries are retained. The normal browser remains available on the host for manual verification; it is not streamed to the laptop. New unit and real CDP/HTTP browser fixture tests cover ownership, launch arguments, page reuse/reconnect, readiness, cancellation and unchanged identity. One harmless live diagnostic request returned text in 4.410 seconds; it is not scored study data. Validation totals are recorded in `TEST_REPORT.md` after the complete regression run.
