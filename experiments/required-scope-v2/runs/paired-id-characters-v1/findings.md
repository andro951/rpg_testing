# Paired identifier characters v1

Three fresh fixed-schema object-ID tasks were each paired between plain and reserved-character IDs: R-7/R.7, node-7/node/7, and rack-7 plus part-7 / rack%7 plus part]7. Schema, state, expected state and task matched after ID normalization. Each pair had three input presentations and three repetitions, yielding 27 matched plain/reserved pairs per recipe and model. ID characters, encoded representations and input lengths necessarily differ. Existing dot JSON, slash JSON and path-list recipes, parsers, sampling and 32K context stayed fixed. Independent expected states, reference application, schema validation, full-path resolution and both evaluators passed before inference.

| Desktop model | Dot plain pass / reserved fail | Slash plain pass / reserved fail | List plain pass / reserved fail |
|---|---:|---:|---:|
| Qwen3 VL 8B Q4_K_M | 16/27 | 0/27 | 15/27 |
| Qwen3.5 4B Q8_0 | 21/27 | 0/27 | 27/27 |
| Qwen3.5 9B Q4_K_M | 18/27 | 3/27 | 18/27 |
| Qwen3.5 2B Q8_0 | 9/27 | 0/27 | 6/27 |
| Qwen3.5 9B Q4_K_S | 18/27 | 3/27 | 18/27 |

Across the five models, those counts sum to 82/135 dot, 6/135 slash and 84/135 list matched pairs. Reverse outcomes also exist: four slash pairs failed plain and passed reserved; see identifier-pairs.json for all both-pass, both-fail and directional cells, and paired-summary.json for method comparisons. Each pair is built from only three underlying tasks and repeated presentations, so these counts are diagnostic, not independent population samples. They compare whole recipes, not syntax alone. All 810 requests were captured and backend-reported full GPU; no inconclusive observations occurred.

The prior reserved-ID failure review is saved in the cohort directory. Most recorded errors involved output syntax or selector resolution; three valid responses targeted an unchanged identifier field rather than the requested amount. The record alone does not prove model intent. The paired results support sensitivity to these specific identifier substitutions but do not justify modifying a recipe against these cases or claiming a universal cause. Perchance remained deferred after its CDP failure; model identity and applied sampling controls remain unverified.
