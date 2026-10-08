# Prompt sharing and expansion review

Reviewed October 8, 2026. The original planning review below is now implemented in [`optimization/sharing.json`](../../optimization/sharing.json), with definition-bound APIs, exact instruction locations, ordered expansion scopes and validation tests. See [implementation details](../../optimization/README.md). The earlier inventory remains a planning snapshot. No benchmark prompts, grouping labels, evaluators, judgments or saved results were changed, and no live model runs were started.

## What already exists

`reporting/grouping_metadata.json` assigns all 42 objective definitions / 159 variants to ability category, task type, prompt comparison set, test version and input presentation. `reporting/grouping.py` verifies definition digests and guards comparison sets against different fixtures and required results. `evaluation/catalog.json` supplies evaluator contracts. These are useful inputs to expansion, but neither defines which text may be replaced or authorizes transfer of a candidate.

There are 58 active definitions / 175 variants, including 16 dialogue variants without a fixed quality oracle. Three inactive example definitions add four variants. `sharing-inventory.json` covers all 61 definitions / 179 variants, with existing grouping labels, definition digests, proposed sharing components and transfer restrictions. This is a reviewed planning inventory, not executable optimization configuration.

## Sharing depends on the edited component

Replacing a complete rendered prompt is safe only for its own test: many prompts contain literal input and task facts. A reusable instruction component can transfer between different fixtures while each test retains its own facts, question, output requirements and oracle. No new fixtures or randomized values are proposed.

| Component | Active objective coverage | Expansion allowed | Boundary |
|---|---:|---|---|
| General JSON Patch formatting / JSON Pointer rules | 123 variants | Same task and compatible presentations → related array or scalar updates → all JSON Patch variants | Preserve operation requirements, task facts and direct versus analysis-first workflow. Do not demand JSON Patch from index or semantic tests. |
| Semantic-operation formatting | 12 variants, clothing append and time update | Same task/presentations → other semantic variants | `set`, `list_add`, `list_remove` are a different contract from RFC 6902. |
| Index location method | 24 variants in 8 definitions | Same target/task/presentations → other index-location tasks | Preserve whether the answer is one index or two, and exact text format. Do not ask for a patch. |
| Single-index answer formatting | 21 variants | Same index task → other single-index tasks | Excludes the move task's comma-separated pair. |
| Move-index answer formatting | 3 variants | Move task's three presentations → all eligible models | No other active two-index answer task. A generic locating component can go wider; its pair-formatting rule cannot. |
| Established-facts / preserve-unchanged-state rules | 135 state-update variants | Closest operation/task → broader state updates | Potentially shared across JSON Patch and semantic output only as an output-neutral component. Do not replace either output contract. |
| Analysis-first instructions | 21 variants across 10 definitions | Same task's analysis-first presentations → compatible analysis-first state-update tasks | Retain two calls, `uses` and the final answer contract. Intermediate prose alone has no semantic pass oracle; assess the complete workflow. Never insert an extra call into direct tests. |
| Presentation interpretation | Existing normal/indexed/full-path groups | Same presentation across compatible tasks | Freeze rendering and values. A generic cross-presentation instruction must be explicitly checked in all three modes. Full paths are often embedded literal text, despite raw_json transport metadata. |

These groups overlap intentionally: one variant can participate in several component experiments. They must not become a single universal whole-prompt family.

## Task families and narrower candidates

