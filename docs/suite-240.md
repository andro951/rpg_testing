# Paired 240-case suite

40 substantially varied synthetic starting states, each used independently for Update, Append, Remove, Move, Copy and no-op. No arm starts from the output of another arm. The state recipes are authoritative and the generator reproduces the five-file source cases. Expected states are independently mutated and cross-checked against evaluator application; they never enter model prompts.

The original 21 cases and historical evidence remain frozen in archives/suite-before-240-2026-11-15. The first 13 successor states retain their meaningful actions and data while adding collections/scalar update targets as needed for six-arm pairing. The original profile-only no-array control is archived, not misrepresented as still array-free.

| State | Distinct coverage | Original cases retained |
|---|---|---|
| 01 baseline_nested_destination | Repeated display names, flat source and nested destination | update_record_field, append_record, remove_record, no_change |
| 02 empty_record_destination | Empty destination and singleton source | append_record_to_empty_array |
| 03 primitive_nested_destination | Primitive strings, nested destination | append_value, remove_value |
| 04 empty_primitive_destination | Empty primitive target | append_value_to_empty_array |
| 05 record_populated_transfer | Flat record transfer with populated destination | move_record, copy_record |
| 06 record_empty_transfer | Flat record transfer with empty destination | move_record_to_empty_array, copy_record_to_empty_array |
| 07 primitive_populated_transfer | Primitive transfer with populated destination | move_value, copy_value |
| 08 primitive_empty_transfer | Primitive transfer with empty destination | move_value_to_empty_array, copy_value_to_empty_array |
| 09 singleton_record | Removal empties record source | remove_last_record |
| 10 singleton_primitive | Removal empties primitive source | remove_last_value |
| 11 profile_fields | Object scalar update preserved; original no-array control archived | update_field |
| 12 nested_record_fields | Nested field on selected record | update_nested_record_field |
| 13 nested_inventory | Both collections nested under inventory | update_record_in_nested_array |
| 14 boolean_flags | Boolean true/false values, repeated non-ID fields | New |
| 15 nullable_fields | Null update and nullable complete elements | New |
| 16 decimal_balances | Negative and fractional numbers | New |
| 17 large_integers | Large integers within supported exact JSON range | New |
| 18 empty_strings | Empty string distinct from missing/null | New |
| 19 whitespace_literals | Leading/trailing whitespace preservation | New |
| 20 unicode_text | Multiscript and emoji scalar payloads | New |
| 21 quote_backslash | Quote and backslash escaping | New |
| 22 delimiter_payloads | Format-like tokens remain data | New |
| 23 multiline_preservation | Multiline data preserved inside complete elements; scalar update remains all-format representable | New |
| 24 deep_scalar | Three-level field nesting | New |
| 25 wide_records | 18 payload fields plus an ID challenge complete copy without losing siblings | New |
| 26 large_collection | 48-element source, target near middle, repeated groups | New |
| 27 deep_collections | Six-level collection path | New |
| 28 cross_branch_transfer | Transfers across separate root branches | New |
| 29 overlapping_destination_ids | Non-target ID repeats across collections; selected target unique within each destination | New |
| 30 duplicate_display_names | Six identical name/role distractors selected only by ID | New |
| 31 heterogeneous_scalar_fields | String tokens vs booleans/numbers/null in different fields | New |
| 32 empty_nested_objects | Empty objects retained on append/move/copy | New |
| 33 integer_values | Primitive integer identity, not index | New |
| 34 negative_decimal_values | Signed fractional primitive identities | New |
| 35 boolean_values | Boolean primitive identities and null append | New |
| 36 null_value | Null primitive source selection | New |
| 37 long_primitive_collection | 64 strings, target in middle | New |
| 38 unicode_primitive_values | Unicode primitive identities | New |
| 39 numeric_string_values | Leading-zero identities remain distinct strings | New |
| 40 collections_inside_selected_record | Nested arrays selected through parent IDs; repeated child ID in other parent | New |

## Scope

240 cases × 3 input presentations × 6 output formats = 4,320 prompts per model before workflow conditions or repetitions. Two distinct self-check conditions would make 8,640 trials/model; this file does not claim such a run was performed.

Safe-number boundary values remain within the evaluator’s supported JSON integer range. Multiline strings are tested inside complete elements and unchanged data, not as unsupported typed-lines scalar text payloads. Primitive values include signed fractions, booleans and null. Collection identities are declared privately for every array, including nested arrays under selected parent elements.

Regenerate: `python scripts/generate_paired_suite_240.py`. Validate: `python -m unittest tests.test_paired_suite_240 -v`. No inference is started by either command.

## Structural dimensions

