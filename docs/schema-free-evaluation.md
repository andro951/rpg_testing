# Schema-free evaluation for template-built tests

New template builds explicitly select `array-identities-intent-v3`. This selection is
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
The normalizer uses the explicit ID mapping as validation context, not a full schema. No expected state,
expected patch, task wording, or prompt is an input. Reference patch application
and comparison happen separately after normalization and final-state scoring.

## Array identity pseudo-schema and permitted uses

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

The mapping is not inserted into model messages, template bindings, schema
explanations or OPRO generation. The user explicitly permits the ID-keyed and
full-path input conversions to consult it internally when choosing array IDs.
These two conversions use the declared exact field rather than guessing from
`id`/`*_id` names. Their resulting keys/path segments necessarily express that
identity; all original fields and values remain present. Missing or invalid
identity declarations fail clearly, without fallback guessing.

Normal JSON presentation needs no mapping. The separate experimental named-table
view is outside this permission and retains its data-only convention: one
unambiguous unique scalar `id` or `*_id` field in starting data. Current-case
prompts remain byte-identical because their declarations name the same IDs.

The old `schema-free-intent-v1`, `ember_text_v1`, and `field_value_v2` runtime decoders are retired. Archived definitions and stored scores remain preserved; these retired contracts cannot be executed in the current checkout. The new version and frozen mapping change experiment
identity even when model messages are unchanged; prior observations are not
relabelled or reused as new results.

Object fields are selected by name. Array elements are selected by ID/value,
never by position. Operations run sequentially. Update targets an existing
object field, Add targets the collection itself, and Remove targets a collection
element. Move and Copy select a source collection element and a different destination collection. Both append a deep copy of the complete source value, keeping its ID; Move also removes the original. Same-collection transfers, transfers into source descendants, and duplicate destination identities are rejected. Whole-array replacement and adding/deleting existing-object fields remain unsupported. All changes are atomic
from the caller's perspective: rejected operations never mutate initial data.

## Six current structured formats and two explicit alternatives

- `json_dot`: JSON operations and generic intent-parser recovery, with dot paths.
- `json_slash`: JSON operations with typed slash selectors, including quoted
  string IDs and embedded slashes. These are not RFC positional array paths.
- `path_list`: one-line operations with unquoted, percent-encoded path steps and
  complete JSON values.
- `literal_line`: one-line `text:`/`json:` values with the documented text escapes.
- `end_marked_line`: one-line text values ending in `|`; earlier pipes and spaces
  remain literal value data.
- `two_line_text` (historical, explicit selection only): operation line followed by a complete `value:` JSON literal.
- `typed_lines`: the new host extends the source protocol with ordered execution,
  typed JSON-scalar slash selectors, complete `object: {JSON}` / `list: [JSON]`
  values and array-element removal. `remove` has no value line; a selected array
  element is deleted, while an existing scalar object field is nullified for
  compatibility. `set` plus `null:` explicitly assigns null. Existing-object-field
  updates (including object values), complete-element append (including empty collections), numeric
  change, custom `move`/`copy` followed by a destination `to:` line, and `none` are supported. Extra value lines and wrong typed payloads
  are rejected. The grammar produces ordered semantic instructions; no typed-line-specific model decoder remains.
- `free_format` (experimental, explicit selection only): no output syntax is prescribed by the prompt. Recognizable
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

Compilation separately checks that the named-table view’s independently chosen IDs agree with the validator declaration. ID-keyed and full-path views select directly from the declaration, including inside nested or empty arrays. Normal JSON presentation remains independent of the mapping; compiling a validated test still requires valid evaluator metadata.

## Migration verification (2026-11-10)

The prior template suite from commit `c5fa3eee` is preserved byte-for-byte in
`archives/template-builds/53af41e35d1e57ec/`: 13 definitions and 77 generated
preview/manifest files. All 38 default `json_dot` message lists remain exactly
unchanged. The selected evaluator and frozen ID metadata intentionally change
experiment identity, so this is not a claim of scoring equivalence.

The synthetic reference test covers 408 case/input/output combinations: 13
cases, four available input presentations (three for the no-array case), and
eight output protocols. This includes the nine case/output pairs previously
unsupported by `typed_lines`. At that historical checkpoint, the selected default was 13 definitions and
38 prompts, or 114 observations with three configured repetitions. These are
compiler and evaluator checks, not model measurements.

Old saved responses and scores are untouched. Historical executable definitions
with old source fingerprints must use their original matching repository
revision; no compatibility alias silently accepts an old pin with new code.