- **Array-move patches:** `array_patch_move_007` and its full-path counterpart provide three variants. A move-specific candidate stops at this family and broadens across models. Only generic patch/array instructions can expand to the other five patch operations.
- **Array copy, insertion, removal, replacement and conditional test+replace:** each operation has the same three-presentation structure. Their operation-specific clauses stay local. In particular, copy must not become add, and test+replace must retain both operations and their order.
- **Array append:** clothing append, coat addition and array calibration can share generic append/patch guidance. Their events, characters, preservation requirements and workflows remain distinct. Clothing append's semantic versions belong to the semantic family.
- **Removal:** coat removal and ticket removal can share generic removal guidance, but item matching and evidence interpretation stay with the task. Do not share an append instruction here.
- **Scalar replacement:** time, boolean, nested-value and inventory tasks can share generic replace/path/preservation guidance. A five-minute time calculation, boolean value requirement, nested mood change or inventory calculation is task-local.
- **Inventory arithmetic:** the active catalog has one arithmetic fixture, in six presentation/workflow variants. Arithmetic-specific optimization therefore expands through that fixture's compatible variants and all eligible models, not an invented arithmetic suite.
- **Index replacement:** ordinary, minimal and explicit-minimal definitions all target the same ticket. Locating guidance can transfer; the minimal variants intentionally have empty system instructions and different question wording. Adding instructions makes a new candidate condition, not an unchanged minimal control.
- **Calibration:** the four calibration tasks can share general patch guidance, but V1–V6 are alternative prompt designs, not six new data fixtures. Optimizing an example or style requires a candidate version with recorded scope. Do not present overwritten versions that now produce identical requests as independent task coverage.
- **Dialogue:** sixteen active entries share a roleplay prompt and vary temperature from 0.0 to 1.5. They are a sampling sweep, not sixteen different transferable tasks. Keep outside objective pass-based optimization until a quality rubric exists. Perchance's unsupported temperature sweep still collapses within each ordinary repetition.
- **Inactive examples:** cached questions, narrative-then-update and verification/repair have typed outputs, dependencies or bounded loops. Their whole-workflow candidates remain local across models. Individual analysis/patch/boolean-format components may transfer only after preserving each step's distinct question, schema, branch/loop and evidence contract. They remain inactive.

## Concrete expansion ladders

For a **generic JSON Pointer / patch-formatting fix** starting at the move failure:

1. Original failing variant, configured repetitions on the triggering model.
2. All three array-move presentations, preserving exactly one move operation.
3. All six 100-item array-patch tasks: replace, remove, add, move, copy, test+replace (18 variants).
4. Other array mutation JSON Patch tests: append and coat removal, retaining direct/analysis-first distinctions.
5. Remaining scalar/state JSON Patch tasks; maximum scope is all 123 JSON Patch variants.

For an **instruction about move destination semantics**, stop after the three move presentations and expand across eligible models. For an **inventory-specific calculation explanation**, stop after its compatible six variants and expand across models. For a **general evidence/preservation component**, a separately declared experiment can reach all 135 state-update variants, including semantic output with its own untouched formatter.

Every expansion uses full configured repetition counts. Model expansion is an independent axis available to every family; single-task optimization can still produce a task-specific best. A candidate can become best only for the scope it completed. No candidate from these families can truthfully be called best across the entire objective suite merely by forcing incompatible outputs to use its template.

## Additional metadata needed before implementation

Reuse current groups, then add:

1. **Component and editable location:** system instruction, shared template section, final-answer instructions, analysis instructions, or an explicit span inside an embedded prompt. Record what remains fixed. Do not infer spans by deleting arbitrary text around headings.
2. **Compatible family and constraints:** output contract, step role, workflow dependencies, required operations/order, answer arity, and presentation-specific interpretation. Existing `task_type` alone is insufficient.
3. **Ordered expansion scopes:** explicit member test/variant IDs, maximum transfer scope and model-expansion policy. Groups can overlap and a task-specific candidate may have no broader task scope.
4. **Definition binding:** reuse definition digests to invalidate compatibility review when a fixture, prompt or contract changes. Preserve candidate version and original rendered requests.

Candidate history should separately record baseline version, candidate version, edited component, completed scopes, models, observations and comparisons. That is optimization-run evidence, not a new grouping option for the results table. Rejected tests remain blocked; this inventory is not permission to run them. The session stopping rules discussed in chat are proposals and are not implemented here.

## Verification and limits

The inventory is generated from the source definitions and current reporting labels. Review checked prompt construction in `workbench/workflows.py`, including direct_text_v1, legacy_v1 and conversational/style variants; exact task requirements; shared short instruction strings; embedded source/event text; analysis-first dependencies; examples and dialogue sampling. Membership and digests were checked for all 179 variants. This establishes proposed structural compatibility, not empirical improvement. Each transfer still needs the candidate-versus-baseline runs discussed above.
