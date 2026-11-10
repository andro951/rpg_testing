# Array scale v1

A fixed-schema existing-field update and unique-ID object removal targeted the last element in arrays of 4, 8, and 16 entries. Each task had three presentations and three repetitions, yielding 18 observations per length and recipe per model. Existing dot JSON, slash JSON, and path-list recipes, parsers, sampling, and 32K context remained fixed. Expected states were independently constructed; both evaluators, schema validation, reference application, and full-path resolution passed before inference.

| Desktop model | Dot JSON | Slash JSON | Path list |
|---|---:|---:|---:|
| Qwen3 VL 8B Q4_K_M | 54/54 | 51/54 | 54/54 |
| Qwen3.5 4B Q8_0 | 54/54 | 42/54 | 54/54 |
| Qwen3.5 9B Q4_K_M | 54/54 | 36/54 | 54/54 |
| Qwen3.5 2B Q8_0 | 45/54 | 36/54 | 27/54 |
| Qwen3.5 9B Q4_K_S | 54/54 | 30/54 | 54/54 |

All 810 requests were captured and backend-reported full GPU; no inconclusive observations occurred. For per-length and matched counts see length-summary.json and paired-summary.json. In this small set, dot JSON and path list were perfect at all three lengths for the four non-2B models; 2B scores were unchanged across lengths. Slash results varied in several models. These are recipe-level observations and do not establish a general array-length threshold. Size, target ID and input length changed together, and the study has just one schema and two underlying tasks per length. Presentations and repetitions are not independent task fixtures. Perchance was deferred after its CDP failure; remote model identity and applied sampling remain unverified.
