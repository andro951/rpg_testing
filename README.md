# RPG Testing Workbench â€” native llama.cpp

A browser-controlled benchmark for **original JSON state + new information â†’ structured state update**. The model and harness run on the GPU computer; your laptop is a private remote control through Tailscale.

**The active workbench no longer uses LM Studio.** It runs its own `llama-server`, browses Hugging Face model repositories, installs selected GGUF variants, and handles a full-GPU primary pass followed by an automatic recovery pass when needed. Setup can ask questions; a running experiment never waits for a repair popup.

## Open it without a terminal

Update `main` with GitHub Desktop, open the repository folder, and double-click **Start Workbench.vbs**. Python 3.10+ must already be installed. The graphical bootstrap asks permission before creating its private Python environment and installing missing requirements. Git is required by the harness's own tests and Git synchronization. No drivers are installed.

**Start Demo.vbs** opens the same interface with a simulated model and no hardware requirement. It cannot install real models or runtimes. The current enabled suite contains **110 simulated cases**, including 84 prompt-wording calibration cases (4 tasks Ã— 7 prompt variants Ã— 3 deterministic repetitions). Run preflight, run, then run again to verify that completed cases are skipped. These outputs are not measurements of model quality or GPU speed.

## First-time setup

1. **Choose your models folder.** It starts unset. On the GPU computer, **Choose models folderâ€¦** opens the operating systemâ€™s normal folder picker. The path is saved immediately and model scanning continues separately, so you can switch to **Installed models** while it scans. Existing GGUFs are discovered in place. A successful rescan/preflight treats this folder as the authoritative installed-model inventory: if you manually delete a model's GGUF files, its machine-local catalog assignment and stale artifact cache are removed automatically while historical benchmark results are retained. An unavailable/disconnected models folder is never treated as an empty authoritative scan. If empty, confirm **Use this empty folder**, or choose another. There is no automatic C-drive model location.
2. **Find models.** Search a name or enter a Hugging Face `publisher/repository`, view quantizations and file sizes, select variants and a VRAM tier, then approve their download. Recommendations are estimates, not measurements. Split GGUFs are handled as one variant. You may also download models manually into your chosen folder.
3. **Native runtime.** Browse official llama.cpp releases and explicitly install a suitable GPU build, or locate an existing `llama-server`. Runtime archives and caches stay inside the repository, not in the models folder. An old GTX 1080 needs a compatible driver/build; the runtime labels and preflight checks help identify candidates but cannot promise compatibility before a real load.
4. **Preflight.** Resolve any listed issue using its specific action button. Preflight checks benchmark readiness only; Workbench unit/smoke tests are run separately with **Run Unit Tests**. It checks only models needed for unfinished work. A completed model does not need to remain installed. Existing uncatalogued models have a VRAM dropdown and an **Accept recommended** action. Model identity uses filename, size, modification time, and known repository/revision metadata; preflight does not reread entire GGUF files to generate SHA-256 hashes. Source-provided hashes are retained when available.
5. **Run remaining tests.** Leave it running. No model-failure confirmation dialog will hold the rest of the queue hostage.

This folder choice applies **only to model files and their partial downloads**. Model assignments are stored in a machine-local root `models.json`; a fresh checkout can discover GGUFs before that file exists, and the file is created only when local model metadata is saved. `models.json` is ignored by Git. Tests stay in `test_specs/`. Real benchmark result JSON files are stored under tracked `results/` so they are normal Git evidence. Logs, preflight reports and operational settings stay under `.local/workbench/`; runtime files use `.local/runtime/`. Credentials and weights are excluded from Git. On first launch after this change, legacy result JSON under `.local/workbench/results/` is migrated into `results/` without overwriting conflicting evidence.

On **Logs**, **Download logs** saves the displayed entries as `rpg-testing-logs.txt`, and **Copy logs** copies the same text. The view contains the latest 300 events. Copy supports plain HTTP/Tailscale through a fallback; if the browser blocks automatic copying, a dialog selects the text for Ctrl+C. Both buttons are disabled when the log view is empty.

## Targeted runs

