# Evaluator implementation review

October 8, 2026. This is the current implementation/review record; the original README, coverage and contracts preserve the planning baseline. [Machine-readable per-variant review](review.json) lists evidence checksums, cases, diagnoses and progress gates.

## Coverage

- All **42 active objective definitions / 159 variants** are registered, implemented, fixture-tested, replayed on saved outputs and reviewed. Each variant has real saved evidence.
- All **16 dialogue definitions / variants** are explicitly tracked as rubric needed; quality remains unscored.
- All **three inactive examples / four variants** have synthetic passing fixtures and workflow tests. They were not activated or run as real benchmarks.

## Evidence replay

Read and checksum-validated **1,428 immutable saved observations**. Results: **429 PASS, 766 FAIL, 42 INCONCLUSIVE timeouts, 191 UNSCORED dialogue observations**. All **1,195 comparable objective verdicts agree** with original scoring; there are no evidence problems or score disagreements. Of the 42 timeouts, 41 are objective and one is dialogue. These derived inconclusive diagnoses do not rewrite the original terminal timeout status or scores.

Reports: [replay index](../../.local/evaluation-reviewed/README.md), [summary](../../.local/evaluation-reviewed/summary.json). They are generated local artifacts; recreate with `python -m evaluation --output .local/evaluation-reviewed`. Original exact messages and raw outputs remain in the source evidence; assessments carry case IDs, definition hashes, message/text hashes and source checksums.

## Concrete reviewed example

The [actual nested-mood response](../../.local/evaluation-reviewed/assessments/75f7664292b9869b125a761cb9174fbbee885b80c406af4402f04674a8be679d.txt) was:

```json
[{"op":"replace","path":"/characters.Tom.mood","value":"relaxed"}]
```

The evaluator correctly reports valid JSON, valid operation structure, the required `replace`, valid pointer syntax and a matching proposed value. It then reports that the root key `characters.Tom.mood` does not exist, explains the corresponding `/characters/Tom/mood` pointer, and marks final-state comparison **not evaluated** because application stopped. The overall result is **FAIL**, agreeing with the original score. The value match is explicitly limited to the proposed value; it does not claim Tom was updated.

## Review against preparation requirements

| Requirement | Implementation / validation |
| --- | --- |
| Shared primitives, specific acceptance contracts | Strict parser/application/equality reused; explicit registrations, per-variant result declarations and fixtures; family requirements supplied with each assessment. |
| Clear passed/failed/unreached stages | Stable codes and operation/step scopes; application stops at first blocking error while independent structure checks continue. |
| Detailed task/array diagnostics | Exact values/types; requested change and preservation checks; membership, duplicate counts, first wrong index, ticket content and required operation order. |
| Correct pointer explanation | Syntax separate from lookup, escaped keys and bounds; dot-path hints are explanatory and never applied as repairs. |
| Every evaluator exercised/reviewed | Known-pass fixture for every objective/example variant, targeted failures across every applicable variant, saved-response replay and representative explanation review for every active objective variant. |
| Sequential/workflow handling | Move resolves destination after removal; copy preserves source; preconditions and ordered ops; typed branches, step order, assignment/repair history, stopping conditions and self-review claims verified. |
| Preserve study identities and evidence | No fingerprint-bearing files, prompts, spec files, result files or judgements changed; no inference or retry. New assessments stored separately. |
| Dialogue remains separate | No keyword grading or invented semantic oracle. |
| Partial/incomplete execution remains honest | Timeouts retain raw partials; no positive semantic verdict from a complete-looking partial; incomplete JSON alone does not prove semantic failure. |

## Contract decisions retained

Equivalent patches retain the existing final-state rule unless `required_ops` is declared. No new hard constraint is inferred from prose. RFC extension fields stay allowed, semantic operation syntax stays strict, and existing numeric equality is preserved while booleans/strings remain distinct. Explicit intermediate checks are reported separately from the original overall exact-match verdict. Unavailable or invalid measurement evidence never becomes invented measured performance.

## Verification

- Focused evaluator suite: **24 tests passed**, covering all 163 objective/example fixtures and per-variant mutation checks.
- CLI smoke: passed twice, proving repeatability and preservation of synthetic raw evidence.
- Git transport tests: **8 passed**, including a global-style `pull.rebase=true` override.
- Full repository discovery: **501 tests**, with 496 passing, four Bash checks skipped and one Windows socket interruption in an existing server test. The complete **32-test server group passed on rerun**, including that origin-rejection test; the **four Bash checks passed separately** using the existing Git Bash. Thus all 501 discovered tests have successful validation across these runs. Logs: [full discovery](../../.local/evaluator-unit-verified.log), [server confirmation](../../.local/evaluator-server-confirmation.log), [shell confirmation](../../.local/evaluator-shell-tests.log).
- Inference fingerprint remains `56502881bc3c89f6b58c8f5e755b32f58cbd675274ed5363293b598aaddf9787`.

