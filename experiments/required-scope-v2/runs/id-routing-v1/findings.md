# ID routing v1

Six tasks across three fixed schemas tested object-ID updates, additions and removals when the same child ID appeared in different parent collections. IDs remained unique within their own collection. Existing dot JSON, slash JSON and path-list recipes, parsers, sampling and 32K context were held fixed. Each task had three presentations and three repetitions: 54 matched observations per recipe and model. Expected states were independently constructed and reference application, schema, path-resolution and both evaluators passed before inference.

| Desktop model | Dot JSON | Slash JSON | Path list |
|---|---:|---:|---:|
| Qwen3 VL 8B Q4_K_M | 51/54 | 18/54 | 51/54 |
| Qwen3.5 4B Q8_0 | 51/54 | 33/54 | 48/54 |
| Qwen3.5 9B Q4_K_M | 54/54 | 6/54 | 33/54 |
| Qwen3.5 2B Q8_0 | 33/54 | 12/54 | 9/54 |
| Qwen3.5 9B Q4_K_S | 54/54 | 6/54 | 39/54 |

All 810 observations had captured requests and backend-reported full GPU; no inconclusive observations were recorded. See paired-summary.json for matched outcomes, and per-model audit.json and raw records for evidence. The scores compare complete recipes, not path syntax alone. Presentations and repetitions are not independent tasks, and these three synthetic schemas cannot establish universal behavior. Perchance remained deferred after the CDP failure; its model identity and sampling controls remain unverified.

A separate predeclared array-scale-v1 comparison holds task structure and last-item position fixed while varying array size, input length and target ID. It is designed to explore a length-related boundary, not prove a pure causal effect.
