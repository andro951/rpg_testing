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

## Optional intent-language diagnostics

The separately vendored, pure-Python `intent_parser` is an experimental alternative
parser, not a replacement scorer or a change to approved prompts. Inspect saved
Workbench evidence without running a model:

```sh
python -m evaluation.intent_replay --source results --id-key item_id
python -m evaluation.intent_replay --source saved-evidence.zip --output new-diagnostics.json
```

The default destination is stdout. A requested output file must be new and outside
the evidence directory. Directory and ZIP evidence use the existing checksum and
identity checks. Only a completed record's captured initial state and final output
text (plus captured schema for value-patch conversion) enter the adapter; expected answers, example patches, prompts and scores are
never supplied. Missing, incomplete and answer-only records are skipped. No model,
provider, prompt generation, current-definition fallback or benchmark retry occurs.

The captured `result.representation` is recorded as `source_dialect`. Explicit
`intent` responses use the general parser. Active `value_patch` responses use a
schema-aware host (`evaluation.value_intent`) that receives only raw text,
captured initial state and captured `state_schema`. It parses typed quoted selectors
(including slashes inside string IDs), uses each collection's declared `x-id-field`,
and enforces the existing five operation scopes via the unchanged value-path
lowerer. Initial state and every resulting state are schema/identity validated.
Unlabeled alternatives are accepted only when exactly one interpretation is valid
against the current state/schema. Failed operations never mutate the input.

`--id-key` selects the general intent parser's single object-ID field, default `id`.
It does not override schema-declared IDs for captured `value_patch` responses.
`--test` restricts the captured test ID. `--json-patch` exclusively selects the
RFC 6902 diagnostic conversion instead of typed custom intent operations; it never
reactivates the retired standard JSON Patch benchmark builder.

Captured `json_patch` remains unsupported because RFC 6902 `add` can replace fields
or insert at array indices, whereas intent `add` means append. Semantic patches and
missing/unknown dialects are skipped rather than guessed. Use the unchanged legacy
benchmark evaluator for those records. This is optional offline analysis: approved
prompts, scoring and immutable evidence are not changed.

Existing active responses use the approved value-patch JSON format, whereas the
experimental parser accepts an intent language. The dialect-aware host explicitly resolves their path/ID semantics; it does not
change the approved evaluator or automatically repair responses. Rejection is a
parser diagnostic, not a newly measured model failure. Acceptance is parser acceptance, not correctness or a new benchmark score.
Original evidence, scores, approvals and case identities are unchanged. Use the
regular `python -m evaluation` for the approved benchmark's correctness verdict.
For explicit synthetic intent-language records, use `python -m intent_parser
prepared.json`; those are software fixtures, not measured inference.
