# Workbench usage and execution guide

## 1. First launch

Update the repository using GitHub Desktop and open its folder. On Windows, double-click `Start Demo.vbs` to inspect the UI without loading a real model. Double-click `Start Workbench.vbs` for real tests. Reopening the launcher while a worker is active opens the existing worker instead of launching duplicate work.

Python 3.10+, Git and the intended inference runtime must exist. The graphical bootstrap asks permission to create `.venv-workbench` and install requirements there when needed; it does not change drivers or system packages. Early startup failures are written to `.local/launcher-error.log` or `.local/setup.log`.

Demo results live separately in `.local/demo`. Its outputs and per-call timing values are simulated test doubles, not measurements of a model. The normal real-result publication switch does not publish demo runs.

## 2. Model discovery

Run preflight. For LM Studio the worker reads recognized settings files to find its CURRENT model directory. It does not substitute a guessed default weights folder. An unknown settings layout needs a one-time UI folder selection. A readable configured directory remains authoritative over a fallback; change LM Studio's own setting if the configured location is wrong. Empty directories require confirmation.

The folder browser runs on the GPU host, even when accessed from a laptop. The scanner reads GGUF metadata, groups split shards, excludes projector files, discovers local paths and resolves model keys using LM Studio inventory where possible. Exact relative artifact paths are the fallback. Duplicate/ambiguous matches are reported rather than silently choosing a quantization.

Assign each uncatalogued variant a VRAM tier from the dropdown, or accept the estimate. The recommendation is based on file size and conservative overhead; it is not measured runtime memory. The assignment is saved to `models.json`. Known catalogued models retain their assignments. No hand-written model binding is required.

The scheduler uses tiers 8, 12, 16, 24, 32, 40, 48 and 80 GB. A variant is tested on its assigned tier and one tier above. The explicit exception allows 8 GB variants on 11 GB hardware; 11 GB never qualifies for a 12 GB variant. GPU identity is recorded separately: equal VRAM does not imply equal speed.

## 3. Preflight and manual repairs

Preflight and Run share the pending-work planner. It determines completed versus pending cases before requiring model files for unfinished work. Missing weights do not block a model whose exact cases are already complete. A new test, artifact or relevant implementation version can legitimately create new cases.

Preflight checks test/catalog validity, result checksums, artifact discovery, shard completeness, paths, software/API availability, applicable GPU tier, some free-memory/disk conditions, and required cache support. Repository self-tests run before proceeding. The execution plan shows pending cases and required model loads.

Each fix requires an explicit click and confirmation. Supported repairs include starting the LM Studio server, downloading an exact catalogued GGUF, creating a needed directory, confirming an empty model folder, unloading specified existing model instances, saving/pushing catalog/test edits, and deleting a corrupt result. Account, driver, administrator and unsupported-runtime issues remain visible rather than being silently modified.

Preflight does not generate benchmark answers. Run rechecks preflight and then probes each loaded model outside benchmark timing. A nonempty normally completed response is required; exact READY compliance is recorded separately so harmless formatting does not exclude a weak model.

Preparation for another GPU is labelled separately. It cannot certify a future Unity allocation, another host's filesystem, driver or permissions. The actual allocated worker must perform its own live check. A file-size check is not proof that loading will fit; load-time failures remain possible and are recorded.

## 4. Run, pause, stop and resume

Run executes cases serially and groups work by model. Pause after case lets the current workflow finish and save before waiting. Resume continues. Stop after model completes that model's pending group. Stop now cancels an active request where the backend supports cancellation and records an interrupted case as aborted. An external LM Studio load command may need to return before cancellation completes; unrelated LM Studio processes are not killed.

Closing the browser does not stop the worker. Close worker closes the service only after active work is stopped. Remote control requires an awake host with the workbench already running.

Incorrect JSON, wrong state and backend-truncated answers are retained as completed outcomes, not repeatedly sampled until correct. Infrastructure errors and aborted cases remain pending for a later Run. Declared verification/repair loops are different: their extra calls are part of the experimental method, and intermediate responses remain in the record.

## 5. Self-contained tests

Test definitions are authored and validated in the browser JSON editor. They are not per-run settings. The default suite contains `time_only` and `clothing_append`, each with direct standard patch, direct semantic patch, analyze→standard patch and analyze→semantic patch. This produces eight cases per applicable model.

Schema version 2 uses `workflow: steps`. The `source` contains initial state and new evidence. Ground truth stays in `expected_state` or expected answers outside source. A generation step declares ID, prompt, output type, sampler settings, optional `uses` references to previous outputs, and optional `when` conditions. A bounded loop declares `max_iterations` and an `until` condition. `assign` replaces an earlier output alias during repair.

Supported outputs are text, JSON with an optional schema, boolean, string and enum. Structured decoding, where the backend supports it, constrains format; it does not establish semantic correctness. Arbitrary code execution and external schema references are not allowed.

Importable examples:

- `cached_questions`: a larger shared background with cache-on/off question variants and a conditional new-time follow-up.
- `verify_repair`: analysis, patch, verification and at most two repairs.
- `narrate_then_update`: narration at temperature 0.8 followed by a separate state-update call at temperature 0 using the same loaded model.

These are smoke examples, not a sufficient research dataset. The narrative example deliberately has a fixed outcome. For truly open-ended narration, an exact final-state oracle must be designed separately. Substring objective checks are not a scientific story-quality judgment. A separately managed external LLM judge service is not implemented.

## 6. Caching and automatic context

The UI and test files offer no arbitrary context/output limit. Internally the worker estimates context allocation from source, shared prefix, instructions and workflow prompts, adds headroom, respects the model's finite native context and records that allocation. This is not unlimited memory. The native backend also tokenizes the formatted request and rejects an oversized input rather than trimming it. Finite context exhaustion and backend cutoffs remain visible.

Controlled caching requires native llama.cpp. The adapter uses a single owned slot, explicit reset, cache reuse/erasure requests, and backend cached-token counters. Missing evidence or failed reuse conditions invalidate the measurement and exclude it from aggregate cache/timing comparisons. A variant may declare `min_cached_tokens`; the default establishes some reuse, not proof that every shared token was cached.

LM Studio's adapter blocks controlled cache-on/off variants instead of pretending ordinary repeated prompts prove caching. Other multi-call workflows work there. Native tests require a compatible `llama-server` with slot/template/tokenizer/schema endpoints; installation or replacement is explicit. Whole-pipeline timing includes cache reset and extra request work, while individual request timing is retained separately.

## 7. Evidence and timing

Results: `.local/workbench/results/<model-id>/<case-id>.json`. Logs: `.local/workbench/logs/`. Status is first, checksums detect corruption, and writes are atomic. There is no completion tracker. `.local/workbench/artifacts.json` remembers fingerprints, not completion. Deleting a result schedules the case again; deletion is recorded in logs.

Evidence includes exact model/test/variant definitions, artifact hashes, hardware/software target, provenance, load/probe metadata, prompts, raw stream chunks, returned text and separately exposed reasoning text, sampler settings, finish reasons, usage/cache counters, scores and timings. Ground truth is never automatically included in inference prompts.

Timing includes local request duration, time to first streamed token, first visible text and whole-workflow duration. It is not pure GPU kernel timing. Pure decoding throughput is not estimated by dividing total request time by output tokens. Scoring and file writes occur after the workflow timer. Backend diagnostics/UI status remain in memory during workflows; application logs and Git checkpoints flush between measured workflows. OS/driver/LM Studio internal logging is outside this application's control.

Peak VRAM and full GPU residency are not independently measured in this release; they are marked unavailable/unverified. A successful preflight or load is not proof of consumer-GPU viability.

Inspect/delete results in the UI. Delete contaminated cases, not valid failures merely because they are undesirable. Export retains corrupt raw files and lists them in the summary. Error/abort records can be replaced by a later attempt; export evidence before deleting anything needed for an audit.

## 8. Git and private remote control

Use a real Git clone for source sync, normally obtained with GitHub Desktop. ZIP users can disable source sync but still need Git for the repository tests. Pull is fast-forward only. Catalog/test edits have a narrowly scoped Save and push action; unrelated changes must be resolved separately. A changed implementation runs only after Restart creates a fresh process. Result publishing is optional, on a separate worker-specific branch, and only stages results/logs.

Enable Tailscale on the desktop, show the pairing key locally, and enter it on the laptop at the displayed address. The key grants worker control and must be protected. The server is authenticated and same-origin guarded, with loopback/private-tailnet binding only. This is a trusted-user research tool, not a public multi-tenant hosting service. No public port forwarding is needed. Firewall/tailnet access may need one-time external approval.

Only synthetic safe-for-work content should be published to this public repo. Private saves, real patient/student records, API credentials and explicit content are not suitable for publication.

## 9. Unity

Unity account, scheduler access and supported OnDemand/SSH access remain university prerequisites. Download the generated job script from the UI and review it in OnDemand Job Composer. Before submission, prepare the repository, Python environment, native llama-server and model shards on persistent storage, and save native-backend settings on that host. The job inherits scheduler GPU visibility and runs the same worker inside the allocation. It does not set up an unauthorized Tailscale tunnel on compute nodes.

Review GPU constraints/partitions against your actual allowed resources. The script intentionally does not assume a verified 12 GB device exists. A successful local preparation check cannot guarantee those remote resources are ready.

## Interface references

- LM Studio inventory: https://lmstudio.ai/docs/developer/rest/list
- LM Studio CLI model list: https://lmstudio.ai/docs/cli/local-models/ls
- LM Studio loading: https://lmstudio.ai/docs/cli/local-models/load
- LM Studio structured output: https://lmstudio.ai/docs/developer/openai-compat/structured-output
- Native llama.cpp server: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Unity GPU allocation: https://docs.unity.uri.edu/documentation/tools/gpus/

References describe interfaces, not proof that a user's installed version/GPU was exercised here. See TEST_REPORT.md for executed validation.