For the objective results table, double-click **Open_Results_Table.bat**. It now has
five grouping presets, an editable ordered grouping list, user-created/deletable
presets, and percentage subtotals at the bottom of each collapsible group. See
[results table grouping](docs/results-table-grouping.md) for controls and total rules.

**Run Individual Test** in the left sidebar selects one modelâ€”or **All** modelsâ€”and one enabled test definition, with all enabled variants or one chosen variant. **Test One Model** shows every enabled test with a checkbox; all are selected by default, and you can run any checked subset for one model. Native-model runs keep the test's repetitions, seeds and sampling settings; only pending cases run. Perchance runs each repetition independently, collapsing only unavailable setting variants within a repetition. Seeds are forwarded experimentally without a reproducibility guarantee. Use the page's check button to preflight that selection, or its run button to preflight and execute it. Progress and any repair actions appear in Overview; normal Results, Comparison and exports contain the evidence.

Selection is temporary and does not edit `models.json` or test files. Targeted and full runs share case IDs and context allocation, so finishing targeted cases removes that work from the normal queue. The selected model must still satisfy the normal hardware tier and runtime checks. Unrelated missing or unassigned models do not block a selected run. Source-update restarts and automatic repair preserve the selection; they never broaden it to the entire queue.

## What happens while you are away

**Primary pass:** load a model with all layers requested on GPU, automatic fitting disabled, and llama.cpp reasoning explicitly set to `off` so every model is measured in direct-output mode rather than template-selected `auto` reasoning. Inspect the backend's placement report and readiness probe. If CPU model placement or GPU-memory failure occurs, record the failed qualification, unload, and proceed to the next model. Unknown placement is not called full GPU.

**Recovery pass:** after primary work finishes, revisit memory-related skips, smallest downloaded footprint first. Retry full GPU, then try a bounded sequence of hybrid placements. Hybrid results have separate identities and `execution_class: cpu_offloaded`; they are not pooled with full-GPU results. Unrelated model/runtime errors do not enter an endless retry loop.

**Loading and test deadlines:** model loading and its readiness probe have no elapsed-time deadline. They wait for readiness, manual Stop or a runtime failure. Loading progress/logs report the phase, elapsed time and time since the last runtime output every five seconds; silence alone does not prove a hang. Legacy `load_timeout_seconds` settings are ignored. Every benchmark test has an explicit positive `timeout_seconds` field; the configured value controls only the time allowed for an active workflow after loading. It is excluded from case IDs, test-version comparison and table grouping. Changing it does not reopen completed cases, including timeouts; actual deadlines remain saved as run metadata. A case that reaches its test limit has only that active request cancelled, keeps its streamed partial output, is recorded as a terminal failed timeout, resets the prompt slot, and continues to the next case. Hybrid layer trials are bounded to four; automatic context expansions to two. The policy is recorded with results.

**Context:** generous automatic allocation includes the shared prefix, source, prompts and workflow structure. There is no context slider or artificial output-token cap. Native context is finite. If capacity is exhausted, the attempt is preserved and the worker retries from the beginning with a larger allocation when possible. Extra context consumes memory, so successful GPU fit is still required.

You can explicitly **Pause after case**, **Resume**, **Stop after model**, or **Stop now**. Completed files survive interruption. A bad JSON answer is a completed model result, not a reason to reroll until it passes.

## Results and visibility

Detailed objective-test diagnostics can be generated offline with `python -m evaluation`. Reports explain format, operation structure, pointer resolution, requested changes, array order/content and final-state checks, while keeping saved scores and raw evidence unchanged. See [evaluator instructions](evaluation/README.md) and [coverage review](docs/evaluator-plan/implementation-review.md).

Prompt-sharing metadata lives in [optimization/sharing.json](optimization/sharing.json). It records reviewed instruction locations, compatible component families and ordered expansion scopes for future prompt optimization. Validate it with `python -m optimization`; see [catalog instructions](optimization/README.md). Metadata does not start optimization runs or alter existing benchmark prompts.

Generate a self-contained offline statistics dashboard from saved evidence with `python -m reporting.report`. Open `.local/reports/statistics.html` in a modern browser. It opens on a compact objective-results matrix with 24-pixel pass/fail squares, models as columns, variants/repetitions as rows, test subtotals and model totals. It includes tests with fixed answer or final-state oracles, current/historical scope filters and links to original evidence. Dialogue and other open-ended generation are excluded from this table and its totals, with saved evidence preserved for a separate view later. The existing long-array comparison, failure and latency views remain available. See [offline reporting](reporting/README.md) for ZIP input, matching rules and tests.

