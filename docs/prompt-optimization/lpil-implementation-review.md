# LPIL writer and feedback review — October 9, 2026

Isaac requested the new optimizer prompt from `LPIL_all_current_files.zip`, fixes
for the duplicate feedback that blocked generation, and an exported first-run
request. All five source files were initially copied verbatim into `lpil/`. Isaac
subsequently requested removing "Read the formatting as follows." from the general
description; that is the only change to those supplied files. No benchmark
definitions, oracles, saved responses or baseline observations were changed.

## Implementation

- `optimization/lpil.py` handles recognized markers, syntax checks, matched named
  blocks, single-level raising/lowering, outer literal normalization and metadata
  lines. It knows nothing about JSON Patch, OPRO scores or mandatory output blocks.
- `optimization/prompt_builder.py` handles the OPRO task's required-output block,
  independent source/new replacement counts, the standard-output choice, and
  one-user-message assembly. New candidate replacements are validated after one
  decrement. The language explanation's syntax examples and raw external evidence
  are opaque text, so normalization cannot rewrite their meaning.
- `optimization/feedback.py` keeps each captured request once and includes every
  model's full captured output with compact diagnostics. It drops repeated states,
  original-score copies, duplicated checks and transport stream chunks from the
  feedback, while preserving all of those in immutable evidence. Missing effective
  requests fall back to saved workflow messages and are labeled honestly.
- `optimization/engine.py` uses the new writer for new sessions and legacy
  zero-candidate resumes, preserves baseline coverage, drops unused request-pool
  entries during history pruning, and saves actual counts when context cannot fit.
- Legacy candidate rendering remains supported. LPIL candidate rendering performs
  normalization before literal one-pass data insertion. An empty system message
  is omitted from the resulting LPIL benchmark request.
- `optimization/export_prompt.py` exports the same request builder used by the
  runner without performing generation, running trials or mutating a session.

The reusable builder supports custom output documents. The current Workbench
executor remains the Array move pilot with a system/user candidate pair. No new
task-editor UI or arbitrary-artifact benchmark executor was added. Delimiter
collisions inside arbitrary data remain the stated LPIL limitation, not a claim
that the language is collision-proof.

## First request

Exported from session `adb9ec46f7bb48bdb84cc276a7f3298a`, which has zero candidates
and 15 baseline observations across five saved model configurations and three
presentations. Baseline remains 5 passes out of 15 observations.

`first-run-prompt.txt` contains only the single user message, with no export-tool
heading or shortened excerpts. It includes three distinct captured source prompts
once each, all 15 responses, and the full 20,331-character timeout output. Its
current content is 130,115 UTF-8 bytes, compared with 1,055,967 bytes in the old
two-message content (about 88% smaller).

An independent local tokenization check used the official Qwen/Qwen3.5-9B
tokenizer and the exact saved runtime chat template. That template matches the
official template byte for byte. With the session's reasoning enabled, the old
request is 291,830 tokens and the corrected request is 42,968 tokens. Including
8,192 reserved output tokens gives 51,160, within the initial 65,536-token
allocation and the model's 262,144-token maximum. This check loaded no weights
and generated no candidate. The actual GGUF runtime still verifies its own count
before inference. The tokenizer revision and file hash are in the exported
token-count diagnostic.

## Verification

- 25 new LPIL/feedback regression tests pass, including the five supplied nesting
  examples, one-level changes, syntax errors, configurable counts, custom output,
  opaque data, exact request/output preservation, immutable export and baseline
  reuse on a legacy preparation-failure resume.
- The existing 47 optimizer tests pass after adapting the mock writer's response
  to the LPIL contract.
- Real Edge/HTTP optimizer smoke passes with simulated inference, including tab
  loading, settings, candidate generation/evaluation, ranking, resume and archive
  export/import.
- Sharing metadata validation passes: 61 definitions, 179 variants, 574 scopes.
- After the complete prompt review below, the full repository test suite passes:
  612 tests in 731.872 seconds, exit 0, recorded in
  `.local/lpil-reviewed-full-suite.log`. This includes the 25 new regressions.
  The Edge/HTTP optimizer smoke was also repeated successfully with simulated
  inference, recorded in `.local/lpil-reviewed-browser-smoke.log`.
- `git diff --check` passes. A final comparison confirms the exported text equals
  the runner's next request, all 15 captured outputs and three source requests are
  preserved exactly, and the saved source session remains unchanged by export.

Prompt-writing elapsed-time and socket timeouts remain disabled. Native and
Perchance benchmark deadlines and the frozen model/test cohort are unchanged.
No real optimization candidate or additional benchmark run was started.

## Complete prompt review

After Isaac explicitly requested a review of the file before delivery, the full
request was checked against the supplied LPIL files, the frozen Array move task,
all saved trial evidence, the candidate parser and the actual runtime builder.
The review found and corrected these points:

- The task no longer claims all tested providers have reasoning disabled. Local
  runs request reasoning off; Perchance's setting is unverified. Captured reasoning
  settings and actual benchmark deadlines now appear in each trial's metadata,
  including the null setting on the incomplete timeout record.
- The scoring explanation now distinguishes an unsuccessful timeout from a
  deterministic semantic failure, and explains `INCONCLUSIVE`, `not_evaluated`,
  missing coverage and unconfirmed sampling controls.
- Marker examples are quoted as exact syntax, with explicit instructions to emit
  actual unquoted deferred markers exactly once. The output instructions also
  explicitly allow an empty system message while requiring both headings and a
  nonempty user message.
- The request names its saved testing scope and starting model, explains the
  origin gate followed by complete task-type testing, and explicitly reports that
  there are no previously generated top-three candidates yet.

The review compared all 21 literal blocks against the original three captured
requests (six role messages) and 15 outputs, including the full timeout partial.
No literal boundary collisions occur in this request. Both a user-only candidate
and a system/user candidate were parsed and bound across all three frozen input
presentations. The resulting requests contain the exact data values once each.
The supplied LPIL source files match the ZIP byte for byte except for Isaac's
requested sentence deletion from the general description. Every file
in the saved source session has the same SHA-256 before and after review/export.

The rebuilt text file and API-message sidecar exactly match the runner's request.
Its SHA-256 is
`ae7774e289aa365180b4586d8a4c8b0c282af1fd3a18c6bfbf0d279900db67bd`.
The reproducible checks and their result are saved beside the prompt as
`review_first_prompt.py` and `first-run-prompt.review.json`. The token diagnostic
has been refreshed for this exact message. This is a review of the request and
its execution contract; no live candidate generation was performed.
