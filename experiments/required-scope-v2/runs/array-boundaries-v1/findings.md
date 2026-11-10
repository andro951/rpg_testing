# Array boundaries v1

Six predeclared tasks across three schemas tested array additions and removals, empty arrays and an ordered cross-branch change. Existing dot JSON, slash JSON and path-list recipes, parsers, sampling and 32K context remained fixed. Each task had three input presentations and three repetitions: 54 matched observations per recipe and model. Independent expected states, reference application, schema validity, full-path resolution and both evaluators passed before inference.

| Desktop model | Dot JSON | Slash JSON | Path list |
|---|---:|---:|---:|
| Qwen3 VL 8B Q4_K_M | 42/54 | 23/54 | 30/54 |
| Qwen3.5 4B Q8_0 | 42/54 | 24/54 | 33/54 |
| Qwen3.5 9B Q4_K_M | 54/54 | 9/54 | 36/54 |
| Qwen3.5 2B Q8_0 | 27/54 | 9/54 | 12/54 |
| Qwen3.5 9B Q4_K_S | 54/54 | 18/54 | 42/54 |

No observations were inconclusive in these five complete audited sets. All 810 requests were captured and backend-reported full GPU. Two tasks are object-ID-only (18 observations per recipe/model); four involve unique primitive-value operations, including one mixed field-update task (36 per recipe/model). See scope-split.json for separately counted results and paired-summary.json for exact matched outcomes. Unique primitive-value operations are included in the repository's ID/value contract, but are not object-ID operations or whole-field replacements.

The controller was stopped for scope review and resumed. The last named request was found completed and retained. All 423 pre-resume record hashes were unchanged after the remaining 387 observations; a separate 99-record partial audit remains as a snapshot. A possible dispatch after the stale final status was not observable and remains uncertain.

Results compare complete prompt-processing recipes rather than path syntax alone. Repetitions and presentations are not independent task fixtures, and three schemas cannot support universal claims. Perchance was deferred after a CDP failure and its remote model and sampling controls remain unverified.
