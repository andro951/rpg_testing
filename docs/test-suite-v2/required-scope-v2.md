# Current research scope

The current requirements cover fixed-schema updates to existing fields and addition or removal of uniquely identified array elements. A separate model-generated Move or Copy and RemoveAll are outside this scope.

The current dot-path JSON operations recipe was tested on 13 fixtures, 38 presentations and three repetitions, or 114 observations per model, across four Unity 12 GB configurations. Each model passed all 114. Raw JSON observations and their verified JSON-only summary are in `experiments/required-scope-v2/runs/unity-work-20261103`.

The previous two-line field/value variant was not the requested one-line format. Its observations and variant definitions were removed from active project results; its scores are not part of the current comparison. Agree the exact one-line format before implementing or running it.

Paths select collection elements by unique ID or value. The dot resolver rejects ambiguous plain selectors when distinct typed identities have the same spelling. The measured results are limited to the tested fixtures and recipe.
