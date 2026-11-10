# Multiple changes v1

Six predeclared fixed-schema tasks across three schemas compared one update with three ordered changes, including one update/remove/append combination. Each task had three input presentations and three repetitions: 54 matched observations per recipe per model. Existing dot JSON, slash JSON and path-list recipes, parsers, sampling and 32K context remained unchanged. Expected states were independently constructed; both evaluators, reference application, schema and full-path resolution passed before inference.

| Desktop model | Dot JSON | Slash JSON | Path list |
|---|---:|---:|---:|
| Qwen3 VL 8B Q4_K_M | 45/54 | 24/54 | 54/54 |
| Qwen3.5 4B Q8_0 | 54/54 | 42/54 | 54/54 |
| Qwen3.5 9B Q4_K_M | 54/54 | 36/54 | 51/54 |
| Qwen3.5 2B Q8_0 | 42/54 | 18/54 | 3/54 |
| Qwen3.5 9B Q4_K_S | 54/54 | 36/54 | 54/54 |

All 810 requests were captured and backend-reported full GPU; no inconclusive observations occurred. change-count-summary.json separates 27 single-change and 27 three-change observations per recipe/model; paired-summary.json and model audit.json files contain matched outcomes and raw evidence. Task content and operations change along with count, so differences cannot be attributed solely to the number of changes. Presentations and repetitions are not independent tasks; three synthetic schemas cannot establish a universal result. These are complete recipe comparisons rather than path-syntax-only comparisons. Perchance remained deferred after the CDP connection failure; its underlying model and sampling controls remain unverified.
