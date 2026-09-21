# Requirement ledger — native workbench

Status updated 2026-09-21. This records implemented behavior after the authorized native-only overhaul. The earlier planning-only hold is no longer active. Research roadmap documents remain separate and unchanged by this implementation.

## Implemented in the active application

- Native llama.cpp only; no active LM Studio runtime, model keys or settings-directory lookup. Historical CLI files remain archived for reproduction, not used by the GUI.
- Models folder initially unset, explicit host-side selection, scan pre-existing GGUFs in place, empty-folder confirmation, normalized path handling. Only models/partials use that path; tests/results/logs/runtime stay with the repository.
- In-app Hugging Face GGUF search, immutable revision details, quantization/shard grouping, file sizes, heuristic recommendations, multi-selection, explicit approved downloads, range resume, hashes and safe file installation. Manual model download remains supported.
- Explicit official native-runtime release browser/installation, platform/architecture filtering, archive validation and installation manifest. No automatic driver installation or hidden runtime upgrades.
- Models-only JSON catalog with required_vram_gb; UI assignments and estimates; assigned/adjacent tier policy with the 11/12 asymmetry.
- Preflight shared with execution, pending cases calculated before model requirements, completed models need no weight files, corrupt results surfaced, manual issue-specific repair actions. Native help/device/API readiness and real load qualification remain separate stages.
- Unattended primary full-GPU pass; automatic record/unload/skip on placement or memory failure; smallest-first deferred recovery; one full-GPU retry then bounded hybrid layer trials. No execution-time confirmation popups.
- Separate full_gpu and cpu_offloaded records and analysis groups; failed qualification is not scored as a wrong semantic answer. Unknown placement is not trusted. CPU utilization/CPU-mapped files alone are not offload detection.
- Generous automatic finite context planning, no UI/test output or context cap, native token/template guard, bounded context-expansion/reload retry with earlier attempts preserved.
- Owned native-process liveness, model identity checks, streaming evidence, time watchdogs, process cleanup, cancellation and user-requested pause/stop controls.
- NVML sampling connected to controller, results and live UI, with explicit sampled-total-device scope and unavailable-state handling.
- Self-contained step tests, per-step settings/types, conditional questions, explicit bounded loops, direct/semantic patches, analyze-then-patch, cache evidence, and imported repair/narrative examples.
- Status-first atomic/checksummed result files, no completion tracker, terminal skips and interrupted attempts, delete/rerun and recovery-only resume. Raw evidence remains inspectable/exportable even when another result is corrupt.
- Browser-first setup, private Tailscale control, host folder/executable browsing, test JSON editing, result inspection/deletion, comparison and ZIP/CSV/JSON export.
- Buffered logs and Git writes outside workflow timing; credential redaction; narrow Git publication. Source-update supervisor restarts and resumes an explicitly requested Run without requiring a new click, bounded against repeated updates.
- Unity job generation, one-GPU allocation guard, documented constraint examples, advance scheduler signal forwarding and batch cleanup. No promise of bypassing university setup/access.

## Validation and remaining boundaries

TEST_REPORT.md identifies the actual test run and counts. Real-browser tests exercise unchanged UI code and authenticated endpoints; Hub assets and inference are fixture-backed for repeatability. Real model/GPU performance has not been measured here.

Actual GTX 1080 driver/runtime compatibility, live model downloads and license gates, your Tailscale/firewall route, and an actual Unity allocation must be checked on their target systems. These are environment-validation requirements, not a claim that the controls or scheduler are unfinished.

Layer-placement verification is based on backend diagnostics. NVML is sampled device-wide usage. Neither independently proves Windows residency/page-fault behavior or exact model-only VRAM. The runtime can differ by release, architecture and drivers; missing cache evidence is marked unverified rather than invented.

Watchdog/context/recovery policies are finite and recorded. Runs do not silently modify test prompts, substitute quantizations, reduce context to a hidden minimum, or reroll incorrect answers. Very long valid workflows may exceed the operational safety deadlines; such events retain their actual reason and partial evidence.

The default three tests and optional examples are infrastructure/research starting points. External model-as-judge orchestration, a global multi-worker claim service, full remote Unity account provisioning and independent OS paging instrumentation are not included in this agreed native/local implementation pass.
