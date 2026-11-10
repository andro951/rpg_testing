# 4B literal v2: retrospective regression check

On 18 previously examined tasks, the unchanged Qwen3.5 4B Q8_0 literal-line v2 recipe passed 132/162 matched observations versus 147/162 for saved original dot JSON. It had nine gains and 24 regressions. All 162 new requests were captured, reported `full_gpu`, completed and had no recorded timeout. Checksummed results were matched on model artifact, target, inputs, expected states, 32K context and sampling.

| Earlier cohort | Dot JSON | Literal v2 | Gains / regressions |
| --- | ---: | ---: | ---: |
| Identity routing | 51/54 | 51/54 | 3 / 3 |
| Array boundaries | 42/54 | 45/54 | 6 / 3 |
| Multiple changes | 54/54 | 36/54 | 0 / 18 |

Both arms passed 18/18 on the two object-ID-only array-boundary tasks. On four unique-value primitive-array tasks, including one mixed task, dot JSON passed 24/36 and literal passed 27/36, with six gains and three regressions. The 18 multiple-change regressions came from two orchard fixtures. Object-ID and primitive-value operations are distinct categories.

These are 18 tasks, each shown in three presentations and repeated three times, not 162 independent tasks. The cases were already used in prior method selection; this is a retrospective regression check, not fresh holdout evidence. In the separate fresh difficult-text confirmation, literal v2 scored 45/54 versus 39/54 dot but lost all nine boundary-space observations while gaining on backslash and quote cases. These results support a workload-specific tradeoff, not a single universal 4B winner. No recipe was tuned on these outputs.
