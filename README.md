# RPG Testing Workbench — native llama.cpp

A browser-controlled benchmark for **original JSON state + new information → structured state update**. The model and harness run on the GPU computer; your laptop is a private remote control through Tailscale.

**The active workbench no longer uses LM Studio.** It runs its own `llama-server`, browses Hugging Face model repositories, installs selected GGUF variants, and handles a full-GPU primary pass followed by an automatic recovery pass when needed. Setup can ask questions; a running experiment never waits for a repair popup.

## Open it without a terminal

Update `main` with GitHub Desktop, open the repository folder, and double-click **Start Workbench.vbs**. Python 3.10+ must already be installed. The graphical bootstrap asks permission before creating its private Python environment and installing missing requirements. Git is required by the harness's own tests and Git synchronization. No drivers are installed.

**Start Demo.vbs** opens the same interface with a simulated model and no hardware requirement. It cannot install real models or runtimes. The current enabled suite contains **110 simulated cases**, including 84 prompt-wording calibration cases (4 tasks × 7 prompt variants × 3 deterministic repetitions). Run preflight, run, then run again to verify that completed cases are skipped. These outputs are not measurements of model quality or GPU speed.

## First-time setup

1. **Choose your models folder.** It starts unset. On the GPU computer, **Choose models folder…** opens the operating system’s normal folder picker. The path is saved immediately and model scanning continues separately, so you can switch to **Installed models** while it scans. Existing GGUFs are discovered in place. If empty, confirm **Use this empty folder**, or choose another. There is no automatic C-drive model location.
2. **Find models.** Search a name or enter a Hugging Face `publisher/repository`, view quantizations and file sizes, select variants and a VRAM tier, then approve their download. Recommendations are estimates, not measurements. Split GGUFs are handled as one variant. You may also download models manually into your chosen folder.
3. **Native runtime.** Browse official llama.cpp releases and explicitly install a suitable GPU build, or locate an existing `llama-server`. Runtime archives and caches stay inside the repository, not in the models folder. An old GTX 1080 needs a compatible driver/build; the runtime labels and preflight checks help identify candidates but cannot promise compatibility before a real load.
4. **Preflight.** Resolve any listed issue using its specific action button. Preflight checks benchmark readiness only; Workbench unit/smoke tests are run separately with **Run Unit Tests**. It checks only models needed for unfinished work. A completed model does not need to remain installed. Existing uncatalogued models have a VRAM dropdown and an **Accept recommended** action. Model identity uses filename, size, modification time, and known repository/revision metadata; preflight does not reread entire GGUF files to generate SHA-256 hashes. Source-provided hashes are retained when available.
5. **Run remaining tests.** Leave it running. No model-failure confirmation dialog will hold the rest of the queue hostage.

This folder choice applies **only to model files and their partial downloads**. Model assignments are stored in a machine-local root `models.json`; a fresh checkout can discover GGUFs before that file exists, and the file is created only when local model metadata is saved. `models.json` is ignored by Git. Tests stay in `test_specs/`. Results, logs and operational settings stay under `.local/workbench/` in the repository; runtime files use `.local/runtime/`. Credentials and weights are excluded from Git.

## Targeted runs

**Run Individual Test** in the left sidebar selects one model—or **All** models—and one enabled test definition, with all enabled variants or one chosen variant. **Test One Model** shows every enabled test with a checkbox; all are selected by default, and you can run any checked subset for one model. Both keep the test's repetitions, seeds and sampling settings; only pending cases run. Use the page's check button to preflight that selection, or its run button to preflight and execute it. Progress and any repair actions appear in Overview; normal Results, Comparison and exports contain the evidence.

Selection is temporary and does not edit `models.json` or test files. Targeted and full runs share case IDs and context allocation, so finishing targeted cases removes that work from the normal queue. The selected model must still satisfy the normal hardware tier and runtime checks. Unrelated missing or unassigned models do not block a selected run. Source-update restarts and automatic repair preserve the selection; they never broaden it to the entire queue.

## What happens while you are away

**Primary pass:** load a model with all layers requested on GPU, automatic fitting disabled, and llama.cpp reasoning explicitly set to `off` so every model is measured in direct-output mode rather than template-selected `auto` reasoning. Inspect the backend's placement report and readiness probe. If CPU model placement or GPU-memory failure occurs, record the failed qualification, unload, and proceed to the next model. Unknown placement is not called full GPU.

**Recovery pass:** after primary work finishes, revisit memory-related skips, smallest downloaded footprint first. Retry full GPU, then try a bounded sequence of hybrid placements. Hybrid results have separate identities and `execution_class: cpu_offloaded`; they are not pooled with full-GPU results. Unrelated model/runtime errors do not enter an endless retry loop.

