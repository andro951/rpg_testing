# Detailed test evaluation

This is a read-only evaluation layer for the current benchmark contracts. It produces a binary objective verdict plus passed, failed, not-evaluated and not-applicable checks. It preserves saved scores, prompts, responses, test judgements and benchmark identities. No model calls or retries occur.

From the repository directory:

```powershell
.\.venv-workbench\Scripts\python.exe -m evaluation
```

Reports are written to `.local/evaluation/README.md`. Each observation has a readable `.txt` report and a structured `.json` assessment under `assessments/`. `summary.json` indexes examples per test variant and outcome. To replay one definition:

```powershell
.\.venv-workbench\Scripts\python.exe -m evaluation --test prompt_calibration_003_nested_full_paths
```

`--source` accepts the saved results directory or an evidence ZIP; checksums and file identities are verified. `--output` chooses a separate assessment directory. Evidence inside a saved record uses its captured definitions, never today's edited source. Replaying produces the same assessments without reopening benchmark cases.

`catalog.json` explicitly registers all current definitions and variants, with their specific requirements. `fixtures.json` contains labeled synthetic known-pass responses for all 159 objective variants and four inactive example variants. These fixtures are test data, never model prompts or real benchmark observations. The 16 dialogue variants remain unscored pending a separate rubric.

Diagnostics use the existing acceptance rules: equivalent patches are permitted unless ordered operations are declared; RFC extension fields are not newly rejected; boolean/string types remain distinct; existing numeric equality is retained. Explicit intermediate checks are reported separately from the original final verdict. Timeout/incomplete outputs remain inconclusive unless an independently documented irreversible violation proves a failure; this initial implementation does not infer failure from unfinished JSON. Execution status and original timeout failures remain visible.

Run verification with:

```powershell
.\.venv-workbench\Scripts\python.exe -m unittest tests.test_evaluation -v
.\.venv-workbench\Scripts\python.exe -m tests.evaluation_smoke
.\.venv-workbench\Scripts\python.exe -m unittest discover -s tests -v
```

See [implementation plan](../docs/evaluator-plan/README.md), [coverage](../docs/evaluator-plan/coverage.md), and [review record](../docs/evaluator-plan/implementation-review.md).
