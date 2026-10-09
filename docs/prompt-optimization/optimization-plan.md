# Automatic prompt optimization plan

Agreed design recorded October 8, 2026. The prototype is now implemented; this document records its contract. Implementation tests do not authorize live optimization runs. Earlier suggestions about five consecutive failures, stopping at the first new best, ranking partial candidates, or fixing the candidate's system message are superseded.

## Goal and first experiment

Use the highest-parameter Qwen 3.5 model available on Isaac's desktop to propose better prompts. Resolve its actual catalog identity, artifact hash and runtime at setup; do not guess a model name or silently substitute another model. Evaluate candidates using existing deterministic evaluators and the existing model configurations, preserving exact prompts, outputs, judgments and provenance.

Start with one optimization experiment for the existing 100-item array-move JSON Patch test. Keep this experiment's definition separate from test JSON. The executable definition is `optimization/definitions/array_move_patch.json`; the `.draft.json` sibling retains the earlier planning snapshot. The executable definition has its own labels, bindings, target, expansion scopes and output contract. The selected failure's exact variant/model/evidence record must be pinned when the session is prepared. This plan uses `array_patch_move_007/indexed_object_json_patch` as a concrete draft anchor; it is not a claim that a particular recorded failure was inspected in this planning turn.

The optimizer controls both the complete system message and complete user message for the call being optimized. There is no hidden fixed system instruction and no mandatory preservation of the original instruction wording. It can change ordering, explanation, formatting, examples and presentation of the supplied information. It cannot change the input data, task meaning, required output/operations, evaluator, model test settings or workflow topology. Generic examples must not expose this benchmark's expected answer, indexes or example solution patch.

## Per-experiment placeholders

There is no global fixed label list. Every separate optimization definition explicitly declares the exact labels required by that experiment, their meanings and their bindings to each covered test. The generator receives that contract on every attempt.

For this draft experiment the labels are `${current_state}`, `${new_information}`, `${task_requirements}`, `${presentation_notes}` and `${prior_outputs}`. These are choices for the array-move/JSON Patch experiment, not reserved names for every future experiment. A future experiment can have a different set.

Each required label must occur at least once across the generated system/user pair. Labels may occur in either message and may occur more than once. A label is never globally restricted to the user message. Any label not declared by this experiment, malformed placeholder or missing required label invalidates the candidate. Empty data values are valid where the definition explicitly allows them, such as no prior outputs in a direct test.

Substitute literal `${label}` tokens once using the definition's bindings. Do not evaluate JavaScript, shell commands, expressions, property accesses or template code. Insert values verbatim; do not recursively expand placeholder-looking text inside supplied values. Store both original templates and exact rendered messages. Placeholder substitution is input construction, not an answer-extraction marker. This first experiment retains the normal JSON Patch output contract and existing parser; it introduces no output sentinel or result wrapper.

The optimizer's response format is ordinary text with two headings, each on its own line, in this order:

```text
SYSTEM_MESSAGE:
The complete candidate system-message template.

USER_MESSAGE:
The complete candidate user-message template.
```

The explanatory lines above are replaced by the actual templates. No JSON wrapping or string escaping is required. The headings occur exactly once and cannot also appear as standalone lines inside the templates. Save raw output and reasoning before validation. Parse the section boundaries using the exact heading lines, preserving message contents and real line breaks; remove only the defined separator blank line immediately before USER_MESSAGE:, without trimming template contents. Missing, duplicate or out-of-order headings, preamble text or invalid placeholders are failed candidate-generation attempts; do not repair them silently or fabricate a usable template. Give that validation feedback to the next generation attempt. This changes the optimizer response format, not the benchmark's JSON Patch output contract.

## Full-template compatibility

The existing `optimization/sharing.json` catalog is component-based and currently protects original instruction spans. Full system/user replacement is a newly agreed requirement and needs a separate reviewed full-template binding in the experiment definition. Do not bypass component-span guards to achieve it.

For the first experiment, optimize the final JSON Patch call. Earlier analysis steps in an analysis-first workflow remain as defined. Their real outputs are supplied through the declared prior-output binding; never invent analysis. This preserves the test's calls, branches and evaluator while allowing the candidate to organize all instructions and context for the final call. Any later optimization of earlier steps is a separately declared experiment.

