# VL8 model-specific confirmation

Qwen3 VL 8B Q4_K_M: the preserved original dot-JSON recipe passed 39/54 matched observations and the unchanged restructured instruction copy v2 passed 54/54. There were 15 matched gains and zero regressions. All 108 requests were captured, reported `full_gpu`, and completed without recorded timeouts. Original/copy inputs, schemas, expected states, semantic scoring, context and sampling were checked as matched.

| Fresh fixture | Original | Copy |
| --- | ---: | ---: |
| Nested update using reserved ward ID | 3/9 | 9/9 |
| Remove using reserved crate ID | 3/9 | 9/9 |
| Numeric field update using simple ID | 6/9 | 9/9 |
| Nested update plus append | 9/9 | 9/9 |
| Append object using simple ID | 9/9 | 9/9 |
| Remove object using simple ID | 9/9 | 9/9 |

The confirmation used six new schemas, each shown in three presentations with three repetitions. Repetitions and presentations are not independent tasks. The copy was selected because of its earlier VL8 heldout improvement, so this is an independently constructed follow-up case set, not untouched model-selection evidence. It does not establish general reliability or applicability to other models. Prompt copy v2 and the original were not modified in response to either heldout set. All raw results, per-case pairs, prompt digests and the earlier evidence are preserved.
