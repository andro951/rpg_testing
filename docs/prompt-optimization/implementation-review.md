# Implementation review — October 8, 2026

Reviewed against `optimization-plan.md`, the separately stored optimizer prompts, and Isaac's final instruction to replace intermediate expansion layers with the full matching task type after an origin pass. The results-table evaluator presentation requested while paused is also implemented.

## Implemented scope

The Workbench has a Prompt Optimization tab. Its first executable experiment is the Array move JSON Patch test, with normal JSON, indexed-object and full-path presentations. The experiment definition and label bindings live separately from the original test specifications. The existing component-sharing catalog is preserved; its wider layers do not drive this pilot.

| Agreed behavior | Implementation and review |
| --- | --- |
| Complete system and user messages; plain two-section response | Strict heading/parser validation; literal single-pass `${label}` replacement across both messages. Missing, unknown or malformed labels invalidate the saved proposal. No JSON wrapper, silent repair or executable interpolation. |
| Labels are defined per experiment | The pilot sidecar declares the required labels and immutable input/operation/presentation bindings. Original state, events, oracles and earlier workflow calls remain fixed; bindings contain no solution patch or expected final state. |
| Pass the origin, then run the complete task type | Every configured origin repetition on the selected starting model must pass. A pass opens all three compatible move variants on every model in the frozen host cohort. Full-scope evaluation continues through wrong answers. |
| All runnable models on this execution machine | Host discovery records eligibility and exclusions. It defaults the generator to the highest-parameter available Qwen 3.5, without silently substituting another model. Models on other computers do not block local completion. |
| Perchance capability honesty and repetitions | Perchance is included last only on an actual 8 GB host. Independent repetitions remain distinct; unavailable control variants may share a recorded observation within a repetition. Requested controls and unverified/applied controls remain separate. The existing install-consent lifecycle applies. |
| Defaults: 20 attempts, randomized temperature and seed | Generator temperature is sampled uniformly from the editable 0.5–0.9 bounds; each proposal gets a fresh uint32 seed. Invalid and duplicate proposals consume attempts and remain saved. |
| Reasoning selectable only for generation | The generator has its own reasoning control, off by default. Native benchmark reasoning remains off. Perchance's unavailable reasoning control is explicitly unverified. |
| Only fully covered local candidates enter the top three | Pooled percentages use unique scored observations across the same frozen case/model cohort. Partial candidates cannot rank or satisfy perfect stopping. Individual-model regressions are allowed when the pooled score improves; ties retain the earlier candidate. |
| Stop at attempt limit, manual stop, or complete 100% | Finding a new best alone does not stop execution. There is no consecutive-failure limit. Infrastructure failures leave coverage pending; completed wrong answers and actual trial timeouts are not selectively rerun. |
| Exact history, top three and context pruning | Stored evidence includes actual messages, raw responses, evaluator checks and generation settings. Context/output space is automatic: request estimates, model metadata and exact native tokenization drive allocation; memory failures reduce it. Least-successful history is pruned from the next request only after available growth; baseline, contract and top-three templates/summaries remain protected. |
| Preserve every attempt and support later machines | Checksummed sessions/evidence live under `optimization_results/`, separate from study `results/`. Continue reuses completed trials and attempt counts. Export/import and Evaluate remaining add compatible missing coverage without generating another prompt. Local rankings use the current cohort. |
| Recover from context or execution interruption | Explicit generator-setting edits while stopped preserve coverage and attempts and save their own evidence. A proposal interrupted by process death is marked interrupted, not silently regenerated. A model-load timeout remains infrastructure failure rather than a failed benchmark trial. |
| Explain results-table verdicts | Cell tooltips include concise evaluator reasons. Evidence shows the verdict and expandable checks with expected/actual details. Any disagreement with a saved score is explicit. Existing percentages, timing badges and manual test judgements retain their meanings. |

The interface supports Start, Continue, Pause, Resume, Stop, generation-setting edits, local rankings, all attempts, evidence inspection, ZIP transfer and candidate-template download. Downloading a candidate does not overwrite an original test or promote it automatically.

## Preservation and actual report checks

The case-preservation CLI passed against the repository commit at the start of this implementation, `b51542e6e8554127dbe69ad7e82202e59ce27d26`. It compared 196 existing model-facing requests and 357 cases per native model. All four stored native-model plans retained 357 complete cases and zero pending cases. No existing case was invalidated; no original results were modified and no inference was performed.

All eleven fingerprint-bearing workflow files are unchanged. The native workflow fingerprint remains `56502881bc3c89f6b58c8f5e755b32f58cbd675274ed5363293b598aaddf9787`.

The previous audit baseline preceded the user-approved result/test cleanup and could not validate today's suite. Its context comparison also used different planning inputs on the two sides. The audit now pins the implementation-start commit and uses the same existing planning projection before and after. Three regression tests prove unchanged full-path context and completed wrong answers remain preserved, while genuine prompt/core-file changes still fail the guard. The earlier failed audit logs are retained under `.local/`.

