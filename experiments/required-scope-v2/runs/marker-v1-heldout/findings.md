# End-marker representation: 4B development and heldout

This branch is a separate representation and parser derived from the preserved pre-optimization dot-JSON baseline. It uses one update per line and a final `|` to delimit unquoted string text, preserving internal pipes and literal boundary spaces without requiring `\s`. It still escapes backslashes and newlines, and non-string values still use JSON. The original prompts and parsers were not changed.

On Qwen3.5 4B Q8_0, the development comparison passed 24/54 matched observations with the marker and 21/54 with dot JSON: six gains and three regressions. The predeclared screen allowed a separately frozen heldout comparison. On those six fresh tasks, marker passed 27/54 and dot JSON 33/54, with nine gains and 15 regressions. All 108 heldout records were captured, reported `full_gpu`, completed and had no recorded timeouts.

| Heldout fixture | Dot JSON | Marker |
| --- | ---: | ---: |
| Literal backslash sequences | 0/9 | 3/9 |
| Boundary spaces | 9/9 | 3/9 |
| Empty string | 9/9 | 9/9 |
| Nested update/remove/append | 6/9 | 6/9 |
| Actual newline | 0/9 | 6/9 |
| Internal and final pipe | 9/9 | 0/9 |

Each fixture was shown in three presentations and repeated three times. These are six tasks, not 54 independent tasks. The model selection was informed by earlier results; the heldout tasks were frozen before marker development outputs. The marker is not a general improvement on this evidence. It remains an experimental branch; no heldout outcome has been used to tune it. The earlier literal-line v2 branch remains independently preserved and had different model-specific tradeoffs.

## Recovery and controller evidence

The first heldout controller exited during model loading before any case was recorded. Its captured stderr shows Windows `PermissionError: [WinError 5]` on `os.replace` from `run-status.tmp` to `run-status.json`; the error handler's same status update also failed. This establishes the cause of that controller's exit, but does not prove why prior controllers without captured stderr exited. Its orphaned owned model server was stopped. The replacement did not retry the denied status-file operation: it reported progress to a separate redirected stdout stream, and all 108 planned observations were completed once. The captured original stderr and recovery logs are preserved alongside these results. The desktop GPU was released after completion.
