# 4B difficult-text confirmation

For Qwen3.5 4B Q8_0 on six new safe-ID tasks, the preserved original dot-JSON recipe passed 39/54 matched observations and the unchanged literal-line v2 recipe passed 45/54. There were 15 matched gains and nine regressions. All 108 requests were captured, backend-reported `full_gpu`, completed, and had no recorded timeout. Both arms used the same cases, model, context, sampling and semantic scoring.

| Fresh fixture | Dot JSON | Literal v2 |
| --- | ---: | ---: |
| Exact boundary spaces | 9/9 | 0/9 |
| Empty string | 9/9 | 9/9 |
| Actual newline | 9/9 | 9/9 |
| Literal backslash sequences | 0/9 | 9/9 |
| Nested mixed operations with Unicode | 9/9 | 9/9 |
| Quoted text | 3/9 | 9/9 |

The candidate was selected for this follow-up using a previous holdout, so this is a fresh case-set confirmation, not untouched model-selection evidence. It covers six tasks, each in three input presentations and repeated three times; those 54 observations are not independent tasks. A caller requiring exact whitespace cannot treat the literal recipe's net gain as a universal improvement. No prompt or parser was tuned to these outputs.