The full-template contract must carry required operation rules as data for the relevant test, rather than hardcoding `move` into a universal instruction. The move test requires exactly one move; copy requires copy; conditional update requires test then replace. This permits generic instructions to expand without changing task contracts.

## Evaluation and expansion

Use existing cases; do not create randomized values or additional fixtures as the widening strategy. Run full configured repetition counts at every layer. The current move fixture specifies one repetition; do not quietly increase it to three. Other covered definitions retain their own configured counts.

Freeze the models available and runnable on the current host, covered tests/variants, settings, judgments, definition hashes, template bindings and the comparator at session start. "Current machine" means the computer executing OPRO and model inference, not a laptop viewing its Workbench. Discover all available model configurations using existing worker preflight and eligibility rules; do not require models installed on other computers or models this host cannot run. Honor provider capabilities, including Perchance's actual 8 GB eligibility. Record unavailable models and exclusion reasons. Rejected tests never run. Inactive examples and dialogue are outside the first objective scope. Do not remove an included model merely because it later errors; that work remains incomplete. Changing the frozen local scope requires an explicit new evaluation cohort.

Completing every covered test/repetition on this frozen local model set is sufficient for all normal OPRO decisions: layer completion, top-three eligibility, incumbent promotion and perfect-score stopping. Missing evaluations on other machines do not block these decisions and do not add failures to the local score. Preserve accurate coverage: say "complete on this machine's model set" rather than claiming untested models passed. Additional models remain pending for later evaluation on other machines.

Provide an "evaluate remaining on this machine" path for saved candidates on another host. It discovers that host's runnable model set, reuses exactly compatible saved observations and evaluates only missing work; it does not regenerate the candidate or consume another prompt-generation attempt. Preserve original local results and the attempt ledger. Group top-three/comparator calculations by model cohort, comparing candidates over identical cases/models. Cross-machine evidence can be combined into a broader comparison once candidates have matching coverage, but an uneven mixture of model sets must not silently reorder the local top three.

October 8 implementation revision: use one starting case on a selected starting model, then every active JSON Patch test of the matching task type on every runnable model on this host. For the pilot this means the indexed-array move origin, followed by all three Array move presentation variants. Do not expand to other operation types or through intermediate scopes. The component catalog retains its older broader scopes for future component experiments; those scopes do not drive this executor.

Run every configured origin repetition on the selected starting model. If all pass, run the complete matching task type on every current-host model at the existing full repetition counts. Otherwise save the failure and generate the next candidate. Complete the full task-type run even when some answers fail. Rank only complete current-host candidates; a higher pooled score may include an individual-model regression. There is no intermediate incumbent expansion gate.

The baseline reference must be explicitly versioned and complete over the final configured scope. It may initially be the existing original prompts for the selected tests, treated as a reference profile rather than pretending they are one generated template. Reuse saved baseline observations only when the exact request/settings/model/evaluator conditions match. Run missing baseline work before relying on its comparisons. Pin the initial comparator and change the incumbent only after complete-scope evaluation.

Preserve each required outcome in the coverage ledger. A correct response is PASS; an incorrect response is FAIL; actual timeout is unsuccessful and retains its timeout evidence. Infrastructure errors do not become semantic failures or disappear from coverage: they leave the candidate incomplete. Pause for infrastructure recovery under the existing explicit recovery policy; do not selectively reroll wrong answers or timeouts.

Completed work is reused as layers expand. Repetitions are distinct trials, never copied responses. If full-template replacement makes several old prompt-version variants render identical requests under identical execution settings, record the mapping and count the unique observations once. Cover every requested member without inventing additional independent samples. Provider-specific collapsing still applies only to unavailable controls within each repetition, including Perchance's unverified seed behavior and unavailable temperature control.

## Score, incumbent and top three

Use pooled PASS observations divided by all scored observations in the same scope. Retain the per-model/per-test breakdown. A regression on one model is acceptable when the total improves. Different legitimate observation counts weight the pooled score naturally; do not switch silently to equal-model weighting.

A candidate is eligible for the top three only after all required tests and repetitions in the final configured test scope are complete on every model available in the frozen current-machine cohort. That local completion is treated as complete coverage for OPRO even when other machines' models remain untested. Candidates incomplete within the local scope never enter the top three, regardless of their score. If fewer than three candidates qualify, show only the available candidates. No locally incomplete candidate fills an empty slot. Show candidate templates, total score, coverage and at least the per-test/per-model statistical summary for each top candidate, with additional-machine work identified separately.

