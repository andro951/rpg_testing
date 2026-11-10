# Schema diversity v1

Six distinct tasks across three new fixed schemas and starting states were presented in three representations, with three repetitions for each of the existing dot JSON, slash JSON, and path-list recipes. Instructions, parsers, sampling and 32K context were unchanged. Reference answers independently produced manually constructed expected states, both evaluators passed, schemas validated, and all rendered full-path entries resolved before inference.

| Desktop model | Dot JSON | Slash JSON | Path list |
|---|---:|---:|---:|
| Qwen3 VL 8B Q4_K_M | 45/54 | 36/54 | 37/54 |
| Qwen3.5 4B Q8_0 | 45/54 | 42/54 | 48/54 |
| Qwen3.5 9B Q4_K_M | 51/54 | 36/54 | 48/54 |
| Qwen3.5 2B Q8_0 | 27/54 | 12/54 | 12/54* |
| Qwen3.5 9B Q4_K_S | 54/54 | 36/54 | 48/54 |

* One path-list observation timed out after 120 seconds and is inconclusive; remaining non-passes were assessed failures. All 810 observations were captured and backend-reported full GPU. See paired-summary.json for exact matched outcomes and audit.json plus raw records for each model.

These are comparisons of complete recipes, not an isolated test of path syntax. Eighteen presentations per recipe arise from only six underlying tasks across three schemas; three repetitions are not independent task samples. In the first three models, primitive-array removal failed in some presentations even where many object field updates succeeded, motivating the separately predeclared array-boundaries-v1 follow-up. A perfect score on this small cohort does not establish broad generalization.

Perchance was deferred after the earlier CDP connection failure; its remote model identity and sampling remain unverified.
