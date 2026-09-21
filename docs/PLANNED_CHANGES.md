# Planned Changes

> Planning-only file. Keep this document current as requirements are discussed. Do **not** implement these changes until Isaac explicitly asks to apply them.

Last updated: 2026-09-20

## Guiding interaction model

The finished harness should require as little manual configuration as possible.

Expected manual actions:
1. Download model files manually.
2. If a discovered model does not yet have an assigned VRAM target, select its required VRAM from a UI dropdown, or accept the UI's recommended value.
3. Click **Preflight**.
4. Click **Run Tests**.
5. Click **Download / Export Logs** when desired.

Anything else that can be discovered reliably from the machine should be automatic. If something truly cannot be discovered, it should be requested through the UI rather than requiring hand-editing JSON.

Potential unavoidable one-time setup:
- If the LM Studio model directory cannot be auto-detected, choose the model-root folder in the UI.
- Git/GitHub authentication and Unity account/Slurm access must already exist or be configured through supported external mechanisms.
- On Unity, if model storage or the inference-server executable cannot be auto-detected, the UI/preflight may need the user to choose those paths once.

## 1. Automatic local model discovery

### Desired behavior

Remove the requirement to manually build model bindings in `worker.local.json`.

The worker should be given, or preferably auto-detect, the root folder containing LM Studio models. It should recursively inspect that folder and discover installed model artifacts automatically.

For each installed model:
- Detect GGUF files and split GGUF shards.
- Match known files against `models.json` by exact filename and, once available, file hash.
- Query LM Studio's local inventory when useful to resolve the LM Studio model key automatically.
- Detect the local path automatically.
- Detect LM Studio/backend version automatically where possible.
- Detect GPU name and VRAM automatically.
- Do not require the user to type an expected GPU name.
- Never silently substitute a different quantization.

If an installed model is not represented in `models.json`, the future UI should show it as **Unassigned / Uncatalogued**.

### VRAM assignment

`required_vram_gb` remains a property of the model variant, not a machine-specific minimum.

The UI should:
- Show every discovered model/quantization.
- Clearly mark models that do not yet have `required_vram_gb`.
- Offer a dropdown for the user to assign the intended VRAM tier.
- Calculate a recommended VRAM tier from model file size plus a conservative runtime/headroom estimate.
- Provide an **Accept Recommended VRAM** button.
- Store the accepted value in the shared model catalog so it does not need to be entered again on every machine.
- Continue to distinguish estimated requirements from measured/verified requirements.

Manual model download is acceptable and preferred for now. Automatic downloading is not required.

## 2. Test definitions become self-contained

There should not be a separate global collection of per-run test settings. A test should define how that test is executed.

The current `experiment.json` approach should eventually be removed or reduced to true harness-wide defaults only. Settings that affect experimental behavior belong in test files.

Each test file should declare:
- Unique test ID and human-readable name.
- Test type / workflow type.
- Inputs and ground truth.
- The sequence of inference steps required.
- Sampling settings needed by each step, such as temperature, seed and top-p where relevant.
- Whether a step expects free text, JSON, a boolean, a selection, a patch, etc.
- Whether steps share/cache a prefix.
- Conditional follow-up behavior.
- Scoring/evaluation rules.
- Repetition requirements if the test itself requires repetitions.
- Any context requirement or special backend capability required by that test.

Model selection remains external: eligible models are run against the test definitions.

### Do not infer workflow solely from arbitrary field presence

Prefer an explicit `test_type` or `workflow` identifier so the execution behavior is reproducible and readable. The test file then supplies all data needed by that workflow.

A generic step-based format may eventually be preferable so new workflows can be expressed without adding a special runner for every experiment.

## 3. Cached-context / multi-question tests

The harness must support experiments where one large shared input is processed once and then many small prompts are asked against that same prefix/context.

Example conceptual workflow:

1. Establish/cache a large game-state prompt.
2. Ask: `Did the time change?` with a constrained boolean response.
3. If true, ask: `What is the new time?`
4. Ask: `Did the location change?`
5. If true, ask for the new location.
6. Continue through other state categories.

The test definition should explicitly state:
- The shared/cached prefix.
- The child prompts.
- Branch conditions for follow-up prompts.
- Expected answer type for each prompt.
- Whether cache reuse is required for the test to count as a valid cache experiment.
- How cache hits/reuse are verified or reported.

