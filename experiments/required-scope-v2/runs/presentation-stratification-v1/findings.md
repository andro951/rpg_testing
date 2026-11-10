# Input presentation, model and recipe: retrospective analysis

This analysis includes every one of the nine completed fixed-recipe desktop cohorts: 56 distinct tasks (six in each of eight cohorts, eight in selection-burden), five models, three complete recipes, three presentations and three repetitions. It uses 7,560 previously audited observations. Each table cell below is out of 168 observations, but those observations are three repetitions of each of 56 tasks, not 168 independent tasks. Unity and Perchance are not included; no local records or outcomes were changed.

| Model | Recipe | Normal JSON | ID-keyed | Full paths |
| --- | --- | ---: | ---: | ---: |
| VL8 Q4 | Dot JSON | 94 | 129 | 165 |
| VL8 Q4 | Slash JSON | 71 | 30 | 145 |
| VL8 Q4 | Path list | 105 | 120 | 159 |
| 4B Q8 | Dot JSON | 126 | 126 | 153 |
| 4B Q8 | Slash JSON | 144 | 57 | 156 |
| 4B Q8 | Path list | 120 | 123 | 150 |
| 9B Q4_K_M | Dot JSON | 138 | 132 | 165 |
| 9B Q4_K_M | Slash JSON | 99 | 36 | 123 |
| 9B Q4_K_M | Path list | 105 | 123 | 159 |
| 2B Q8 | Dot JSON | 54 | 108 | 144 |
| 2B Q8 | Slash JSON | 42 | 12 | 111 |
| 2B Q8 | Path list | 36 | 30 | 39 |
| 9B Q4_K_S | Dot JSON | 135 | 129 | 165 |
| 9B Q4_K_S | Slash JSON | 90 | 39 | 132 |
| 9B Q4_K_S | Path list | 129 | 111 | 165 |

The 2B dot-JSON full-path result is a practical candidate: against normal JSON on the exact same task and repetition keys, it has 93 fail→pass gains, three pass→fail regressions, 51 pass→pass, and 21 fail→fail. It is not a model-only path-finding comparison: full-path input supplies program-generated, pre-encoded paths and selectors. For VL8, full-path dot has 71 gains and no regressions against normal JSON; for 4B, 30 gains and three regressions; for 9B Q4_K_M, 27 gains and no regressions; for 9B Q4_K_S, 30 gains and no regressions. Counts describe these tasks and repeated observations, not population probabilities.

For a conservative identifier split, a task is called simple-component only when every ID, primitive-array selector value and field name in both its initial and expected state uses letters, digits, hyphens or underscores. Any other task is classified as containing a reserved component, even if that component is not the target. There are 41 simple-component tasks from seven cohorts and 15 containing reserved components from three cohorts. For 2B dot JSON, simple-component normal/full scores are 51/123 and 105/123, with 57 gains and three regressions; reserved-component scores are 3/45 and 39/45, with 36 gains and no regressions. This conservative classification is not an isolated causal estimate of identifier characters.

Nine tasks across five cohorts change a string field or add an object containing non-ID text; the category excludes primitive-string array membership, and overlaps the identifier groups. On those nine tasks, 2B dot scores normal/full 9/27 and 24/27, with 18 gains and three regressions. For 4B, the same text subset scores 24/27 normal and 21/27 full, with three regressions and no gains. Thus full paths are not a blanket improvement for every task or model. The separate safe-ID text cohorts provide more direct difficult-text evidence and remain separate in `branch-stratified.json`.

For 4B full-path input, slash JSON passed 156/168 versus dot JSON 153/168, but the paired change is nine gains and six regressions; this modest retrospective difference does not establish a universal winner. For 9B Q4_K_S, full-path dot and path list both passed 165/168, but the paired outcomes contain three gains and three regressions for path list relative to dot. Inspect the machine-readable matched transitions before selecting a recipe for a specific workload.

Later prompt-copy and literal-format experiments are not merged into those fixed-recipe totals. `branch-stratified.json` reports all ten completed branch campaigns separately by model and presentation, with exact matched recipe transitions and explicit unmatched cases. For example, in the VL8 restructured-copy holdout, normal JSON improved from 9/18 to 16/18 and ID-keyed from 7/18 to 16/18, while full paths tied at 12/17 on matched pairs. Its later fresh confirmation passed 18/18 for the copy in each presentation; candidate selection had used the earlier holdout. On the 4B safe-text holdout, literal v2 scored 15/18 versus original 9/18 in each presentation, but the separately tested boundary-space weakness still matters.

## Fresh 2B confirmation

The 2B full-path candidate was selected from the retrospective data, then tested without prompt changes on three new simple-ID tasks, one repetition each. Normal JSON passed one of three and full paths passed all three: two matched gains, no regression. All six observations completed on the GPU and were audited. This is consistent with the retrospective pattern but is only a three-task confirmation; it does not establish general reliability. The plan and case set were frozen before outputs. See the separate `twob-presentation-confirm-v1` cohort and run.
