# Automatic full model coverage after OPRO

Successful built-in OPRO sessions now call the supported promotion/coverage path.
Only a `perfect` session with a fully evaluated 100% candidate whose attempt is
complete and not rejected can enter promotion. The structural review validates
the template, every presentation binding, and equality with the actual validated
messages. It preserves fixtures, expected states, operation contracts, controls,
repetitions and evaluator. Unsupported multi-step/legacy promotion is blocked.

The durable transaction is saved under `coverage_results/<id>/state.json` before
normal definitions change. It retains the before/after definitions and accepted
candidate recipe. The normal builder reads `test_builder/active_opro_promotions.json`;
`python -m test_builder.automatic_promotion` is not a CLI. Python callers can use
`test_builder.automatic_promotion.rebuild(root)` to replay the saved recipes.
An interrupted promotion resumes only if every destination is still either its
saved before or after definition. Conflicts block without overwriting them.

Full coverage freezes all enabled desktop catalog models and includes Perchance
once on an eligible actual 8 GB desktop. Targeted local and all-local batches now
include the same provider scope. Provider setup is checked first; installation
still requires the run-scoped Yes/No choice. No leaves Perchance pending. Larger
tiers and demo inference exclude it. Provider capability grouping, independent
repetitions, the 300-second deadline, terminal failures/timeouts and raw requests
are unchanged. This change introduces no new OPRO round.

Configured Unity models live in the machine-local file
`.local/workbench/coverage-workers.json`, as an object with a `unity` array.
Each entry needs `model_id`, the full pinned `model` catalog object, `model_path`,
`runtime_path`, `python`, `ssh` (an argv array including destination),
`remote_base`, `constraint`, `qos`, and a distinct `inference_port`.
`seed_results_roots` may name retained prior remote result roots. These are
candidate evidence, not automatic completions: the ordinary planner requires exact
workflow, artifact, target, experiment and repetition compatibility. No credentials
or machine paths should be committed. No model/runtime download or service install
is performed by this feature.

Each Unity model receives one isolated source/settings/result root and one GPU
job. A remote exclusive submission intent and receipt survive lost acknowledgements.
Resume adopts exactly one job matching its exact Slurm comment; absent or multiple
matches block and never resubmit automatically. A failed/terminal job without full
evidence remains blocked. Submitted jobs continue when local monitoring stops.
The orchestrator polls until those jobs reach a terminal state. Normal Workbench
restart reconnects pending monitoring; explicitly stopped work requires Resume.

Overview and Prompt Optimization show coverage separately from the optimization
score. `GET /api/coverage/list` lists batches; `GET /api/coverage?id=<id>` reads one;
`POST /api/coverage/resume` accepts `{"id":"..."}`. Explicit UI Resume also sends
`retry_blocked: true`; background monitoring never repeatedly retries blocked local
work or failed submissions. Current suite changes block
the frozen batch. Completion requires actual compatible completed observations,
including completed wrong answers and terminal timeouts; skipped infrastructure
records do not complete coverage. Missing/changed raw files invalidate the displayed
completion and are audited on resume. Remote raw archives and per-file hashes are
checked before completion is reported. UI status is not an independent score.

`POST /api/coverage/adopt` accepts `{"batch_root":"absolute frozen batch root"}`
for the existing dot-root-prefix batch receipt format. It verifies the accepted
candidate, exact frozen requests, source/suite receipts, model/job uniqueness and
collected raw evidence. It monitors existing collectors and never launches desktop
inference or submits Unity jobs. Stale collector status blocks; it does not authorize
a replacement job. Original batch snapshots and evidence remain untouched. If the
active application uses a different suite, the adopted suite is labeled separately;
its results never complete the active suite's cases.

Validation uses simulated transports/Slurm plus unit and browser/API checks.
Those tests are not real inference or evidence of a new automatically launched
Unity batch. The existing real batch is collected and audited separately.
