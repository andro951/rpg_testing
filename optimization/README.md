# Prompt Optimization tab

The executable pilot is `definitions/array_move_patch.json`. Opening the Workbench Prompt Optimization tab automatically scans runnable host models and populates both dropdowns. It rescans on each visit, preserving available selections; Refresh host models also remains available. Select the generator and starting model, then Start new session. Maximum attempts defaults to 20, temperature bounds to 0.5–0.9, and generator reasoning to off. A pass at the full origin repetition count opens all three Array move JSON Patch presentation variants across all host models. Benchmark reasoning stays off; unsupported Perchance controls remain unverified and its provider runs last only on 8 GB hosts.

`templates.py` implements per-experiment literal labels and immutable bindings, `engine.py` controls sessions/coverage/rankings/context, `runtime.py` isolates generator and benchmark processes, and `storage.py` preserves checksummed evidence under `optimization_results/`. Continue preserves terminal answers and attempt counts. Evaluate remaining creates the current host cohort without generating new prompts. Export/import transfers sessions between machines; candidate export does not change test definitions.

The component catalog below remains a separate reviewed compatibility resource. Its broader expansion layers are not used by this full-message pilot.

# Prompt-sharing metadata

`sharing.json` is the executable sidecar catalog for prompt compatibility. It covers all 61 test/example definitions and 179 variants without adding fields to execution specs or changing existing benchmark identities. All 159 active objective variants have component locations and expansion scopes; dialogue and inactive examples are registered with explicit exclusions.

Each variant records its reviewed definition digest, source file, existing report groups, task family, output contract, immutable requirements, repetition/model policies and compatible components. Each component has exact instruction locations and an ordered list of explicit scope memberships. `expansion_levels` describes the scope sequence; repeated member sets are omitted. These are structural compatibility groups, not evidence of improved model performance or permission to run rejected tests.

## Editable locations

Slots refer to the system message or the last user message of a named step. They carry exact character offsets, original text and the digest of the reviewed message. `locate()` resolves the instruction location and rejects altered input or instructions. The offsets count Python Unicode characters, not UTF-8 bytes or JavaScript UTF-16 code units; a future browser editor must convert them before using string offsets.

- Shared JSON Patch, semantic, index-formatting and task guidance has a zero-width insertion location after the existing final user instructions. Add a paragraph separator when composing guidance. Original input, question and required-operation clauses stay untouched.
- Established-facts guidance replaces the reviewed system instruction prefix. Presentation-specific instructions remain outside that span.
- Index-location guidance replaces the system instruction; insertion into an originally empty system message is recorded as a new candidate condition.
- Analysis guidance replaces only the instruction at the existing analysis step, including an exact tail span when its source/event text is embedded. No workflow step or history message is added or removed.

Span integrity protects the original data, not the meaning of newly written prose. Candidates must retain their declared requirements and pass the unchanged evaluator. A model can still write contradictory guidance; the catalog does not certify that candidate.

## Expansion and guards

General patch formatting starting at an array-move variant expands through its origin, the three move presentations, the 18 array-patch variants, broader array updates, then all 123 JSON Patch variants. Task-specific move guidance stops at its three presentations. Inventory-specific guidance stops at six compatible variants. Each scope declares full configured repetitions and all eligible models; actual eligibility, pending work, rejected-test blocking and provider-control restrictions must be applied by the future executor.

Task-specific instructions cannot transfer across different output contracts. General established-facts and analysis components may span JSON Patch and semantic workflows because their output-specific instructions remain fixed. Formatting families preserve one-index versus two-index answers. Old calibration versions remain alternative prompt conditions, not additional input fixtures. Any future candidate executor must detect identical rendered requests created by overrides and avoid presenting them as distinct task coverage.

## Use and maintenance

Validate every current definition before constructing an optimization run:

```powershell
.\.venv-workbench\Scripts\python.exe -m optimization
```

`optimization.catalog.registration(test, variant)` binds metadata to a current definition. `expansion(test, variant, component)` reads its declared layers. `locate(test, variant, slot)` resolves an instruction span. These APIs do not execute tests, change prompts or choose candidate winners. The catalog itself remains read-only; the tab implementation is described above.

After reviewing changed definitions or prompt construction, maintain `tools/build_prompt_sharing.py`, update the existing report-group reviews where needed, then regenerate:

```powershell
.\.venv-workbench\Scripts\python.exe tools/build_prompt_sharing.py
```

The builder refuses stale reporting classifications. This is an explicit maintenance action, never an automatic runtime review. Validate the generated catalog and review its diff before relying on new membership. Unknown definitions, changed prompt/oracle/input and changed workflow implementation fail closed. Timeout-only changes remain compatible, consistent with timeout-independent test identity. Repetition counts are read from current definitions by the future executor.

See [sharing review](../docs/prompt-optimization/sharing-review.md) for the task-by-task rationale. The earlier `sharing-inventory.json` is a planning snapshot; this catalog is the current implementation.

Generator controls can be explicitly updated while stopped using Apply settings to selected session. Their before/after settings are saved as evidence without changing test coverage or resetting attempts. Context and output allowance are managed automatically; there are no token settings to adjust.

`token_budget.py` estimates an initial allocation from the actual generation packet, model context metadata, reasoning mode and prior generated output. The native tokenizer verifies the real input size before generation. The runner grows context within the model's limit before pruning history; explicit GPU-memory load failures trigger smaller allocations. Only removable history is pruned, and protected baseline/contract/top-three information stays intact. Generation may use the remaining allocated context until EOS or the deadline; its minimum continuation allowance is not a fixed output cap. Allocation, measured input, load failures, pruning and actual generation limit are saved in evidence. Missing model metadata or protected material that cannot fit produces a clear diagnostic without consuming a generation attempt or retrying benchmark answers. Old session token settings remain preserved as historical data but do not control new requests.
