# Ember typed-line method v1

This method uses the actual normal EmberAdventures response grammar, not an
invented shorthand inferred from a voice description. The authoritative checkout
is `E:\Users\Isaac\EmberQuest`, commit
`ceb01d2c2898576fdefec7ee4790ad0bcdb85497`. `SOURCE_BUILD.md` identifies `src/`
as authoritative. The exact `src/contracts/ai-response-text.js` is retained in
`tests/fixtures/ember_source/ember_ai_response_text_v1.js`; its provenance JSON records
the original CRLF byte hash; Git stores the same source with LF line endings. The Python parser is checked against that JavaScript implementation.
The general consumer is `src/scripts/app/11a-state-text-contract.js`, which calls
`parseCompactAiPatch` in `26-objective-suggestions.js`. The specialized participant
blocks in `11b-focused-state-text.js` are a separate, domain-specific contract and
are not presented as a general database operation language.

## Exact syntax and processing

An operation line (`set`, `append`, `change`, or `remove`) names an exact slash
object path. All except remove take one immediately following typed value line:
`text`, `number`, `boolean`, `null`, `list`, or `object`. No-change is `none`.
Path components use ~1 for slash and ~0 for tilde. Empty components and the exact
prototype-related field names rejected by the source remain rejected. There is
no dot-path, JSON-string-selector, or invented ID-path alternative.

Text values are literal, including colons, quotation marks, backslashes and
JSON-looking text. There is no JSON escape processing for text. Actual multiline
text has no representation in this grammar. The source trims the whole response;
its final text-line trailing whitespace therefore cannot round-trip. The parser
preserves that behavior; the synthetic reference emitter rejects values it cannot
represent exactly. Numbers use the source's finite decimal grammar and JavaScript
number interpretation, not exponent syntax or arbitrary-precision integer claims.

The source groups all sets, then null/removes, then appends, then numeric changes;
within each group order is preserved. This grouping is retained. The source's
remove operation becomes a **null assignment** in the consumer, not JSON Patch
deletion. Move and Copy do not exist. Empty container labels are legal syntax,
but building objects/lists needs extra records and often positional list indexes.

The study adapter lowers supported records through the existing strict
`value_patch` operation roles, fixed schema, uniqueness checks and final-state
oracle. It does not copy game-specific aliases, calendar rollover, relationship
clamping, scene-name resolution or membership deduplication into benchmark data.
It never silently reinterprets remove as collection-element deletion. It does not
invent ID selection or positional tasks to expand coverage. Unsupported compound
construction is reported rather than replacing a whole collection.

## Unchanged tasks and explicit exclusions

| Existing fixture | Presentations | Observations/model |
| --- | ---: | ---: |
| Update an existing object field | Normal JSON, Full paths | 6 |
| Append a unique primitive value | All three | 9 |
| Append a unique primitive value to an empty collection | All three | 9 |
| No change for unrelated information | All three | 9 |
| Total | 11 requests, 3 repetitions each | 33 |

The other 17 fixtures remain listed with explicit reasons in the export manifest:
three ID-selected element Update fixtures, two complete-object Append fixtures,
four collection-element Remove fixtures, four Move fixtures and four Copy fixtures.
Their schemas, oracles and task meanings are not simplified to make this method fit.

Normal JSON and ID-keyed-array input data use the existing renderers. Native Full
paths show actual object paths; a collection is a complete JSON value on its own
line, not a set of unsupported element selectors. The data and semantic oracle
are unchanged. This presentation difference must be reported; an end-to-end method
comparison is not evidence that the output delimiter alone caused a difference.

The retired exporter produced four separate definitions, eleven requests, synthetic
references, provenance and the unsupported ledger. Its frozen definitions and
references are preserved in `archives/prompt-builder-inputs/frozen_definitions.json`;
the executed experiment retains its exact requests under
`experiments/ember-text-v1/runs/unity-revised-20261103`. Saved definitions run without
the old builder. New test construction uses `prompt_builder`; earlier results and
source-contract evidence remain unchanged.

## Review and comparison

Before a live run, read all eleven fully rendered requests and verify their actual
input values, paths, instructions, examples, typed parsing and unchanged semantic
requirements. Syntax examples must use disjoint example fields, never an expected
fixture patch. Independent checks use the source JavaScript parser and handwritten
responses as well as the existing semantic oracle. Exact request digests and review
observations belong in the run manifest. Isaac has authorized this review and the
sequential supported Unity trial; do not ask him to approve our review work.

Compare against **the same eleven requests/33 observations per model** from the
corrected dot cohort, by fixture, presentation and repetition. Do not compare a
33-observation percentage with a full 186-observation percentage. The four existing
Unity 12 GB configurations imply 132 new observations, after the current corrected
cohorts finish. No new paid provider, desktop GPU run, Move/Copy extension or OPRO
round is part of this method.

Existing methods enter no new parser branch. Their exact compiled definitions,
requests and oracle outcomes are checked before/after integration. Any reviewed
workflow-fingerprint compatibility entry must name the exact extension source
hash and explain that new behavior is reachable only through `ember_text_v1`.
The new parser itself is included in raw implementation provenance so later edits
cannot silently reuse method results.

## Completed Unity 12 GB research trial, 2026-11-03

The revised typed-line / field-value method completed 132 fresh observations:
four fixtures, eleven presentations, three repetitions, four existing Unity
configurations. Exact rendered requests were read by Codex and independently
reviewed by the coordinating thread before launch. Unsupported-operation and
evaluator bookkeeping stayed outside the final model instructions.

| Configuration | Corrected dot baseline on matching 33 cells | Typed-line method | Typed-line job |
| --- | ---: | ---: | --- |
| Qwen3.5-9B Q4_K_M | 33/33 | 27/33 | 66559293 |
| Qwen3.5-9B Q8_0 | 33/33 | 33/33 | 66559294 |
| Qwen3.5-27B UD-IQ2_XXS | 33/33 | 33/33 | 66559298 |
| Qwen3.5-27B IQ2_M | 30/33 | 33/33 | 66559335 |

The six new Q4_K_M failures were no-change cases: the model used unrelated
documentation text to rename inventory items in the ID-keyed and Full paths
presentations. All 24 mutation observations passed. IQ2_M's three baseline
failures surrounded an otherwise correct primitive append with JSON code fences;
the typed-line responses passed. These are observed model-dependent tradeoffs,
not evidence that one format is universally superior. Wrong answers were retained
without selective retries.

All four runs qualified on actual 12 GB TITAN X GPUs with full GPU placement,
32K context and f16 KV. Sampled peaks were 6.260, 9.419, 10.303 and 11.149 GiB in
the table's order. Matched records use the same artifact identities, runtime
version, requested sampling and recorded target metadata. Full paths rendering
differs between methods, so this comparison does not isolate the output delimiter.

The other 17 fixtures remain explicitly unsupported. A 33-cell result is not
full-suite coverage. The corrected dot cohorts separately cover 186 cells each
with 183, 156, 150 and 129 passes; 744 total observations include 447 new and
297 retained exact-compatible observations.

Audited raw records, matched baseline copies, exact prompts, frozen source,
qualification reports and regression logs are in
`experiments/ember-text-v1/runs/unity-revised-20261103/manifest.json`.
Baseline copies are labeled as copies and do not count as new observations.
The final regression outcome is recorded in that manifest. An earlier 782-test
run had one Windows WinError5 in unchanged optimizer atomic persistence; the
isolated test passed. No desktop inference, project commit or push was performed.