Overview shows the current pass, execution class, reported GPU/CPU layer counts, and available whole-device memory samples. Layer reports do not prove that Windows will never page GPU allocations. CPU utilization, a host-pinned buffer, or a CPU-mapped model file alone is not proof of CPU model-layer execution.

**Results** exposes raw prompts, responses, scores, attempts, timings and provenance. Delete a case file to make that case pending again. A failed primary qualification and a later hybrid result are separate records. Recovery interrupted before completion resumes as recovery work.

**Comparison** separates model files, test definitions, context configurations, hardware, software and execution classes. **Download all logs & results** exports JSON evidence, logs and CSV/JSON summaries. Application logging and Git writes occur outside timed workflows. GPU telemetry is sampled in memory through NVML; it is a sampled total-device peak, not exact model-only memory accounting.

## Tests and caching

The Perchance Text Generator adapter follows the standing [provider capability policy](docs/perchance-capability-policy.md): unsupported or unverified setting/seed-only sweeps collapse within each configured repetition; ordinary repetitions remain independent service trials, with collapsed cases mapped to that observation. They are never reported as independently executed controlled trials. The adapter is implemented and locally tested; real service inference remains unverified until connection setup succeeds.

Preflight first checks whether Perchance has pending work on this worker, then verifies its browser dependency and local browser launch. Missing or broken setup opens an **Install Perchance browser dependency?** popup. **Yes, install** installs Playwright and a managed Chromium browser if needed, verifies launch, then continues preflight. **No, skip this run** records the choice and leaves Perchance pending while local tests can continue. A preflight's No applies to exactly one matching run; the next run asks again if setup is still needed. Installation occurs on the worker computer, including when controlling through Tailscale.

In **Worker setup**, use **Verify Perchance connection** to complete any site verification in the separate window. Select **Perchance Text Generator** under **Test One Model** or **Run Individual Test**, check the plan, then run. It requires exactly one detected NVIDIA GPU in the 8 GB tier; larger tiers are excluded. Choose **Skip local model-folder onboarding** for a remote-only worker. The browser window closes after the batch; its private profile under `.local/workbench/perchance-profile` retains site verification without sharing the EmberAdventures browser. No saved Perchance page is changed.

Each distinct effective workflow runs once per configured repetition. Requested temperature/cache/seed/schema constraints remain recorded as unavailable controls; ordinary-text schema answers are validated locally. Observation mappings are saved before generation and exported with results. **Run all** and **All models** keep their local-model scope. See [preparation and acceptance review](docs/perchance-integration-prep.md).

The current database suite is built with `python -m test_builder`: 14 cases and 41 complete prompts, covering Update, Append, Remove, transfer between collections, and No change. Shared database rules live in `test_builder/database-rules.txt`; the common explanation of all four operations and typed value-based paths lives in `test_builder/methods/value_patch.txt` (standard JSON Patch remains a separate method). Task wording and schema/data inputs stay separate so future methods can reuse them. The `prompt-review/` folder contains only one complete prompt per `.txt` file. Draft cases remain disabled until Isaac and the assistant approve their exact prompts. Edit source templates/data and rebuild; generated exports are refreshed and obsolete managed exports removed.

The previous 61 benchmark/example definitions and their metadata are preserved under `archives/test-suite-2026-10-14/`, with verified source hashes. Saved responses and scores remain unchanged. The ten deferred tasks are listed in `docs/test-suite-v2/deferred-tests.txt`. See `docs/test-suite-v2/build-and-review.txt` for scope and review details.

Native llama.cpp exposes the cache controls. The harness starts the server with a Workbench-owned slot path under `.local/runtime-cache/slots`, clears the slot between required measurements, and records reuse evidence. Missing or inconsistent cached-token counters mark a cache measurement unverified; keeping a chat open is not accepted as proof. The interface does not use `experiment.json` or require a hand-written `worker.local.json`.

## Laptop and Unity

