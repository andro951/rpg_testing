# Using the native workbench

This guide replaces earlier LM Studio instructions. The graphical workbench is `workbench/`, started by **Start Workbench.vbs**. **Start Demo.vbs** is isolated simulated operation. Existing results from older implementations remain inspectable but may have different experiment identities.

## Storage and first launch

The application starts without a model path. It never chooses a weights directory based on a conventional home/AppData/C-drive location. On the GPU computer, **Choose models folder…** opens the operating system’s normal folder picker; merely opening or cancelling it creates nothing. The selected path is saved promptly, then a separate background scan discovers GGUFs. You can navigate to **Installed models** during that scan; the page shows `SCANNING` instead of blocking on the settings lock. When controlling remotely through Tailscale, the native picker would appear on the GPU host, so enter the known host path in Worker setup instead.

That folder can already contain downloaded GGUFs. The scanner recursively inspects metadata and split-file groups without moving them. It ignores image projectors for these text-only experiments. If no models are found, a dialog asks whether the empty folder is intentional. Confirm it, or choose a different folder. Confirmation is tied to the normalized selected path; it cannot authorize another directory.

A successful **Rescan / preflight** or normal preflight reconciles the machine-local model catalog to the GGUF files actually present in the configured folder. Manually deleted models are removed from active model assignments and the artifact-identity cache, but their historical benchmark result files remain available for analysis. Incomplete split models are retained while any shard remains so missing shards can still be repaired. A moved/disconnected drive or unreadable folder is never interpreted as an empty scan and must be fixed before pending model work can run. If old settings came from the LM Studio version, the new model-folder policy asks for fresh consent rather than silently inheriting the old path.

Only models and partial downloads use this directory. Repository-relative storage is:

```text
models.json                         shared model catalog, not model bytes
test_specs/                         experiment definitions
examples/test_specs/                optional workflow examples
.local/workbench/settings.json      automatically created operational settings
.local/workbench/results/<model>/<case>.json
.local/workbench/logs/<timestamp>-<id>.json
.local/runtime/                     explicitly installed native builds
.local/runtime-cache/               native cache environment
.local/demo/                        simulated data, kept separate
.venv-workbench/                     private Python environment when installed
```

No manual JSON settings file is necessary. Python and Git must already be available; the launcher can ask to install the pinned Python requirements into the private project environment. It does not install drivers or request university access.

## Finding and installing models

Open **Find models**. Search by model name; repository results show publisher/repository, download/like metadata and license information when available. An exact `publisher/repository` can be opened directly. The app requests GGUF-compatible results, then fetches the available files at an immutable revision.

**View quantizations** lists format, decimal GB, binary GiB, shard count, and a heuristic recommendation. K_M receives a preference where useful, but recommendations do not claim measured superiority. The suggested set is deliberately small and size-spaced; it does not recommend shrinking a tiny model merely to fill a list of quants.

Select individual variants or **Select recommended variants**. Choose the VRAM assignment, then click **Download selected variants** and approve the destination. Assignment is part of model metadata, not an ad hoc inference setting. No network download happens just because you search, open a result or select a checkbox.

Downloads stream directly to the selected root, normally under publisher/repository/revision. All parts of a split GGUF are downloaded together. A partial file remains beside its eventual destination; selecting the same variant resumes it when the server supports byte ranges. Range responses, expected sizes, publisher SHA-256 when available, and GGUF metadata are checked. Completed files are renamed into place only after verification. Existing conflicting files are not silently replaced. HTTPS redirects cannot downgrade to HTTP; authorization is removed when redirecting to another host.

A Hugging Face read token can be saved through Worker setup for gated/private models. The workbench does not accept a model's access agreement for you, bypass a license gate, or obtain account permission. Resolve that through the publisher when necessary. Credentials stay out of exported evidence and Git staging.

Manual downloading remains valid. Put files under the selected root, rescan, and assign uncatalogued variants in **Installed models**. Exact paths and model hashes are discovered automatically; no LM Studio model key is required.

## VRAM assignments and scheduling

Each variant uses `required_vram_gb`. This is an assigned device tier, not a measured claim that every context/workflow will fit. Recommendations use file size and headroom; load-time results supply actual evidence.