The full suite exposed an existing Git transport issue under the user’s global rebase preference. `pull --ff-only --no-rebase` now makes the existing conservative policy explicit; its two local-edit preservation tests also explicitly set the conflicting preference. This affects repository synchronization, not experiment identities.

## Per-definition review

Every active objective row below represents reviewed completion of **all** its variants, not only one passing example. Individual case links and outcomes are in `review.json`.

| Definition | Family | Variants | Saved observations | Status |
| --- | --- | ---: | ---: | --- |
| array_index_add_012 | index | 3 | 12 | reviewed |
| array_index_copy_014 | index | 3 | 12 | reviewed |
| array_index_move_013 | index | 3 | 12 | reviewed |
| array_index_remove_011 | index | 3 | 12 | reviewed |
| array_index_replace_010 | index | 3 | 12 | reviewed |
| array_index_replace_explicit_minimal_017 | index | 3 | 12 | reviewed |
| array_index_replace_minimal_016 | index | 3 | 12 | reviewed |
| array_index_test_015 | index | 3 | 12 | reviewed |
| array_patch_add_006 | array_patch | 2 | 8 | reviewed |
| array_patch_add_006_full_paths | array_patch | 1 | 4 | reviewed |
| array_patch_copy_008 | array_patch | 2 | 8 | reviewed |
| array_patch_copy_008_full_paths | array_patch | 1 | 4 | reviewed |
| array_patch_move_007 | array_patch | 2 | 8 | reviewed |
| array_patch_move_007_full_paths | array_patch | 1 | 4 | reviewed |
| array_patch_remove_005 | array_patch | 2 | 8 | reviewed |
| array_patch_remove_005_full_paths | array_patch | 1 | 4 | reviewed |
| array_patch_replace_004 | array_patch | 2 | 8 | reviewed |
| array_patch_replace_004_full_paths | array_patch | 1 | 4 | reviewed |
| array_patch_test_009 | array_patch | 2 | 8 | reviewed |
| array_patch_test_009_full_paths | array_patch | 1 | 4 | reviewed |
| clothing_append | clothing | 8 | 32 | reviewed |
| clothing_append_full_paths | clothing | 4 | 16 | reviewed |
| dialogue_test_0_0 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_0_1 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_0_2 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_0_3 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_0_4 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_0_5 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_0_6 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_0_7 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_0_8 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_1_0 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_1_1 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_1_2 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_1_3 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_1_4 | dialogue | 1 | 12 | rubric needed |
| dialogue_test_1_5 | dialogue | 1 | 12 | rubric needed |
| dialogue_test | dialogue | 1 | 12 | rubric needed |
| household_coat_add_003 | household | 4 | 16 | reviewed |
| household_coat_add_003_full_paths | household | 2 | 8 | reviewed |
| household_coat_remove_002 | household | 4 | 16 | reviewed |
| household_coat_remove_002_full_paths | household | 2 | 8 | reviewed |
| inventory_net_stock_001 | inventory | 4 | 16 | reviewed |
| inventory_net_stock_001_full_paths | inventory | 2 | 8 | reviewed |
| prompt_calibration_001_time | calibration_time | 14 | 168 | reviewed |
| prompt_calibration_001_time_full_paths | calibration_time | 5 | 60 | reviewed |
| prompt_calibration_001_time_v1_full_paths | calibration_time | 2 | 24 | reviewed |
| prompt_calibration_002_boolean | calibration_boolean | 12 | 144 | reviewed |
| prompt_calibration_002_boolean_full_paths | calibration_boolean | 5 | 60 | reviewed |
| prompt_calibration_002_boolean_v1_full_paths | calibration_boolean | 1 | 12 | reviewed |
| prompt_calibration_003_nested | calibration_nested | 12 | 144 | reviewed |
| prompt_calibration_003_nested_full_paths | calibration_nested | 5 | 60 | reviewed |
| prompt_calibration_003_nested_v1_full_paths | calibration_nested | 1 | 12 | reviewed |
| prompt_calibration_004_array | calibration_array | 12 | 144 | reviewed |
| prompt_calibration_004_array_full_paths | calibration_array | 5 | 60 | reviewed |
| prompt_calibration_004_array_v1_full_paths | calibration_array | 1 | 12 | reviewed |
| time_only | time | 8 | 32 | reviewed |
| time_only_full_paths | time | 4 | 16 | reviewed |
| cached_questions | cached_questions | 2 | 0 | inactive example: fixtures reviewed |
| narrate_then_update | narrate_then_update | 1 | 0 | inactive example: fixtures reviewed |
| verify_repair | verify_repair | 1 | 0 | inactive example: fixtures reviewed |