Do not merely assume that keeping a conversation open proves KV/prefix-cache reuse. Controlled cache experiments need observable evidence from the backend where possible.

The harness should also support the same logical workflow with caching disabled so latency/correctness can be compared.

## 4. Preflight mode

Add a real **Preflight** operation that does everything necessary to determine whether the corresponding real run is ready, but performs no benchmark cases.

Preflight must use the same planning logic as the real run.

### Pending-work-first behavior

Before deciding what is required:
1. Read the test definitions.
2. Inspect existing result files.
3. Determine exactly which cases are already complete.
4. Build the remaining/pending job list.
5. Require only the models and resources needed for pending jobs.

Therefore, a missing model must NOT fail preflight if every test that requires that model is already complete.

### Preflight should check

Static/general checks:
- Repository/code is present and internally valid.
- Unit/smoke tests for harness code pass.
- Test JSON is valid.
- Ground truth/scoring definitions are internally valid.
- Model catalog is valid.
- Pending jobs can be constructed.
- Every model needed for pending work is discovered locally.
- All required split model shards are present.
- Model files match expected filename/hash where available.
- Backend/LM Studio/llama.cpp executable is present and compatible enough to attempt the run.
- Required Python packages are present.
- Required directories are readable/writable.
- Sufficient free disk space exists for expected result/log output.
- Git repository is in a state that will not block the real run.
- Result/log paths are writable.
- Any backend features explicitly required by pending tests are available (structured output, seed, cache control, etc.).

On the actual GPU host, preflight additionally checks:
- Actual GPU identity.
- Actual total/free VRAM.
- Driver/backend visibility.
- Pending models' `required_vram_gb` against the actual device.
- Any hardware-specific inference prerequisites.

For Unity preparation before receiving an allocation, a target GPU profile may be selected so static preflight can verify everything that does not require the actual allocated GPU. Once inside the real Slurm allocation, the full run performs preflight again with the actual GPU.

### Real-run behavior

The real **Run Tests** operation always begins by executing the same preflight automatically. If preflight fails, no benchmark tests start.

A successful preflight should give high confidence that pressing Run on that prepared machine/allocation will work.

## 5. Result completion is file-based; no tracker database

Do not use one separate tracker/database as the source of truth for completion.

Completion should be determined directly from result files on disk.

Desired behavior:
- One final result file per test case / experiment identity.
- Prefer a flat or shallow result directory rather than one directory per case.
- The result file has a top-level `status` field that can be inspected immediately.
- Scheduler checks file existence and the top-level status.
- A valid `status: "completed"` means the case is complete regardless of whether the answer was correct.
- Deleting the result file means the case becomes pending again.
- Wrong/invalid model output is still a completed experimental result.
- Infrastructure failures should not masquerade as completed benchmark results.
- Writes remain atomic: write to a temporary file, then rename.
- Corrupt files must be reported, not silently treated as complete.

Potential desired flat form:
`results/<worker-or-hardware>/<case_id>.json`

Exact folder organization is still open for discussion.

## 6. Model load health check

The current harness already performs a warm-up call after loading a model:

`Reply OK.`

If the request fails, the model is skipped.

Planned improvement:
- Make this an explicit **model-ready health check** rather than only an untimed warm-up.
- Verify the endpoint is serving the exact model requested.
- Issue a tiny deterministic prompt such as `Reply exactly READY`.
- Verify a normal stop/finish condition and a valid response.
- Keep this health check outside benchmark timing.
- Only begin real test cases after the model passes the health check.
- Record health-check failure as infrastructure/setup information, not a model-quality score.

The health check should not require the model to demonstrate benchmark competence; it only proves it is loaded and responding correctly.

## 7. No arbitrary maximum output-token limit

Remove the harness-wide `max_output_tokens: 512` limit.

Do not fail a benchmark merely because the model needed a few more tokens than an arbitrary cap.

Desired behavior:
- Omit an explicit max-output limit when the backend allows it.
- The only unavoidable ceiling is the model/backend context window and resource availability.
- Tests should instruct the model to produce concise output where appropriate, but correctness should not depend on an arbitrary generation cutoff.
- If a particular research test intentionally studies output limits, that limit belongs in that specific test definition.
- A response truncated because the true context window is exhausted should still be recorded accurately as truncated.