**Safety deadlines:** model loading has a 300-second (5-minute) infrastructure watchdog. Every benchmark test also has an explicit positive `timeout_seconds` field; all current tests and bundled examples are set to **60 seconds**. A case that reaches its test limit has only that active request cancelled, keeps its streamed partial output, is recorded as a terminal failed timeout, resets the prompt slot, and continues to the next case. Load-time stalls still stop the owned llama-server process. Hybrid layer trials are bounded to four; automatic context expansions to two. The policy is recorded with results.

**Context:** generous automatic allocation includes the shared prefix, source, prompts and workflow structure. There is no context slider or artificial output-token cap. Native context is finite. If capacity is exhausted, the attempt is preserved and the worker retries from the beginning with a larger allocation when possible. Extra context consumes memory, so successful GPU fit is still required.

You can explicitly **Pause after case**, **Resume**, **Stop after model**, or **Stop now**. Completed files survive interruption. A bad JSON answer is a completed model result, not a reason to reroll until it passes.

## Results and visibility

Overview shows the current pass, execution class, reported GPU/CPU layer counts, and available whole-device memory samples. Layer reports do not prove that Windows will never page GPU allocations. CPU utilization, a host-pinned buffer, or a CPU-mapped model file alone is not proof of CPU model-layer execution.

**Results** exposes raw prompts, responses, scores, attempts, timings and provenance. Delete a case file to make that case pending again. A failed primary qualification and a later hybrid result are separate records. Recovery interrupted before completion resumes as recovery work.

**Comparison** separates model files, test definitions, context configurations, hardware, software and execution classes. **Download all logs & results** exports JSON evidence, logs and CSV/JSON summaries. Application logging and Git writes occur outside timed workflows. GPU telemetry is sampled in memory through NVML; it is a sampled total-device peak, not exact model-only memory accounting.

## Tests and caching

All experimental settings live in `test_specs/*.json`, with a validating editor in the UI. The normal V2 model-facing state-update prompt uses short conversational wording: a plain-language request, a pretty-printed **Current State**, the **New Information**, and the requested output format. Four `prompt_calibration_*` tests preserve the historical V1 clinical prompt and compare it with V2 plus four controlled alternatives: **only changed fields**, **smallest patch**, **value-difference rule**, and **one example**. V1 Original also preserves the old indexed-array/SOURCE presentation and extra time-test wording; V1 Raw-JSON Control isolates the clinical wording from those representation differences. The defaults cover a time change, a clothing-array append without movement, and the retail inventory test. Examples can be imported for large shared-prefix cache-on/off questions, conditional follow-ups, verification/repair, and narration followed by state updating using the same model.

Native llama.cpp exposes the cache controls. The harness starts the server with a Workbench-owned slot path under `.local/runtime-cache/slots`, clears the slot between required measurements, and records reuse evidence. Missing or inconsistent cached-token counters mark a cache measurement unverified; keeping a chat open is not accepted as proof. The interface does not use `experiment.json` or require a hand-written `worker.local.json`.

## Laptop and Unity

On the desktop, open **Worker setup → Enable private Tailscale access** and display the pairing key. Open the displayed address on the laptop and pair that browser. These controls operate the desktop; inference remains on loopback. Keep the desktop awake. Tailnet permissions and the host firewall still apply. No public listener, port forwarding or Funnel is enabled.

Unity support is intentionally practical rather than a promise of zero setup: put the repo, Python environment, native runtime and models on permitted storage, select the models folder there, then submit the generated job with Unity OnDemand/Slurm. Preparation checks on the laptop cannot certify a remote installation. The job requests a GPU and forwards scheduler warning/termination signals so the worker can stop and retain evidence. Actual cluster authorization and runtime compatibility must be checked on Unity.

## Git behavior and validation

Optional source synchronization pulls before a real run. When code changes, the supervisor restarts with the new source and resumes the explicitly requested Run; automatic restart chains are bounded. No hot-reloading experimental code during a measurement. Optional result publishing uses a worker-specific branch, narrow staging, and no force reset or automatic stash.

Only synthetic safe-for-work data belongs in this public repository. Do not publish private saves, real patient/student records, explicit content or credentials.

See [TEST_REPORT.md](docs/TEST_REPORT.md) for actual test evidence, [WORKBENCH_GUIDE.md](docs/WORKBENCH_GUIDE.md) for operation details, and [PLANNED_CHANGES.md](docs/PLANNED_CHANGES.md) for requirement coverage and validation limits. UI/subprocess fixtures are not real GPU inference.

The old `rpgbench/`, `run_worker.py`, `fixtures/`, and `experiment.json` are retained only for historical reproduction. The active UI is `workbench/` and native-only.