Rank fully covered unique candidates by pooled score. Proposed deterministic tie handling: retain the earlier candidate; a tie does not replace the incumbent. Duplicate template pairs are archived but do not occupy multiple top-three positions. The winner is best only over the experiment's declared compatible scope; it is not a universal prompt for index answers, semantic operations or dialogue.

## Attempts, generation settings and stopping

October 9 user requirement: prompt-writing generation has no elapsed-time watchdog or socket timeout. Apply this with reasoning on or off. Completion, the automatically allocated context/output allowance, and manual Stop govern an individual generation request. Save the no-timeout policy in new request evidence and preserve partial output on interruption. Candidate benchmark deadlines remain independent.

UI setting `maximum attempts`: default 20, editable before starting. One generation request consumes one attempt. Invalid and duplicate proposals consume attempts and are saved. Trial observations and expansion layers do not each consume a generation attempt. Explicit resume continues the same attempt ledger and count rather than restarting at zero.

UI settings `minimum temperature` and `maximum temperature`: proposed defaults 0.5 and 0.9, midpoint 0.7. Sample uniformly between them for each prompt-generation request. Equal bounds give a fixed temperature. Validate finite, nonnegative bounds with minimum no greater than maximum, and reject settings unsupported by the chosen generator/runtime. Generate a fresh randomized uint32 seed for each generation request. Record the sampled temperature, seed, all other actual sampling settings and raw response. Do not vary benchmark-model temperature or seeds as part of this generator exploration.

UI setting `generator reasoning`: off by default. It applies only to the prompt-writing model. Reasoning for benchmark runs is always off and is not exposed as an option. Keep generator and test configurations separate so an optimizer reasoning setting cannot leak into test requests. Verify local reasoning control; never silently fall back to an unavailable setting. For external providers, retain accurate capability evidence instead of pretending to enforce an unavailable control. Save returned reasoning separately from the parsed candidate message sections when present; it is not part of the candidate's templates.

There is no consecutive-failure stopping rule. Finding an improved fully covered candidate does not stop the session. Stop automatically when the attempt limit is reached or a candidate passes 100% of required observations on every covered test and every model in the frozen current-machine cohort at full configured repetition counts. Other machines' pending models do not prevent this local perfect-score stop. An empty runnable-model cohort cannot qualify or produce a perfect result. Missing local work, infrastructure errors, excluded controls or partial local coverage cannot manufacture a perfect result. Also support explicit pause/stop, retaining resumable evidence. Requests that cannot fit the generator's context after permitted pruning require attention; do not silently truncate protected information.

## Feedback and context pruning

On each attempt, supply the baseline/reference, the optimization contract, the top three fully covered candidates and their per-test/per-model summaries, and the retained history of every earlier attempt in this session. History contains the exact candidate templates, actual rendered prompts and outputs, detailed evaluator/validation feedback, completed layers and coverage. Include both successful and unsuccessful outcomes; do not select only favorable results. Deduplicate repeated input blocks by explicit references when assembling the packet, retaining exact bytes in the evidence store and including referenced material needed by the generator.

All attempts remain on disk. When the complete generation request plus reserved generation/reasoning output budget exceeds the actual context window, prune attempt records from the generator's input only. Prune candidates rejected at the earliest expansion layer first; within the same layer, prune the lowest score first. Proposed stable tie break: prune the oldest equally unsuccessful record first. Invalid proposals rank below evaluated proposals. Do not compare percentages from different layers as if they had equal scope.

Protect the current contract, required label definitions, current task/baseline material and the top three fully covered candidates with their required summaries. Top-three templates are always included even if their detailed per-observation evidence needs to be removed as a separately recorded context reduction; retain at least the agreed summaries. Record exactly which history/evidence blocks were pruned, the reason and the final prompt actually sent. October 8 UI revision: context and output space are automatic, not user settings. Derive an initial allocation from model metadata and request/history estimates, verify exact input with the runtime tokenizer, grow within the native limit before pruning, and reduce allocation on explicit GPU-memory load failures. Record every allocation/load decision. Generation can use the remaining context until EOS, manual Stop or the allocated context limit; the minimum continuation allowance is not a fixed output cap. If protected information still cannot fit the model/GPU capacity, stop with a clear diagnostic without discarding the contract or consuming a proposal attempt.

## Persistence and interface