Context handling and memory budgeting will need to be revisited when this is implemented.

## 8. Logging

We want detailed logs, but logging must not contaminate timed measurements.

### Desired behavior

- Timed inference/pipeline sections never include log-file writes.
- Result serialization/writes occur only after the measured section is complete.
- Ordinary diagnostic logs are buffered in memory during a model/test batch.
- Flush buffered logs at safe untimed boundaries, such as after a model finishes, after a run finishes, or on explicit shutdown.
- Critical/fatal failures may require an emergency flush.
- Keep logs in a separate top-level `logs/` directory rather than creating one folder per result.
- Provide a future UI button to **Download / Export All Logs**.
- Logs should include model-load activity, health checks, backend messages, preflight details, retries, errors and run lifecycle events.
- Raw prompts/responses and per-case evidence may remain inside the result JSON rather than being duplicated into text logs unless useful.

Immediate per-case result writes are still desirable for crash-safe resume, provided the write occurs outside the measured timing interval.

## 9. Current result storage (before redesign)

As of the current implementation:

- Results are stored under:
  `.local/results/cases/<case_id>/attempt-0001.json`
- Additional infrastructure attempts become `attempt-0002.json`, etc.
- The top level is currently an envelope:
  `{"record": {...}, "sha256": "..."}`
- The `status` field is currently inside `record`, not at the file's top level.
- `status` is either `completed` or `error`.
- `completed` includes correct, incorrect and invalid model answers.
- The record includes case/model/pipeline identity, fixture/model hashes, source commit, environment, load metadata, raw call data, prompts, model responses, timing and score.
- Completion is already derived from result files rather than a separate completion tracker.
- The current structure is more nested than desired and should be redesigned as described above.

There is currently no real GPU result file committed to `main`. The prior smoke outputs were local simulated artifacts and intentionally were not published as real experiment results.

## 10. Test/model assignment and UI expectations

Future UI behavior:
- Scan/discover installed models automatically.
- Show catalogued and uncatalogued installed models.
- Show whether each installed model has an assigned `required_vram_gb`.
- Recommend VRAM based on file size plus conservative overhead.
- Dropdown to select target VRAM.
- One-click accept recommended VRAM.
- Show which tests are pending/complete for each model.
- Button: **Preflight**.
- Button: **Run Tests**.
- Button: **Download / Export Logs**.
- No requirement to edit `worker.local.json`, model keys or file paths manually.

The UI can be built later, but the underlying APIs/configuration should be designed so the UI is only a front end and does not contain benchmark logic.

## 11. GitHub synchronization

GitHub synchronization remains useful for code, test definitions and results, but global multi-worker scheduling is not a priority.

Assumption for now:
- Isaac will not intentionally run multiple workers against the same pending workload at the same time.
- Do not spend complexity on distributed claims/locks yet.
- Resume behavior should primarily be based on local/result-file existence and Git-synced result files.

## 12. Preflight auto-fix UX

Preflight should be designed as a guided repair loop rather than only an error report.

For every detected problem that the harness can safely repair, show a button whose text states the exact repair, for example:
- **Download Qwen3.5-9B Q4_K_M**
- **Create Results Folder**
- **Install Missing Python Packages**
- **Start LM Studio Server**
- **Pull Latest Benchmark Files**
- **Accept Recommended 8 GB VRAM Tier**

Ideal interaction: Isaac can run Preflight, press the offered fix, rerun/continue Preflight, and repeat until the entire preflight passes.

Rules:
- Never label a problem auto-fixable unless the repair can be performed deterministically and verified afterward.
- The button text must describe the specific action, not merely say **Fix**.
- Do not silently perform large downloads, destructive Git operations, model substitutions, driver changes, admin-level system changes, or anything that may affect unrelated software.
- After every fix, verify that the issue is actually resolved.
- Preflight should distinguish: PASS, FIXABLE, NEEDS USER INPUT, and BLOCKED/UNSUPPORTED.
- The real Run operation still performs preflight automatically before starting benchmark cases.

## 13. No user-visible context-limit setting

