# RPG Testing Workbench

A browser-controlled benchmark for **original JSON state + new information → state update**. The worker and model run on the GPU computer. A laptop can control the worker through Tailscale; inference remains on the GPU host.

## Start without a terminal

Update the `main` branch using GitHub Desktop, open the repository folder, then double-click:

- **`Start Workbench.vbs`** — actual worker and browser controls.
- **`Start Demo.vbs`** — the same interface with an explicitly simulated model. No GPU or weights are required; this checks the interface, not model quality.

Python 3.10+ must already be installed. The graphical bootstrap asks permission before creating a private Python environment and installing missing requirements. LM Studio, its compatible runtime, and downloaded models remain prerequisites for actual inference. Git is needed for repository self-tests and source/result synchronization.

On a fresh clone, the demo has two tests × four variants = **eight cases**. Click **Run preflight**, then **Run remaining tests**. Run again to confirm completed cases are skipped. Inspect a result, delete it, and run again to see exactly that case scheduled.

## Normal workflow

Open **Models** and run a scan/preflight. The worker reads recognized LM Studio settings for the current model folder rather than guessing a default weights directory. An unknown or empty folder is surfaced through the UI. New GGUF variants get a VRAM dropdown and an **Accept recommended … GB** button. No manual model-key/path bindings are required.

Click **Run preflight**. Each repairable issue has a specific action, such as **Start LM Studio server**, **Download …**, or **Save and push catalog and test edits**. Every repair needs approval. Checks do not perform a chain of fixes silently.

Click **Run remaining tests**. The worker rechecks readiness, groups unfinished cases by model, loads and probes that model, runs its cases, saves each result, then advances. Controls include **Pause after case**, **Resume**, **Stop after model**, and **Stop now**.

Use **Results** to inspect raw evidence or delete a result for rerunning. **Download all logs & results** exports result JSON, logs, and summary CSV/JSON. Disk-heavy inspection/export waits until the active operation finishes or stops.

## Included capabilities

The generic workflow interpreter supports direct standard JSON Patch and semantic patches; analysis followed by patch generation; typed/JSON-schema output; conditional follow-up questions; shared-prefix cache-on/off comparisons; bounded verification/repair loops; and narration followed by state updating with the same loaded model.

All experimental settings live in `test_specs/*.json`. The UI contains a validating editor and import buttons for examples under `examples/test_specs/`. There are no temperature/seed/context/output controls for an ad hoc run. `models.json` remains a models-only catalog with `required_vram_gb`.

Scheduling uses the assigned hardware tier plus one adjacent tier, not every larger GPU. An 11 GB GPU is an opportunistic comparison for 8 GB models and never satisfies a 12 GB assignment. VRAM recommendations are estimates. Context is allocated automatically and recorded. No arbitrary 512-token response cap is imposed.

**Controlled cache tests require native llama.cpp.** This LM Studio adapter does not claim controllable, verifiable cache reuse; preflight blocks those variants there. Ordinary LM Studio workflows can still make multiple calls and request constrained JSON. Native cache experiments retain backend reuse evidence; absent evidence invalidates the cache measurement.

## Laptop control

Start the workbench on the desktop. In **Worker setup**, click **Enable private Tailscale access**, then **Show pairing key on this host**. Open the displayed address on the laptop and enter that key. Normal controls, including the folder browser, operate on the desktop.

The desktop must stay awake with the worker running. The service binds only to loopback and the explicitly enabled Tailscale address, uses a pairing key and same-origin checks, and offers no arbitrary-command endpoint. Do not add public port forwarding. Firewall and tailnet permissions must permit the connection.

## Unity

Use **Prepare for a different GPU** and download the generated Unity job script. Submit it through supported Unity OnDemand Job Composer after preparing the repository, Python environment, native `llama-server`, and model files on Unity storage. It runs the same controller inside a Slurm allocation and refuses GPU batch operation on a login node.

A preparation check on the laptop cannot certify another machine's filesystem, drivers, authorization or future GPU. The allocated worker rechecks readiness. Review partition/constraint examples against the resources actually available to your account.

## Evidence and synchronization

Results are individual checksummed files with `status` first:

```text
.local/workbench/results/<model-id>/<case-id>.json
.local/workbench/logs/<timestamp>-<id>.json
```

Completed incorrect/invalid answers remain completed experiments. Errors and aborted cases remain pending. Completion comes from files, not a tracker database. Deleting a result schedules it again. Artifact fingerprint metadata is cached separately, not used as a completion tracker.

Source is pulled conservatively before real runs when enabled. Changed source requires **Restart workbench** so the new code runs in a fresh process. Optional publication sends only result/log directories to a separate worker branch, outside measured workflows. No force-reset, automatic stash or broad `git add .` occurs.

This repository is public. **Only synthetic safe-for-work fixtures and outputs belong here.** Never publish API credentials, private saves, real patient/student records, explicit content or model weights.

## Validation

The full committed suite passed **179 tests on Windows and 179 on Linux**, plus a real Chromium browser workflow in GitHub Actions. See [TEST_REPORT](docs/TEST_REPORT.md) for the tested commit and evidence, [WORKBENCH_GUIDE](docs/WORKBENCH_GUIDE.md) for usage, and [PLANNED_CHANGES](docs/PLANNED_CHANGES.md) for requirement coverage.

No real GPU model inference was available during this implementation. Actual GTX 1080/LM Studio loading, real Tailscale connectivity, and Unity allocation must still be tested on those systems. Peak VRAM is explicitly unavailable and complete GPU residency is unverified. Simulated results are never model-quality or throughput evidence.

## Legacy prototype

`run_worker.py`, `rpgbench/`, `fixtures/` and `experiment.json` remain for historical reproduction. **The new browser workbench does not use `worker.local.json` or `experiment.json`.** Use the new launchers and `test_specs/`.
