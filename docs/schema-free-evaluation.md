# Schema-free evaluation for template-built tests

New template builds explicitly select `schema-free-intent-v1`. This selection is
not a change to archived strict, schema-backed, or live-intent definitions.
Generated definitions do not need `state_schema`, a `schema.json` file, or a
model-facing database-structure section.

## Compiler contract

A compiled variant uses:

```python
from evaluation.schema_free_intent import configuration
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
`normalize_response(raw, initial_state, output_format='json_dot')`. No expected
state, expected patch, schema, task wording, or prompt is an input. Reference
patch application and comparison happen separately, after model normalization
and final-state scoring.

## Array identities without a schema

At each current collection, an object array must have exactly one shared scalar
field named `id` or ending in `_id` whose values are unique. Examples include
`item_id` and `person_id`. Unrelated unique values, such as a name or count, are
never guessed to be identifiers. No particular ID-named field wins when
multiple candidates qualify. This is an explicit implementation limitation:
custom names such as `key` or `sku`, and ambiguous ID-bearing records, require a
future explicitly designed identity contract rather than hidden case metadata.

Object shapes may differ. Adding a new object does not require it to have the
same fields or field types as existing elements. Empty arrays carry no inferred
object/primitive type or ID-field declaration: the incoming value establishes
what is present. New nested arrays are validated by the same general rules.
Arrays cannot mix objects and primitive values, contain arrays directly, or have
duplicate identities. Plain selectors with colliding typed spellings, such as
`1` and `"1"`, are rejected rather than guessed. Identity inference is checked
against every sequential resulting state; a collection must remain unambiguous.

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
- `typed_lines`: the existing typed-line source grammar and application order,
  restricted to scalar updates through object paths, primitive-value append,
  and no-change. It does not acquire array-element targeting, complete-object
  append, or collection-element deletion merely because it has a new label.
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
python -m unittest tests.test_schema_free_intent tests.test_current_live_intent tests.test_value_diagnostics -v
python -m tests.schema_free_report_browser_smoke
```

These checks use synthetic responses, not real model inference. The browser
smoke includes repeated opening/closing, reload, narrow-screen visibility, and
unchanged pass totals. It needs a working local Chromium or the
`REPORT_BROWSER_EXECUTABLE` environment variable.

The new source fingerprint normalizes checkout line endings and does not include the Python patch version, so unchanged definitions load across supported desktop/Unity environments. The actual Python version is retained in each normalization result as runtime provenance. Historical dot-intent-v1 fingerprint rules are unchanged.