There should be no context-length control in the normal UI and no per-run context setting that Isaac must choose.

However, inference backends always have a finite context window and some backends reserve KV-cache memory based on the configured context size. Therefore the harness still needs an INTERNAL automatic context-sizing policy.

Desired behavior:
- Determine the model's supported context window automatically.
- Determine the pending test's prompt requirements automatically.
- Choose a sufficient context allocation automatically rather than asking the user.
- Do not impose an arbitrary output-token cap.
- Do not silently truncate prompts or outputs.
- If a test cannot fit within the model's true context capability or available memory, preflight reports that explicitly.
- Context allocation and any context-related VRAM effects are recorded as provenance, even though the user does not configure them.
- Exact automatic sizing policy still needs to be finalized before implementation.

## 14. Remote UI control over Tailscale

All normal desktop-worker controls should be usable from the laptop without Remote Desktop.

Preferred direction to discuss before implementation:
- Run the benchmark control service on the GPU desktop.
- Expose its UI/API only through the private Tailscale network, not the public Internet.
- From the laptop, open/control the desktop worker through that private address.
- The same controls available locally on the desktop should be available remotely: model discovery/assignment, Preflight, dynamic fixes, Run/Pause/Stop, status, results/log download and health information.
- Benchmark inference still runs locally on the GPU host over loopback; remote UI traffic must never be included in benchmark timing.
- Authentication/binding strategy must be decided before implementation (for example binding to the Tailscale interface or using Tailscale Serve).

## 15. LM Studio model-root discovery

Do NOT blindly scan conventional/default LM Studio folders.

The harness should determine LM Studio's CURRENT configured model storage location from LM Studio's settings/configuration or supported CLI/API.

Desired behavior:
1. Query the active LM Studio model location.
2. If it exists and contains models, use it automatically.
3. If the configured folder exists but is empty, ask the user through the UI whether this is the intended folder rather than blindly accepting it.
4. If the current configured folder cannot be determined, ask the user to select it through the UI.
5. Remember/verify the choice rather than requiring repeated manual entry.
6. Model discovery then scans that current configured root and/or LM Studio inventory.

## 16. Changes explicitly NOT to implement yet

Until Isaac asks to apply the planned changes:
- Do not redesign result layout.
- Do not remove `experiment.json`.
- Do not remove the max-output setting.
- Do not change model discovery/configuration.
- Do not add preflight mode.
- Do not change logging.
- Do not add cached-context workflows.
- Do not build the GUI.
- Do not modify current runner behavior based on this document.

Only keep this planning document updated as requirements evolve.


## 17. Hardware-tier scheduling decision

Do NOT run every smaller model on every larger GPU.

Use discrete VRAM tiers and allow opportunistic testing approximately one tier above the model's assigned requirement.

Current intended behavior:
- Models assigned to **8 GB** should run on 8 GB hardware and may also be run on nearby 11/12 GB hardware when available.
- Treat 11 GB and 12 GB GPUs as effectively the same comparison tier for models whose assigned requirement is 8 GB or lower.
- A model assigned to **12 GB** must wait for hardware that actually provides at least 12 GB; an 11 GB GPU does NOT satisfy a 12 GB requirement.
- Higher tiers should follow the same principle: test on the assigned tier and, where useful, the next nearby tier up rather than propagating the test indefinitely to 24/40/80 GB hardware.
- Do not spend expensive 80 GB accelerator time rerunning small 8 GB models unless a specific experiment explicitly asks for that comparison.
- Exact tier mapping (8, 12, 16, 24, 32, 40, 80, etc.) and what counts as the immediately adjacent tier should be represented explicitly in scheduler policy rather than inferred from arbitrary percentages.
- The UI should show why a model is scheduled on a given GPU: **assigned tier** or **one-tier-up comparison**.

## 18. Preflight fix interaction is always manual

Preflight may detect and offer a specific repair action, but it must NEVER execute a repair automatically.

Desired flow:
1. Run Preflight.
2. Show issues and their state.
3. For a safely fixable issue, show a button whose text describes the exact action.
4. Isaac manually clicks the button.
5. Perform only that one repair.
6. Verify the repair.
7. Rerun/continue Preflight and present the next issue.

There is no automatic chain of fixes and no silent remediation.