On the desktop, open **Worker setup â†’ Enable private Tailscale access**. Open the displayed address on the laptop while connected to Tailscale; the workbench opens directly without a pairing key. These controls operate the desktop; inference remains on loopback. Keep the desktop awake. Tailnet permissions and the host firewall govern access. The service accepts only loopback/Tailscale clients and retains Host/Origin checks. No public listener, port forwarding or Funnel is enabled.

Unity support is intentionally practical rather than a promise of zero setup: put the repo, Python environment, native runtime and models on permitted storage, select the models folder there, then submit the generated job with Unity OnDemand/Slurm. Preparation checks on the laptop cannot certify a remote installation. The job requests a GPU and forwards scheduler warning/termination signals so the worker can stop and retain evidence. Actual cluster authorization and runtime compatibility must be checked on Unity.

## Git behavior and validation

Optional source synchronization pulls before a real run. When code changes, the supervisor restarts with the new source and resumes the explicitly requested Run; automatic restart chains are bounded. No hot-reloading experimental code during a measurement. Result JSON under `results/` is intentionally visible to normal Git workflows on the main checkout. Optional result publishing still mirrors evidence to a worker-specific branch for unattended checkpoints, using narrow staging and no force reset or automatic stash.

Only synthetic benchmark data belongs in this public repository. Test outputs may include mature fictional benchmark content when that is part of the experiment. Do not publish private saves, real patient/student records, credentials, or other personal data.

See [TEST_REPORT.md](docs/TEST_REPORT.md) for actual test evidence, [WORKBENCH_GUIDE.md](docs/WORKBENCH_GUIDE.md) for operation details, and [PLANNED_CHANGES.md](docs/PLANNED_CHANGES.md) for requirement coverage and validation limits. UI/subprocess fixtures are not real GPU inference.

The old `rpgbench/`, `run_worker.py`, `fixtures/`, and `experiment.json` are retained only for historical reproduction. The active UI is `workbench/`, with native inference and an explicitly selected Perchance remote text provider.

On 8 GB workers, Overview **Run all remaining tests** runs eligible local models first (including native recovery), then Perchance Text Generator unless you declined its setup for this run. Local test definitions use a 120-second watchdog; Perchance uses 300 seconds. Completed local cases remain complete, so the same button can run only the remaining Perchance observations. Larger workers and explicitly targeted local runs do not include Perchance. Configured Perchance repetitions run independently; unsupported setting variants collapse within each repetition. Existing compatible baselines fulfill only repetition zero.


### Manual test judgements

`Open_Results_Table.bat` opens a local viewer with separate Rejected, Needs review,
and Accepted tables, in that order. Every definition initially needs review.
Click a variant label or a test-version group's Judge action to record a decision.
Rejected definitions stay saved but cannot run again; editing the execution
definition creates a fresh Needs review definition. Grouping panels start collapsed
and retain separate presets per table. Keep the launcher console open to save reviews.
The offline HTML remains a read-only snapshot. See [review and grouping details](docs/results-table-grouping.md).


### Prompt Optimization

Open the **Prompt Optimization** Workbench tab; it scans runnable benchmark models and the worker's installed Codex. Choose **Codex** or **Local model** for prompt writing. Codex has separate GPT model and effort selectors populated from its local model catalog. It uses the worker's existing Codex sign-in and one persistent thread per session, including after pause/resume or a Workbench restart. Local model mode keeps its model, randomized temperature and reasoning controls. Writer selections apply to new sessions; Continue uses the saved writer and thread. The pilot optimizes collection-transfer operation instructions: an origin pass opens all matching task-type tests across every runnable host model. Only complete host-cohort candidates qualify for the top three. Maximum attempts defaults to 20; benchmark reasoning always stays off. Sessions, raw proposals and objective feedback are stored separately under `optimization_results/`. Export/import sessions and **Evaluate remaining on this machine** support other hosts without generating new candidates. See [Codex writer details](docs/prompt-optimization/codex-writer.txt) and [the optimization plan](docs/prompt-optimization/optimization-plan.md).

Generator context and output space are managed automatically from the selected model and each actual request. There are no token controls in the optimizer settings; measured allocation and pruning decisions remain available in evidence.
