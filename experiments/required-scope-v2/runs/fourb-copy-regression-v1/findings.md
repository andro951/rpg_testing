# 4B three-recipe retrospective comparison

On 18 previously examined tasks, original dot JSON passed 147/162 matched observations, literal-line v2 passed 132/162, and the restructured dot instruction copy v2 passed 108/162. Against original dot, the copy had 12 gains and 51 regressions. All three arms are matched by case, presentation and repetition; their individual audits verify model artifact, target, source, expected state, 32K context and sampling. This is retrospective evidence, not a fresh holdout.

| Earlier cohort | Original dot | Restructured dot | Literal v2 |
| --- | ---: | ---: | ---: |
| Identity routing | 51/54 | 21/54 | 51/54 |
| Array boundaries | 42/54 | 42/54 | 45/54 |
| Multiple changes | 54/54 | 45/54 | 36/54 |

The equal array totals hide different behavior. On two unique-ID object-array tasks, original and literal each passed 18/18, while the copy passed 9/18. On four unique-value primitive-array tasks, including one mixed task, the original passed 24/36, the copy 33/36, and literal 27/36. The categories are distinct. The 18 cases were each shown in three presentations and repeated three times; the resulting 162 observations are not independent tasks.

This comparison does not cancel the copy's positive VL8 evidence. For 4B, it supports the original dot recipe as the stronger general-scope choice in these cases, while literal v2 remains a workload-specific text candidate with a known boundary-space weakness. No prompt or parser was tuned to these results. All 162 new copy requests were captured, `full_gpu`, completed and not recorded as timed out; earlier original and literal records remain in their own cohorts.
