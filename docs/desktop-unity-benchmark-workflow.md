# Desktop and Unity benchmark workflow

October 16, 2026: Isaac approved the following defaults. Derive future scope from
its reviewed prompt manifest; the current frozen suite contains 21 tests,
62 prompt configurations and 3 independent repetitions:186 cases per cohort.

## Desktop model batches include Perchance

Include Perchance once for the requested prompt scope whenever running a desktop
model benchmark batch on the eligible actual 8 GB worker. This includes targeted
local and all-local batches; do not silently exclude it because of those scope
labels. This October 16 instruction supersedes the earlier automatic-phase
exclusion for targeted/all-local selections. Larger tiers and demo inference
remain excluded. Do not repeat the same provider condition separately for each
native model. Use the capability-aware plan and retain each configured ordinary
repetition as an independent service trial. This does not authorize extra trials.

At the start of preflight, check eligible pending provider work, the existing
Python dependency and local browser launch before the other readiness checks.
If setup is missing or broken, offer the required run-scoped installation Yes/No
choice; never answer it automatically. A verified existing installation can be
reused without installation. Preserve readiness failures and recovery evidence.
Honor site login/verification and service restrictions without bypasses.

The normal combined sequence keeps Perchance after native recovery. An explicitly
authorized concurrent remote cohort may use isolated result/lock storage, provided
it retains ordinary ownership and runtime failure safeguards. Never gate or
automatically pause a batch because of keyboard/mouse activity, CPU utilization,
GPU utilization or general desktop use. Honor explicit user Stop/Pause requests.
If reliable per-process evidence shows another workload actively competing on
the same GPU, show the nonblocking deduplicated warning "you're interfering with
the test"; do not pause automatically. Process presence, allocated memory or
general activity alone does not establish contention. State measurement limits
when same-GPU per-process activity cannot be verified. Preserve the normal
browser profile and unrelated user processes. Record ownership before cleaning up
any browser created by the cohort. Native loading has no elapsed deadline;
benchmark trials use 120 seconds after readiness, and Perchance uses 300 seconds.

Perchance is remote service inference;8GB is scheduling eligibility, not measured
local GPU execution. Preserve exact messages and effective role-label serialization.
Forward repetition-derived seeds experimentally and record their effects as
unverified; unsupported/applied defaults and unavailable measurements remain
unknown/null. Keep errors and timeouts distinct from scored responses. A transport
error with no observed response is not a scored independent trial. Preserve every
attempt and never rerun completed wrong answers or terminal timeouts to improve
accuracy. Apply [the provider capability policy](perchance-capability-policy.md).

## Future Unity batches use one job per model

Submit one independent job per requested model, with one allocated GPU per job.
Allow those jobs to run in parallel when resources and account/QoS limits permit;
parallel start is not guaranteed. Keep an already-running approved job intact.
Use an isolated working/result root, settings, cache, logs, review lock, status,
collector and audit for each job. Use unique per-job localhost inference ports
because different single-GPU jobs can share the same physical host.

Share immutable, verified model files, pinned runtime and frozen source inputs;
avoid duplicate downloads or redundant large-file hashing. Retain the requested
VRAM class, full GPU placement, context, KV precision, sampling/seeds, chat template,
evaluator, fixture/oracle and runtime commit. Record actual node/GPU/driver/compiler
provenance. Never claim that the same weights and greedy sampling guarantee
identical output across different compiled runtimes or GPUs.

The reviewed October 16 four-model comparison used physical 12 GB GTX TITAN X
Maxwell (sm52) workers with the recorded Haswell feature constraints, full GPU
placement, 32K context, f16 KV and one runtime slot. Do not silently substitute a
different memory tier or runtime. The largest measured loading/generation device
peak was 11.149 GiB, within the 11.5 GiB ceiling and 0.5 GiB minimum headroom.

Use a QoS that permits simultaneous submissions. The October 16 account inspection
found Short MaxSubmitPU=1, which prevents four independent concurrent submissions.
Normal allowed MaxJobsPU=1000 and MaxSubmitPU=2000, with lower configured priority
than Short; the shared account GPU limit was 64. Recheck current policy before
future submission. Arrays also count against submission/job limits and do not
bypass them. Account limits, fair share and available GPUs can still queue jobs.

Each collector seals and audits its own model's evidence. Resume only genuinely
unfinished cases; keep completed failures and terminal timeouts. Report a finished
audited cohort promptly rather than waiting for its siblings. Combine summaries
only after verifying the exact frozen requests and retained raw evidence.

### Existing launcher limitation

October 17 implementation update: the supported OPRO path now has durable normal
promotion and configured-model coverage orchestration, a single-model Unity worker,
unique saved inference ports, submission reconciliation, and UI/API status/resume.
Targeted desktop scopes now include Perchance. See
[automatic full coverage](prompt-optimization/full-model-coverage.md) for worker
registration, exact evidence checks and current validation limits. The legacy
launcher below remains available; frozen already-running snapshots retain their
original code and existing job IDs.

This is the approved workflow standard. This documentation change does not add
new launcher flags or change runtime code. The existing legacy Unity launcher
can still launch a whole matrix, and the current NativeBackend uses a fixed 1235
port. Existing targeted/all-local controller selections also still exclude the
automatic Perchance phase: explicitly schedule the provider cohort separately
until a reviewed and tested controller change implements the new desktop default.
Do not claim that this documentation changed the application's automatic behavior.
Before the next parallel Unity batch, use or implement a reviewed single-
model runner with isolated roots and unique ports; do not invoke the legacy
whole-matrix script once per model or silently share its result/cache/lock files.
Any runtime-code change needs its required tests and operational-compatibility
review. Do not change experimental identity or declare arbitrary changes equivalent.

## Current Windows contention companion

The completed desktop batch used a task-local, read-only NVML companion monitor.
It never controlled inference or paused the scheduler. Per-process GPU samples
were verified on the GTX 1080 under WDDM, although nvidia-smi pmon was unsupported.

A warning requires fresh positive benchmark SM activity, another live process
with at least 10 percent SM activity, and at least 90 percent total GPU utilization
for three consecutive two-second polls. The GPU is selected by its recorded UUID.
Unavailable metrics, stale samples, CPU use, memory allocation and process
presence cannot trigger a warning. A nonmodal, nonactivating popup displays
"you're interfering with the test", expires after 15 seconds, and has a global
ten-minute cooldown. The benchmark continues unchanged.

Ten decision tests passed without displaying a fabricated warning. No qualifying
real contention occurred during the monitored remainder, so the popup renderer
was not visually validated. Detection is deliberately conservative: it does not
measure causal slowdown and can miss memory-bandwidth pressure or a completely
starved benchmark. This companion is separate from the application GUI; do not
claim that the installed GUI automatically launches it or that every platform
provides these process-level measurements.