Store a durable session definition and append-only attempt/evaluation records outside test_specs. Record every optimizer request, raw output, reasoning, validation result, template pair, random seed/temperature, actual test requests/responses, evaluator version, model identity, timings, scope progression, comparisons, pruning decisions, terminal status and stop reason. Preserve interrupted attempts and infrastructure evidence. Keep candidate study observations separate from original benchmark results and completion state.

The UI should select the one optimization definition and generator model, show the current host's covered tests/models and separately pending models, expose the attempt limit, temperature bounds and generator-only reasoning toggle, and provide Start/Pause/Resume/Stop plus evaluation of remaining candidate trials on another machine. Show progress, retained history, locally eligible top three and evidence inspection. Proposed winner promotion is an explicit action that creates a versioned default/reference; do not overwrite original tests or silently deploy a winning prompt. Existing model/provider setup and rejection controls still apply.

## Optimizer prompt and implementation sequence

The complete draft request consists of `optimizer-system.txt` and `optimizer-user-template.txt`. The latter contains one application-owned packet insertion point. It is separate from candidate `${label}` placeholders and is replaced with serialized session evidence, not evaluated as template code.

The serialized packet must contain these named sections, matching the optimizer prompt:

- `experiment`: definition/version, generator/model configuration, attempt number/limit, fixed model/test scope and current layer.
- `required_labels`: this experiment's exact label names, meanings, required occurrences and data bindings, including empty-value rules.
- `immutable_contract`: member-specific task/output/operation requirements, unchanged inputs/workflow, evaluator and reasoning policy. Never put a solution patch or oracle answer in a tested-model binding.
- `reference`: pinned baseline/incumbent identity, same-scope statistics and exact relevant rendered prompts, responses and evaluator feedback. Missing reference evidence must be identified rather than invented.
- `top_three`: zero to three unique fully covered candidates, their complete templates, overall coverage/score and at least per-test/per-model summaries. An empty initial list is valid.
- `attempt_history`: retained prior proposals, exact requests/responses, validation/evaluation diagnostics and scope progression. Keep incomplete outcomes explicitly incomplete.
- `pruning`: omitted history IDs, omission reasons and retained coverage. Do not summarize omitted exact text as though it were supplied.

The current planning files contain no fabricated trial outputs or optimizer successes. Actual reference and history evidence is inserted during session preparation and execution. The optimizer prompt is complete; the packet insertion point is runtime data, just as candidate labels receive per-test runtime data.

Implement in this order: reviewed per-experiment bindings and template validation; session/attempt persistence; exact baseline/candidate observation mapping and evaluation; expansion/top-three/stop logic; context accounting and pruning; generator adapter with random settings and separate reasoning; UI; unit and smoke coverage. Test malformed templates, missing/unknown labels, literal placeholder-looking input, both-role placement, unchanged input/oracles, operation preservation, full-scope ranking, regression tradeoffs, duplicate requests, invalid/infrastructure outcomes, pruning protection, context exhaustion, max-attempt resume, perfect-score stopping and reasoning isolation. Run the full repository suite and simulated run/resume checks before live trials.

The existing metadata implementation documented Windows socket-abort errors in two server tests, including one that repeated on isolated rerun. Do not erase that validation history or claim those checks were clean; recheck them during implementation.


## Prototype operation and storage

Open the Workbench Prompt Optimization tab; it automatically scans runnable host models and populates the dropdowns on each visit. Choose the prompt-writing and starting-case models, set generation controls, and start a new session. Qwen 3.5 with the highest reported parameter count is selected when it is installed and fits the host; no substitute is silently selected. Models must have an assigned memory budget. Load errors leave their coverage pending. The prototype is disabled in ordinary Demo mode; mock model execution is confined to its unit/browser tests.

Sessions and checksummed evidence live under `optimization_results/<session-id>/`, separate from normal `results/`. Stop before exporting a consistent ZIP; import it on another host and choose Evaluate remaining on this machine. Larger sessions can be transferred by copying their session directory. Compatible terminal observations are reused; foreign-host scores never enter the local ranking. Exporting a candidate produces a plain-text template file, without overwriting benchmark definitions. Use Apply settings to selected session while stopped to change attempt, temperature or reasoning controls; context/output space is automatic. Each explicit control change is saved as separate evidence and preserves benchmark coverage and consumed attempts. Continue session resumes the history. Legacy saved token values remain archived but are ignored by the new automatic policy.
