# Reserved identifiers v1

Six predeclared fixed-schema object-ID update/removal tasks across three schemas used distinct IDs containing dots, slashes, quotes, Unicode, percent signs, and brackets. Each task had three presentations and three repetitions: 54 matched observations per recipe per model. Existing dot JSON, slash JSON and path-list recipes, parsers, sampling and 32K context remained fixed. Independent expected states, reference application, schema validity, both evaluators and full-path resolution passed before inference.

| Desktop model | Dot JSON | Slash JSON | Path list |
|---|---:|---:|---:|
| Qwen3 VL 8B Q4_K_M | 18/54 | 27/54 | 18/54 |
| Qwen3.5 4B Q8_0 | 18/54 | 51/54 | 18/54 |
| Qwen3.5 9B Q4_K_M | 24/54 | 42/54 | 15/54 |
| Qwen3.5 2B Q8_0 | 12/54 | 27/54 | 6/54 |
| Qwen3.5 9B Q4_K_S | 18/54 | 39/54 | 18/54 |

All 810 requests were captured and backend-reported full GPU; no inconclusive observations occurred. For the path-list recipe, every pass across all five models occurred in the full-path input presentation, which exposes method-specific encoded paths. This suggests difficulty producing the required escaping from the other views, but does not prove a universal cause. presentation-summary.json contains counts out of 18 per presentation/recipe/model; paired-summary.json and per-model audit.json files preserve matched outcomes and raw evidence.

These are comparisons of complete recipes, not path syntax alone. The tasks were selected to probe a known awkward-identifier weakness, so scores are diagnostic, not estimates of general task frequency. Three synthetic schemas and repeated presentations cannot establish universal behavior. Perchance remained deferred after its CDP failure; its remote model and applied sampling are unverified.