| State | Array sizes (including empty) | Maximum tree depth | Maximum object field count |
|---|---|---|---|
| 01 | [4, 0] | 3 | 3 |
| 02 | [0, 1] | 3 | 3 |
| 03 | [3, 0] | 2 | 3 |
| 04 | [0, 1] | 2 | 3 |
| 05 | [4, 1] | 3 | 3 |
| 06 | [4, 0] | 3 | 3 |
| 07 | [3, 1] | 2 | 3 |
| 08 | [3, 0] | 2 | 3 |
| 09 | [1, 1] | 3 | 3 |
| 10 | [1, 1] | 2 | 3 |
| 11 | [2, 0] | 3 | 4 |
| 12 | [3, 0] | 4 | 3 |
| 13 | [4, 0] | 5 | 3 |
| 14 | [3, 0] | 3 | 2 |
| 15 | [2, 0] | 3 | 2 |
| 16 | [3, 0] | 3 | 2 |
| 17 | [2, 0] | 3 | 2 |
| 18 | [2, 0] | 3 | 2 |
| 19 | [2, 0] | 3 | 2 |
| 20 | [2, 0] | 3 | 2 |
| 21 | [2, 0] | 3 | 2 |
| 22 | [2, 0] | 3 | 2 |
| 23 | [2, 0] | 3 | 3 |
| 24 | [2, 0] | 5 | 2 |
| 25 | [3, 0] | 3 | 19 |
| 26 | [48, 1] | 3 | 3 |
| 27 | [2, 0] | 8 | 2 |
| 28 | [2, 0] | 4 | 2 |
| 29 | [3, 2] | 3 | 2 |
| 30 | [6, 0] | 3 | 4 |
| 31 | [2, 0] | 3 | 5 |
| 32 | [2, 0] | 3 | 3 |
| 33 | [5, 2] | 2 | 3 |
| 34 | [3, 0] | 2 | 3 |
| 35 | [2, 0] | 2 | 3 |
| 36 | [3, 1] | 2 | 3 |
| 37 | [64, 0] | 2 | 3 |
| 38 | [3, 0] | 2 | 3 |
| 39 | [4, 0] | 2 | 3 |
| 40 | [2, 2, 0, 1, 0] | 5 | 3 |

All 21 retained action requests preserve the original requested_change.txt text exactly. New requests describe field/collection/ID selectors in prose, not prewritten output paths.

## Run matrix and execution status

- 240 cases × 3 input presentations × 6 structured output formats × self-check off/on = **8,640 workflow observations per model** at one repetition. There are 4,320 initial task/presentation combinations and 1,440 case/output definitions.
- Self-check off generates one answer. Self-check on uses the pre-existing `retry_enabled` workflow, retains the full original conversation plus answers/reviews, asks `Does this answer look correct? Yes or no.`, and permits at most three full-answer revisions when the model says no. A final fourth check records model acceptance or exhaustion. Ambiguous checks stop with the current answer unendorsed and still grade that answer normally, preserving the existing self-review protocol. All raw answers/checks/revisions are saved; no evaluator or reference-answer feedback enters the model's decisions.
- At most 38,880 generation calls per model are possible (4,320 off calls + 4,320 on workflows × 8 calls). These are not additional independent observations. Provider capability controls and configured repetitions still apply.
- Building, reference checks and mocked workflow tests are **not model inference**. At implementation time this cloud checkout has no configured models, GPU/model weights, or Unity worker configuration. No real model run has started in the cloud. Isaac explicitly authorized execution on his desktop after publishing. Read-only inspection verified five installed local model files, an actual 8 GB GTX 1080 (Perchance eligible), saved runtime/browser dependencies and four configured Unity model entries. Remote Unity availability and actual run progress must still be verified.
- Use the supported `Controller.run(selection=None)` route after successful preflight, with the intended committed source stable, so result-sync journaling and resume remain active. Do not substitute a demo/mock run or bypass provider restrictions. User-computer access requires specific permission.

### Preserved desktop work

The desktop had an unpublished prior commit, `935f0a6f`, implementing bounded self-review. It was transferred by a verified Git bundle and merged, preserving its provenance and behavior rather than replacing it with a second implementation. The new on/off matrix uses that existing `retry_enabled` protocol. See [self-review-retries.md](self-review-retries.md).

## Deterministic validation (not model results)

- Archive SHA-256 verification: all 2,627 preserved files match their recorded original bytes.
- Generated and installed 1,440 definitions/8,640 workflow conditions with complete coverage, no unsupported combinations or input exclusions.
- Paired-state checks verify 40 canonical states, six arms each, all 21 preserved original task texts and representative expected patches, and all 1,440 case/output compatibility checks.
- Preserved original self-review disabled-parity tests still cover 372 original prompts using frozen inputs.
- 44 focused integrated tests passed after adopting the existing desktop self-review implementation, including walltime, uniqueness, pairing and review behavior. Full regression: `python -m unittest discover -s tests -v` ran 1,147 tests in 730.779 seconds, passing with one skip. These checks are synthetic and not benchmark observations.

## Requested execution placements

Desktop inspection verified five installed local configurations and eligible Perchance on the actual 8 GB tier. Read-only SSH checks verified four configured Unity model files/runtimes and an empty user queue. The requested ten model/placement entries therefore represent 86,400 workflow observations before exact-compatible completion reuse. Jobs retain one model per GPU/job, distinct inference ports and durable evidence. The approved run may request Unity walltime `5-00:00:00` within the observed partition limit; the software default remains four hours. Verification of readiness is not proof that any inference has started.