Regenerated the actual report at `.local/reports/statistics.html`: 1,395 records, 180 long-array records, two current cohorts, zero unreadable files. Derived diagnostics contain 493 PASS, 861 FAIL and 41 INCONCLUSIVE outcomes. Comparable completed verdicts agree with saved scores. Inconclusive execution/partial-output evidence remains explicitly inconclusive; this presentation change does not rewrite timeout statuses or raw scores.

## Verification record

Final repository suite: **568 tests passed in 560.110 seconds**, exit 0 (`.local/opro-handoff-suite.log`), after the last smoke-test edit. The expanded run also passed all 568 tests in 608.144 seconds (`.local/opro-complete-suite.log`); the earlier 565-test run passed in 572.786 seconds. Optimizer-focused coverage passed 35 tests, result-feedback coverage passed six tests, and preservation-audit coverage passed three tests.

All 15 repository smoke checks pass: 14 browser checks and the offline evaluator CLI replay. These cover optimizer controls, evidence, reports, judgements, timing, Perchance worker/setup/error/connection paths, ordinary Workbench run/resume, model management, targeted runs and memory assignment. Browser checks use real Edge/HTTP with simulated model responses. The optimizer smoke verifies complete rankings, explicit settings changes, readable evidence, resume without duplicate trials and portable session import/export. The evaluator CLI passes twice and confirms its synthetic raw evidence remains unchanged.

Review fixed a model-load timeout classification bug and a browser-smoke teardown race. Two older Perchance smokes assumed fewer fixture repetitions; their assertions now verify every configured independent repetition, including six infrastructure-error attempts across two three-repetition fixtures. The server's bounded rejected-POST handling also has regression coverage for the previously observed Windows socket-abort problem.

The metadata validator passes for 61 definitions, 179 variants and 574 component scopes. No real optimization or benchmark inference was run. This checkout has no configured host model folder, so actual discovery requires selecting that folder in Worker setup. Mock/browser checks establish implementation behavior, not improved prompt quality, GPU fit or successful live model generation.

## User operation

Restart the Workbench and open Prompt Optimization. With the execution host's model folder configured, the tab automatically scans runnable models and populates both dropdowns on each visit. Choose the generator and starting model, then start the pilot when ready. The usual `Open_Results_Table.bat` rebuilds and opens the updated results table; hover a cell for the reason and open evidence for detailed checks.

Implementation, review and required verification are complete. No commit or push was made. Preexisting sharing metadata and planning work were preserved. Actual prompt-quality measurement remains a future user-started optimization run, not an unfinished implementation check.

## Follow-up — automatic model discovery

Opening Prompt Optimization now calls host-model discovery alongside the session refresh, filling both model dropdowns without a separate Installed Models or Refresh host models action. Each visit rescans, retaining available selections and falling back when a selected model disappears. Scan errors use the existing error dialog; entering the tab again retries.

The expanded Edge browser smoke passes automatic first-entry loading, later additions/removals, selection preservation, failed-scan feedback/recovery, and the existing optimizer run/resume/export/import flow (`.local/opro-auto-scan-smoke.log`; simulated inference). The full repository suite passes all 568 tests in 561.157 seconds, exit 0 (`.local/opro-auto-scan-full.log`). `git diff --check` passes. Native benchmark code, identities and evidence are unchanged by this follow-up.

## Follow-up — automatic token management

Removed both token inputs and their public settings/API fields. `optimization/token_budget.py` plans the generator allocation from the selected model's context metadata, actual request bytes, reasoning mode and prior proposal lengths. Estimates are identified as estimates; the loaded model's tokenizer verifies actual input size. The runner grows allocation before pruning, backs off only explicit GPU-memory/full-placement load failures, and records every load/allocation decision. No proposal is issued during sizing and no benchmark answer is rerun. Protected material that cannot fit stops with a diagnostic, with preparation evidence retained and no generation attempt consumed.

The automatically calculated continuation allowance protects room for an answer; generation can use all remaining allocated context, with a small framing margin, until EOS or the existing deadline. This replaces the previous fixed 4,096-token generation cap. Existing session token values remain archived but are ignored; user-adjustable controls are attempt count, temperature bounds and generator reasoning. Session transfer validates and merges preparation-error and configuration-history evidence as well as trials.

The Edge optimizer smoke verifies the token controls are absent and new requests/session settings contain no manual token values (`.local/opro-auto-tokens-browser.log`). All 46 optimizer tests pass, including eleven new tests for automatic allocation, tokenizer-driven growth, memory backoff and its bound, protected history, non-memory errors, old-session compatibility, preparation recovery, output space and error-evidence transfer (`.local/opro-auto-tokens-focused-pass.log`). The browser smoke also retains complete run/resume/import/export coverage and is included in CI's browser job. Final full suite: **579 tests passed in 548.648 seconds**, exit 0 (`.local/opro-auto-tokens-full.log`). `git diff --check` passes. No live model-quality inference was performed.
