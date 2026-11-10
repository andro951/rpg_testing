# 2B presentation confirmation

The unchanged original dot-JSON recipe was evaluated on Qwen3.5 2B Q8_0 using three newly constructed simple-ID tasks, each once as normal JSON and once as full paths. Full paths passed 3/3; normal JSON passed 1/3. The two matched gains were the nested update-plus-append task and the quoted-newline text update; both presentations passed the object-removal task. There were no matched regressions.

All six requests were captured, reported full GPU, completed with no recorded timeouts, and were audited for matching model artifact, state, expected result, 32K context, sampling and semantic scoring. Full-path input supplies program-generated paths, so this compares presentations as complete recipes, not model-only path-finding. The candidate presentation was selected from retrospective evidence, and three tasks are too few to establish general reliability. The tasks and unchanged prompts were frozen before their outputs were observed.