Assigned tiers are 8, 12, 16, 24, 32, 40, 48 and 80 GiB. A model normally runs at its own tier and the next tier. Eight-GiB variants can additionally use 11-GiB hardware, but an 11-GiB device never satisfies a 12-GiB assignment. Small models are not automatically scheduled on every larger accelerator. Physical GPU identity and runtime version remain part of provenance.

## Native runtime

Open **Native runtime → Find official runtime releases**. The list filters official llama.cpp GPU archives for the host platform and architecture, with CUDA/Vulkan build notes. Choose a build and explicitly install it, or locate an existing executable using the host browser.

Downloads and extraction stay under `.local/runtime/`. Checks cover release origin, publisher digest when available, traversal/unsafe archive entries, extraction budgets, exactly one server executable, and an installation manifest with file hashes. A runtime is not selected until its required command controls can be inspected. Reusing an installed build rechecks its manifest. No driver or system-wide CUDA installation is performed.

Keep the runtime version stable for a benchmark campaign. A newer build can change kernels, templates, cache reporting and tokenization. Compatibility with the particular GPU still needs a real load; choosing an archive with a familiar name is not proof that it supports an older card.

## Preflight versus Run

**Run preflight** checks definitions, harness tests, pending result identities, discovered files/shards, source state, native executable controls, device visibility, local port availability and output paths. It does not generate benchmark answers. It reports the exact remaining model/case plan.

Dependencies are evaluated after completed work is subtracted. Deleting a model whose entire applicable workload is already complete does not cause a missing-model error. A memory-skipped primary case whose recovery is unfinished still needs the model to finish recovery.

Specific repair buttons require an individual click. Examples include choosing the model folder, confirming an empty folder, downloading a missing catalogued model/shard, selecting/installing a native runtime, assigning VRAM, saving test/catalog edits, and deleting corrupt evidence. Drivers, credentials, unsupported devices, disk exhaustion or unrelated source conflicts are not silently repaired.

**Run remaining tests** reuses preflight, then runs unattended. If setup is incomplete, it stops before any benchmark; it does not quietly change your configuration. Once execution begins, a model failure is never a confirmation popup.

If source sync is enabled and the pull changes code, the supervisor restarts the process and resumes the already-requested Run. Restart intent expires and is consumed once. The chain is bounded; repeated continuous source changes stop safely rather than looping forever. Ordinary completed-case state is still read directly from result files.

## Unattended two-pass policy

1. **Primary:** load each pending model with all GPU layers requested, fitting disabled, no requested CPU MoE/FFN placement, and generous automatic context. Parse backend placement, verify the model identity, run a tiny liveness probe, then execute its cases.
2. **Skip automatically:** CPU model-layer/KV placement or GPU allocation failure records a qualification failure, unloads the owned model and advances immediately. Unknown placement is not accepted as full GPU. Unrelated incompatibilities are recorded without wasting recovery attempts on them.
3. **Recovery:** after primary models finish, sort deferred memory-related models by total model-file size. Try full GPU once again. If still unsuitable, try a finite sequence of reduced GPU-layer placements while retaining at least some GPU work. No all-CPU fallback is silently introduced.
4. **Record separately:** successful hybrid runs use `execution_class: cpu_offloaded`, a distinct case identity and false `valid_for_full_gpu_comparison`. CPU-layer counts, context and attempts are retained. Hybrid results never replace or get averaged into normal full-GPU data.

Model-load attempts have a 600-second (10-minute) operational watchdog. A full-GPU workflow has 600 seconds; a hybrid workflow has 300 seconds, including its multi-call steps. Four hybrid layer trials and two context expansions bound recovery. These are explicit time/resource safeguards, not output-token truncation. A workload that legitimately needs longer may hit this policy; its record says so rather than scoring a partial answer as a normal semantic failure.

Stop/pause controls are deliberate user requests. **Pause after case** preserves an active case then waits. **Stop after model** completes the current model and prevents entry into later recovery. **Stop now** cancels active I/O and terminates only the owned model process. Abrupt process/machine termination can interrupt a write; atomic result replacement avoids falsely completed files.

## Context and cache experiments

There are no run-level context/output settings. Automatic planning uses the whole enabled suite, not only the cases left after resume. It includes source, shared prefix, instructions, step prompts and bounded loop structure, then adds generous continuation room and rounds upward. The initial floor is 16K tokens when the native window permits it.

