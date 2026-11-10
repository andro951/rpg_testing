# Live current-contract intent evaluation

This integration is explicitly selected. Existing definitions without
`result.evaluator` keep strict scoring. No saved response, saved score, approved
prompt, frozen runner or frozen source directory is rewritten.

## Scope and source

The maintained research contract is `dot_patch_v1` / `research_json_v2`:
updates to existing object fields, additions to existing arrays, removal of an
ID/value-selected array element, and explicit no change. Selection is never by
position. Array order, fixed schemas, declared per-collection ID fields,
uniqueness and ambiguous typed-selector rejection remain enforced.

The generic Python, JavaScript and C# library remains broader. The new Python
research host does not enable Move/Copy, generic Set/Replace aliases, an RFC
input bridge, whole-record replacement, or inferred values. Its scoped
`replace` spelling is the existing research operation name.

The root `test_specs/` is the historical 21-definition / 62-variant five-operation
suite, **not** the current overnight round. Supply the exact current definition
directory to the preparer. The eight frozen overnight rounds contain 1,680
model/arm-specific definitions, 4,960 variants and 14,880 configured observations.
Each round includes regression, selection and reserved-final roles; those roles
must remain separate in retrospective reports. The latest round has 210
definitions, 620 variants and 1,860 observations. These are coverage denominators,
not newly executed model trials.

`intent-live-source-snapshot.json` records the narrow maintained dependencies
needed by the published checkout. Native port selection and filtered Perchance
companion planning/setup are retained. Unrelated later optimizer, coverage-resume
routes and UI features were not imported. This is not a whole-app parity claim.

## Select a new live run without changing prompts

Run from this implementation's checkout, using a Python environment with the
repository requirements installed. These commands only prepare a new directory
and then, separately, expose the normal Workbench UI:

```sh
python -m workbench.live prepare \
  --definitions CURRENT_ROUND/desktop/test_specs \
  --output NEW_RUN \
  --evaluator dot-intent-v1 \
  --test EXACT_TEST_ID

python -m workbench.live serve --root NEW_RUN --port 8787
```

Omit `--test` only when the entire source directory is intended, or repeat it
for an explicit subset. Current overnight definitions are model/arm-specific:
select the corresponding model and test scope in Workbench. Preparation is not
authorization to run inference. Serving does not press Run. Configure the model
folder/runtime using the existing setup workflow before an authorized run.

For a separately prepared strict control, use `--evaluator strict-json-v1`.
An existing output directory is never overwritten. Source definitions, steps,
prompts and source rejections are preserved. Source sync and result publication
start disabled in the new root. The existing app's eligible 8 GB Perchance
companion/setup-consent behavior remains; an old cohort's decline is not silently
carried into a new run.

Do not start an old frozen `overnight.py` expecting it to load this implementation:
it intentionally keeps its own frozen source. No frozen round was upgraded or
reopened by this integration.

## How grading works

The normal Controller → Session → monitored execute → workflows execute/evaluate
path now recognizes an explicit result evaluator object:

```json
{"version": "dot-intent-v1", "fingerprint": "GENERATED_SOURCE_FINGERPRINT"}
```

Use the preparer/API to generate the fingerprint; do not copy a placeholder.
It pins parser/host/scorer sources, the generated grammar specification, and Python and jsonschema versions. Unknown,
stale, malformed, non-dot or constrained-final-output selections fail before a
normal live backend call. Selection changes experimental definition and case
identity; an old strict observation cannot fulfill an intent-mode case.

The host receives only the original textual response, initial state and state
schema. It parses once, resolves paths sequentially against copied state, and
returns a canonical dot patch and final state. Final-state grading, required
operation checks and response-schema checks all use that same normalized result.
The expected state is consulted only afterward by the ordinary scorer.

Raw calls and outputs stay unchanged. Scores separately record evaluator
version/fingerprint, parser diagnostics, normalized patch and raw-output hash
when normalization succeeds. Normalization failure is a completed wrong answer,
not a reason for selective inference retries.

The host preserves lexical dot boundaries: percent escapes and JSON-quoted
components stay explicit, while literal unescaped separators use the reviewed
unique state/schema resolver. Explicit grouped components remain literal.
JSON values, including numeric integer/float spellings important to plain
selectors, are not rewritten. A no-change result must be an explicit empty
array, optionally enclosed in the supported fence; blank text, lone brackets,
separator-only output and empty non-array groups do not count as no change.

The generic parser defaults remain unchanged. Two private Python host hooks
preserve lexical path and value information; model output cannot configure them.

## Verification and immutable replay

```sh
python -m unittest tests.test_current_live_intent tests.test_native_ports -v
python -m unittest discover -s tests -v

python scripts/audit_current_live_intent.py \
  --baseline-root MAINTAINED_CHECKOUT \
  --night-root FROZEN_OVERNIGHT_ROOT \
  --output NEW_AUDIT_DIRECTORY \
  --phase references \
  --freeze-id RECORDED_CODE_FREEZE \
  --expected-fingerprint RECORDED_EVALUATOR_FINGERPRINT
```

The reference phase uses only a fake backend, checks all selected current
reference responses plus independent negatives, and compares strict scores,
prompts, identities and terminal resume behavior with the maintained baseline.
The replay phase additionally verifies captured definitions, file hashes,
checksums, request digests and role labels before reading saved outputs.
Both phases require a frozen implementation and exclusively new output folders.

Reserved-final outcomes are retrospective validation only, never selection or
normalizer tuning. A timed-out record stays incomplete and terminal. Original
evidence and source hashes are checked again after the audit. Detailed local
audit inventories and outputs are not public repository artifacts.

See the accompanying validation report for executed counts and limitations.