## Full five-operation coverage (2026-11-11)

The 21 current cases contain four Update, four Append, four Remove, four Move,
four Copy, and one no-change case. The eight transfer cases were restored from
preserved task/data definitions into the current templates without restoring
full schemas or model-facing schema descriptions. Each case has a separately
stored reference patch and expected final state.

The standard build covers six active structured output formats and three input
views (two for the no-array field update): 62 case/input pairs × six formats =
372 distinct prompts. The current default is one repetition, so there are 372 observations per model. Extra repetitions can be explicitly configured; three would produce 1,116. Historical and already-frozen runs keep their recorded repetitions.
Those are coverage counts, not measured model results. Historical two-line and
experimental free-format prompt styles remain explicitly selectable through the same grammar. No model run is
started by a build, an installation, or a synthetic reference check.

The required catalog and format status metadata guard full-suite selection.
Build manifests distinguish requested, produced and omitted coverage, format
status, distinct prompts, repetitions and observations. Explicit subsets remain
possible for targeted experiments but cannot silently replace the full suite.
A missing required case or unsupported full-suite combination is an error, not
an excuse to report a smaller number as full coverage.

Transfers use the same canonical reference objects in every output arm:
`{"op":"move","from":"items.item-a","path":"storage"}` (or `copy`).
JSON slash output uses typed slash paths for both fields. Path-list output uses
`move [items, item-a] -> [storage]`. Literal/end-marked lines use
`move items.item-a -> storage` without a value or text end marker. Two-line
output uses `move: items.item-a` followed by `to: storage`; typed lines use
`move: /items/"item-a"` followed by `to: /storage`. Copy uses the same forms.

That historical v2 migration intentionally changed evaluator identity. The current v3 migration retires v1/v2 execution in this checkout; their captured scores remain viewable without replay. Prior raw observations, prompts and archived answers stay unchanged.


## Shared grammar migration (2026-11-11)

All six current output formats now enter `parse_intent_with_diagnostics` in
`intent_parser/parse.py`. The authoritative source is
`intent-parser-js/intent.grammar`; generated rules are shared by Python, C#,
and JavaScript. `evaluation/output_formats.py` is only the common entry point
and lexical-path adapter, not a collection of format-specific parsers.
The old line-record and typed-line decoders were deleted, including the retired
research `ember_text_v1` and `field_value_v2` decoders. Reference encoders that
create synthetic tests are not model-response readers.

The requested format still identifies how an explicit `text:` literal is
encoded: raw text in typed lines, escaped text in literal lines, and escaped
text with a final pipe in end-marked lines. These are value interpretations,
not alternate operation grammars. Exact text, quoted strings, nested objects,
array contents, and operation order are preserved. `none` and `[]` explicitly
represent no changes. Empty or unrecognized responses are never invented patches.

Entirely unquoted bracketed path lists are the documented textual-selector format: `[strings,42]` names the unique textual ID `42`. If a grouped path contains a quoted component, its scalar values retain explicit JSON types, so `["strings",42]` cannot select string ID `"42"`. Quoted strings never match numeric or boolean IDs by coercion. This lexical precedence preserves the existing unquoted path-list prompt contract; typed identity collisions in a collection still reject.

Slash paths preserve quoted JSON scalar types. A bare non-JSON spelling such
as `/locations/town-a` may select the unique string ID `town-a`; a numeric path
part is still an ID, never an array position. Duplicate identities, typed
identity collisions, ambiguous dot paths, unresolved source/destination roles,
and extra operation payloads reject. Neither the expected patch nor the expected
final state is available to parsing or identity resolution.

The literal word `add` retains a semantic marker until the target is resolved: it appends to an array or updates an existing non-array object field. `append` and `insert` remain array-only. Missing targets, root/whole-element updates and ambiguous paths reject.

State-dependent work remains outside grammar: resolving declared IDs, checking
array destinations and duplicate IDs, executing numeric deltas, compatibility
nullification for typed scalar removal, and enforcing data preservation. Grammar
cannot determine these without the actual input document. Literal escape
interpretation and bounded ambiguity/resource checks are also procedural.

Version v3 deliberately changes scoring identity. Old v1/v2 pins fail validation
before normalization; old saved scores and raw evidence remain unchanged and
readable. This change does not rescore a completed observation or modify a
running frozen experiment. A new-parser comparison must be a separate, explicitly
identified analysis, never relabeled historical model accuracy.
