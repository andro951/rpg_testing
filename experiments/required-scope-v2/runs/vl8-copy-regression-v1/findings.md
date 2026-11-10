# VL8 restructured copy: retrospective regression check

On 18 previously examined tasks from three fixed-recipe cohorts, the unchanged VL8 restructured dot-JSON copy passed 159/162 matched observations versus 138/162 for the saved original. There were 21 gains and zero regressions. All 162 new requests were captured, reported `full_gpu`, completed and had no recorded timeout; their checksummed records were matched to the existing original observations on model artifact, inputs, expected states, context and sampling.

| Earlier cohort | Original | Copy | Gains / regressions |
| --- | ---: | ---: | ---: |
| Identity routing | 51/54 | 54/54 | 3 / 0 |
| Array boundaries | 42/54 | 51/54 | 9 / 0 |
| Multiple changes | 45/54 | 54/54 | 9 / 0 |

For array boundaries, the two unique-ID object-only tasks scored 15/18 for both arms. The four unique-value primitive-array tasks, including one mixed task, scored 27/36 original and 36/36 copy. These are different operation categories. There are 18 tasks, each in three presentations and three repetitions; 162 pairs are not independent tasks. This is a retrospective check on cases already used in earlier research, not a fresh holdout. The separate fresh VL8 confirmation remains 39/54 original versus 54/54 copy, and the earlier holdout remains 28/53 versus 44/53. No prompt was tuned on any of these outputs.
