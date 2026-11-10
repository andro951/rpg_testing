# Generalization holdout v1 — findings

The existing dot JSON, slash JSON and path-list prompt recipes were evaluated unchanged on six new tasks, with three input presentations and three repetitions: 54 observations per recipe per configuration. All six tasks use one synthetic schema and starting state, so these are not 54 independent underlying fixtures. The test exercises nested updates, longer arrays, escaped strings, append, removal and ordered multiple changes. Reference outputs were checked by independently applying each format and comparing against separately constructed final states; rendered inputs and unchanged instruction prefixes were validated before inference.

| Configuration | Dot JSON | Slash JSON | Path list |
|---|---:|---:|---:|
| Desktop Qwen3 VL 8B Q4_K_M | 39/54 | 12/54 | 38/54 |
| Desktop Qwen3.5 4B Q8_0 | 36/54 | 21/54 | 39/54 |
| Desktop Qwen3.5 9B Q4_K_M | 36/54 | 12/54 | 42/54 |
| Desktop Qwen3.5 2B Q8_0 | 33/54 | 0/54 | 6/54* |
| Desktop Qwen3.5 9B Q4_K_S | 33/54 | 15/54 | 42/54 |
| Unity Qwen3.5 9B Q4_K_M | 39/54 | 12/54 | 36/54 |
| Unity Qwen3.5 9B Q8_0 | 33/54 | 24/54 | 42/54 |
| Unity Qwen3.5 27B IQ2_M | 36/54 | 27/54 | 42/54 |
| Unity Qwen3.5 27B UD-IQ2_XXS | 36/54** | 36/54 | 42/54 |

* Three path-list observations timed out and are inconclusive. ** Six dot observations timed out and are inconclusive. All other non-passes were assessed failures. The watchdog was 120 seconds.

These results compare entire prompt and processing recipes, not syntax alone. The previously perfect results on the earlier 13-fixture set do not establish performance on this new set. The new set also cannot establish general performance across schemas: all six tasks share one schema and starting state. Path-list did well on several configurations but not uniformly; the 2B model scored much worse on that recipe. Refer to paired-summary.json for matched pass/fail cells and the individual audit.json files and raw results for evidence.

There are 1,458 completed local and Unity observations (9 configurations × 162), each with a captured request and backend-reported full-GPU placement. Perchance's additional 162 observations were not run: the controlled browser CDP connection timed out at localhost port 23912. Its underlying remote model and applied sampling controls also remain unverified.

Next useful independent test: retain these recipes and design a separate cohort with genuinely distinct fixed schemas and starting states, preregister its expected states, and compare matched outputs without tuning prompts against this holdout. The current findings do not by themselves select a universal winner.
