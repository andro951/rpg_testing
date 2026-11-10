# Selection burden v1

Eight predeclared fixed-schema cases crossed array length (4 or 40), target position (first or last), and operation (existing-field update or unique-ID object removal). Each case had three input presentations and three repetitions: 72 observations per recipe and model, 1,080 total. The 4-element state is the prefix of the complete 40-element state. IDs and values were simple. The 32K context, output contracts, parsers and sampling were unchanged; preflight found no truncation. Independent expected states, reference applications, both evaluators, schema validation and full-path resolution passed before inference.

| Desktop model | Dot JSON | Slash JSON | Path list |
|---|---:|---:|---:|
| Qwen3 VL 8B Q4_K_M | 60/72 | 24/72 | 69/72 |
| Qwen3.5 4B Q8_0 | 72/72 | 54/72 | 72/72 |
| Qwen3.5 9B Q4_K_M | 72/72 | 48/72 | 72/72 |
| Qwen3.5 2B Q8_0 | 60/72 | 24/72 | 24/72 |
| Qwen3.5 9B Q4_K_S | 72/72 | 48/72 | 72/72 |

All 1,080 requests were captured and backend-reported full GPU; no inconclusive observations occurred. factorial-summary.json reports each length/position/operation condition and nine matched early/late or short/long pairs per contrast (three presentations times three repetitions). Dot JSON and path list were perfect across all eight conditions for the 4B and both 9B configurations in this study; other configurations and slash JSON showed failures. This is one synthetic schema, and target ID and input length necessarily vary along with length and position. Repetitions/presentations are not independent tasks, and the results do not establish a universal length or position threshold. These compare complete recipes, not path syntax alone. Perchance remained deferred after its connection failure; its model and sampling controls are unverified.
