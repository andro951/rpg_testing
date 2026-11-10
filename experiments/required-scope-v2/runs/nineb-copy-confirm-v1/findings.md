# 9B instruction-copy-v1 confirmation

Two existing Qwen3.5 9B configurations were tested sequentially on four new simple-ID tasks, with three presentations and three repetitions per task. The original dot-JSON and unchanged instruction copy v1 were compared with matched model, data, expected state, semantic grading, context and sampling. Candidate selection was informed by earlier heldout results, so this is a fresh case-set confirmation rather than untouched model-selection evidence.

| Model | Original dot | Copy v1 | Paired transitions |
| --- | ---: | ---: | --- |
| Q4_K_M | 27/36 | 27/36 | 27 pass→pass, 9 fail→fail |
| Q4_K_S | 36/36 | 36/36 | 36 pass→pass |

Q4_K_M failed all nine observations of the same quoted-newline message task for both recipes; both passed the literal-backslash/boundary-space task, nested update-plus-add task, and object removal task. Q4_K_S passed all nine observations of each task for both recipes. The earlier 9B copy-v1 holdout gains therefore did not recur on this small new set; this does not prove the recipes equivalent in general. Three presentations and three repetitions of each of four tasks do not make 36 independent tasks.

Both runs completed sequentially, each with 72 captured full-GPU observations, no recorded timeouts, no missing or duplicate keys and unchanged prompts and parsers. Both audits verify paired model artifact, target, schema, source, expected state, 32K context and sampling. The desktop model server and controller had exited and the GPU was released at the final check. Prior results and all branch lineage are preserved.