This is an estimate, not a proof of future output length. Native template/tokenization checks actual input before generation. Context exhaustion preserves the attempt and retries the case from scratch with a larger permitted bucket; it does not silently trim state, instructions or the output. A larger allocation may fail GPU fit and be deferred for recovery. Comparisons retain their actual context configuration.

Cache-on/off examples use one large common prefix with small subsequent questions and conditional follow-ups. The native adapter erases the slot, requests reuse or fresh processing, and retains counters. A cache-on measurement requires a cold first call and observed reuse later; a cache-off measurement requires zero reported reused tokens. Missing counters or unexpected behavior invalidate the cache measurement, not fabricate a speedup.

## Results, logs and analysis

Each case has a JSON file whose first field is `status`. `completed` includes correct and incorrect model answers. `skipped` records execution qualification and whether recovery remains relevant. `error` and `aborted` retain interrupted attempt evidence. The scheduler reads these files; there is no central completion tracker.

Deleting a result makes its identity pending again. Deleting only a hybrid result resumes the recovery portion while retaining the primary fit failure. Later successful full-GPU recovery keeps earlier skipped/error attempts in the same primary result. Every result has a checksum; corrupt files are exposed for inspection and manual removal rather than trusted.

A result includes model and artifact hashes, the source/test definition, pipeline steps, request settings, raw text/reasoning/stream evidence, status/score, timings, context, placement, runtime/source provenance and telemetry where available. Ground truth is present in result evidence but is never supplied to the model prompt.

**Comparison** keeps distinct artifact/test/software/context/execution-class groups apart. It reports observed descriptive accuracy and timing, not unsupported statistical certainty. Skip counts and infrastructure failures are retained. Export contains raw result JSON, logs, `summary.json` and `summary.csv`. Simulated data remains explicitly labelled.

Application diagnostics are buffered while a workflow is timed. Writes, result serialization and Git publication occur afterward. NVML samples whole-device used memory in a background thread without shell commands or disk logging. It is a sampled peak with possible missed brief peaks, display/other-process usage included. Sampling itself has overhead; its policy is recorded. It does not establish per-process allocation or physical residency independently.

## Placement evidence: what it does and does not prove

A backend report such as “offloaded 33/33 layers to GPU” is used as evidence for model-layer placement. CPU KV placement is flagged. A CPU-mapped file, CUDA-host buffer or nonzero CPU utilization alone is not treated as CPU model-layer computation.

The UI shows these reports live once available. They are **backend-reported placement**, not independent proof that a Windows driver never pages VRAM, that every tiny host operation is GPU-only, or that no other program is competing for the device. Unknown reports are rejected for full-GPU qualification. The watchdog limits a pathological run without inventing an offload diagnosis from CPU utilization.

## Tailscale and Unity

Enable private Tailscale access on the desktop, display its pairing key locally, and open the displayed address from the laptop. Native folder/file pickers open on the GPU host when the UI is used locally. A remote laptop should enter known GPU-host paths in Worker setup; browser file pickers are not used because they would select laptop files. Pairing/Host/Origin checks and loopback/private-interface binding protect the control API; no arbitrary-shell endpoint or public Funnel is provided. The desktop must be awake and the actual tailnet/firewall route must allow access.

Unity uses its supported allocation workflow. Prepare persistent model storage, the repo, Python and compatible native runtime there, configure the models path, and download the generated Slurm script. It requests one GPU and uses the same batch controller inside the allocation. Confirm permitted partition/device constraints yourself; examples are not reservations or authorization.

The script asks for an advance wall-time signal and forwards it through the launcher to stop the worker and publish/save outside timing. Actual scheduler behavior, storage paths and GPU compatibility remain environment checks. The laptop preparation report cannot certify an unconfigured Unity machine. No interactive dialog is needed while the allocated worker is processing models.

## Validation boundary

See TEST_REPORT.md for the exact tested commit and CI jobs. Unit, local HTTP/subprocess and real-browser tests validate software behavior using small deterministic fixtures. No actual user GPU, large downloaded model, public runtime binary, real Tailscale route or Unity allocation was executed during development. Those are still hardware/environment smoke checks, not unimplemented scheduler/UI plumbing.
