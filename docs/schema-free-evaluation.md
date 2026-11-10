# Schema-free evaluation for template-built tests

New template builds explicitly select `array-identities-intent-v1`. This selection is
not a change to archived strict, schema-backed, or live-intent definitions.
Generated definitions do not need `state_schema`, a `schema.json` file, or a
model-facing database-structure section.

## Compiler contract

A compiled variant uses:

```python
from evaluation.array_identities_intent import configuration
test['source']['array_identities'] = [{'path': ['items'], 'id_field': 'sku'}]
variant['result'] = {
    'step': 'patch',
    'representation': 'dot_patch_v1',
    'output_format': 'json_dot',
    'evaluator': configuration(),
}
variant['expected_patch'] = [
    {'op': 'replace', 'path': 'items.item-a.count', 'value': 2},
]
```

The reference patch always uses canonical dot operations, independently of the
model's selected output format. The expected final state remains in
`test['expected_state']`. Neither is included in model prompts. Recompile after
changing a pinned evaluator dependency; stale selections fail validation rather
than silently using different semantics.

The normalizer's complete input interface is
`normalize_response(raw, initial_state, output_format='json_dot', array_identities=...)`.
The ID mapping is validator-only context, not a full schema. No expected state,
expected patch, task wording, or prompt is an input. Reference patch application
and comparison happen separately after normalization and final-state scoring.

## Validator-only array identity pseudo-schema

Each case has `array_identities.json`, frozen as `source.array_identities`:

```json
[
  {"path": ["items"], "id_field": "sku"},
  {"path": ["items", null, "tags"], "id_field": null}
]
```

Strings in a path are literal object fields, including dots, slashes and numeric
names. A `null` segment means every element in an array. `[]` denotes a root
array. `id_field` is the exact property name, or `null` for primitive-value
collections. Declare every array, including empty arrays and nested arrays
introduced by an append. Empty arrays keep their declared identity contract.
Missing declarations, duplicate declarations, duplicate identities and records
missing the declared ID are rejected, never inferred from expected answers.

Arbitrary names such as `sku` are supported; multiple ID-looking fields are
unambiguous because the map names exactly one. Other fields and object shapes
are not prescribed. Plain selectors with colliding typed spellings such as `1`
and `"1"` remain rejected. Identity rules apply after every sequential operation.

This metadata never reaches prompt assembly, model messages, template bindings
or OPRO generation. Normal JSON displays arbitrary records. ID-keyed, full-path
and named-table views retain a separate data-only convention for choosing a
display ID: one unambiguous unique scalar `id` or `*_id` field in starting data.
Those views reject unsupported records and recommend normal JSON; they do not
use the map to select a display field. Current-case prompts remain byte-identical.

The old `schema-free-intent-v1` evaluator and archived definitions retain their
original inference rules. The new version and frozen mapping change experiment
identity even when model messages are unchanged; prior observations are not
relabelled or reused as new results.

Object fields are selected by name. Array elements are selected by ID/value,
never by position. Operations run sequentially. Update targets an existing
object field, Add targets the collection itself, and Remove targets a collection
element. Whole-array replacement, adding/deleting existing-object fields, and
Move/Copy are outside this new host's operation contract. All changes are atomic
from the caller's perspective: rejected operations never mutate initial data.

## Eight executable output choices

- `json_dot`: JSON operations and generic intent-parser recovery, with dot paths.
- `json_slash`: JSON operations with typed slash selectors, including quoted
  string IDs and embedded slashes. These are not RFC positional array paths.
- `path_list`: one-line operations with unquoted, percent-encoded path steps and
  complete JSON values.
- `literal_line`: one-line `text:`/`json:` values with the documented text escapes.
- `end_marked_line`: one-line text values ending in `|`; earlier pipes and spaces
  remain literal value data.
- `two_line_text`: operation line followed by a complete `value:` JSON literal.
- `typed_lines`: the new host extends the source protocol with ordered execution,
  typed JSON-scalar slash selectors, complete `object: {JSON}` / `list: [JSON]`
  values and array-element removal. `remove` has no value line; a selected array
  element is deleted, while an existing scalar object field is nullified for
  compatibility. `set` plus `null:` explicitly assigns null. Existing-object-field
  updates (including object values), complete-element append (including empty collections), numeric
  change and `none` are supported. Extra value lines and wrong typed payloads
  are rejected. Legacy hosts keep their original grouped, restricted reader.
- `free_format`: no output syntax is prescribed by the prompt. Recognizable
  intent and explicit `none` can be applied deterministically. Unrecognized
  prose is recorded as `score.status = "parser_gap"`, `exact_match = null`, and
  an unassessed semantic outcome. It is excluded from pass/fail totals, not
  mislabeled a model failure or interpreted using the oracle. A recognized
  operation with an invalid target or result still fails normally.

No model inference, semantic guessing, expected-answer substitution, or selective
retry is part of evaluation.

## Scoring and diagnostics

Valid resulting states are compared recursively with array order ignored at
every depth. Actual state and operation order are preserved in saved evidence.
Equivalent patches, redundant operations, and valid temporary changes that are
reversed before completion can pass. Historical `required_ops` and response
schema gates do not change this new host's final-state verdict.

`expected_patch_match` compares the normalized operation list with the separately
normalized reference patch. `expected_patch_mismatch` is its inverse. Both are
null when no usable reference or normalized model patch exists. A malformed
reference patch, or one that does not produce the oracle state, is reported as
an unavailable diagnostic and cannot change the model's final-state verdict.

The results table shows a purple **≠** marker for a mismatch, without changing
cell color, pass/fail totals, or the saved score. The result detail shows the
reference and actual normalized patch separately from final-state validation.
Detailed evaluator checks mark this comparison `affects_verdict: false`.

## Deterministic verification

```sh
python -m unittest tests.test_array_identities_intent tests.test_typed_lines_extension tests.test_identity_optimizer_boundary tests.test_prompt_builder tests.test_schema_free_intent -v
python -m tests.schema_free_report_browser_smoke
```

These checks use synthetic responses, not real model inference. The browser
smoke includes repeated opening/closing, reload, narrow-screen visibility, and
unchanged pass totals. It needs a working local Chromium or the
`REPORT_BROWSER_EXECUTABLE` environment variable.

The new source fingerprint normalizes checkout line endings and does not include the Python patch version, so unchanged definitions load across supported desktop/Unity environments. The actual Python version is retained in each normalization result as runtime provenance. Historical dot-intent-v1 fingerprint rules are unchanged.

Compilation separately rejects an ID-dependent view if its data-only display field disagrees with the validator declaration, including in nested arrays. This validation gate never passes metadata to rendering or changes prompt text. Empty arrays display no selectors; normal JSON remains available for every declared ID convention.

## Migration verification (2026-11-10)

The prior template suite from commit `c5fa3eee` is preserved byte-for-byte in
`archives/template-builds/53af41e35d1e57ec/`: 13 definitions and 77 generated
preview/manifest files. All 38 default `json_dot` message lists remain exactly
unchanged. The selected evaluator and frozen ID metadata intentionally change
experiment identity, so this is not a claim of scoring equivalence.

The synthetic reference test covers 408 case/input/output combinations: 13
cases, four available input presentations (three for the no-array case), and
eight output protocols. This includes the nine case/output pairs previously
unsupported by `typed_lines`. The selected default remains 13 definitions and
38 prompts, or 114 observations with three configured repetitions. These are
compiler and evaluator checks, not model measurements.

Old saved responses and scores are untouched. Historical executable definitions
with old source fingerprints must use their original matching repository
revision; no compatibility alias silently accepts an old pin with new code.
