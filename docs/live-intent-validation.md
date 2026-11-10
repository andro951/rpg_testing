# Live intent integration validation

Executed on 2026-11-10 with Python 3.10.6 and jsonschema 4.26.0. No live model inference, model loads, weight scans, provider requests, or frozen-runner edits were performed.

## Frozen implementation

Evaluator: `3c8f2b365473bc40613018db847f15a63fe4b14b0e6f1c35cdd285065cc7b790`.

Implementation was frozen before reserved-final references or saved outcomes were evaluated. No parser changes were made in response to reserved-final results. The exact default-strict compatibility mapping was independently reviewed; unknown future source changes are not aliased.

## Current coverage

All eight current overnight manifests were verified: 1,680 model/arm-specific definitions, 4,960 variants, and 14,880 observations. Latest round eight contains 210 definitions, 620 variants, and 1,860 observations. Every selected method is dot_patch_v1/research_json_v2. No current record was converted from another representation. Historical root five-operation definitions and predecessor cohorts were excluded from this audit.

- All 4,960 reference variants passed through actual workflow execution with a mock backend; all 9,920 independent negative checks were rejected.
- Independent maintained/current strict scores, raw synthetic outputs, and request digests matched for every reference. Selected intent identities were distinct.
- All 14,880 actual captured IDs reconstructed exactly from captured artifact pins, targets, repetitions, definitions, and provenance. All equal maintained/current strict IDs.
- All 4,960 pending and terminal plans matched. All 14,880 synthetic completed-wrong records remained terminal, including 4,960 synthetic completed-timeout records.
- Saved evidence hashes, record checksums, exact captured definitions, request digests, roles, repetitions, and completeness were verified. One historical timeout remains terminal and is excluded from new grading, without retry.

## Saved-response replay

Stored is the immutable historical score. Maintained strict is a fresh evaluation with the original maintained source. Selected is this explicitly selected intent evaluator. Current strict matched maintained strict in every complete record. These are retrospective scores, not new model trials.

| Scope | Role | Arm | Complete | Stored exact | Maintained strict exact | Selected exact | Gains | Regressions | Incomplete |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| all_eight | all | all | 14879 | 12966 | 12966 | 13599 | 633 | 0 | 1 |
| all_eight | final | all | 2879 | 2010 | 2010 | 2400 | 390 | 0 | 1 |
| all_eight | final | baseline | 1440 | 996 | 996 | 1200 | 204 | 0 | 0 |
| all_eight | final | candidate | 1439 | 1014 | 1014 | 1200 | 186 | 0 | 1 |
| all_eight | regression | all | 9120 | 8889 | 8889 | 8889 | 0 | 0 | 0 |
| all_eight | regression | baseline | 4560 | 4446 | 4446 | 4446 | 0 | 0 | 0 |
| all_eight | regression | candidate | 4560 | 4443 | 4443 | 4443 | 0 | 0 | 0 |
| all_eight | selection | all | 2880 | 2067 | 2067 | 2310 | 243 | 0 | 0 |
| all_eight | selection | baseline | 1440 | 1041 | 1041 | 1155 | 114 | 0 | 0 |
| all_eight | selection | candidate | 1440 | 1026 | 1026 | 1155 | 129 | 0 | 0 |
| latest_round_eight | all | all | 1860 | 1635 | 1635 | 1716 | 81 | 0 | 0 |
| latest_round_eight | final | all | 360 | 255 | 255 | 303 | 48 | 0 | 0 |
| latest_round_eight | final | baseline | 180 | 126 | 126 | 150 | 24 | 0 | 0 |
| latest_round_eight | final | candidate | 180 | 129 | 129 | 153 | 24 | 0 | 0 |
| latest_round_eight | regression | all | 1140 | 1122 | 1122 | 1122 | 0 | 0 | 0 |
| latest_round_eight | regression | baseline | 570 | 555 | 555 | 555 | 0 | 0 | 0 |
| latest_round_eight | regression | candidate | 570 | 567 | 567 | 567 | 0 | 0 | 0 |
| latest_round_eight | selection | all | 360 | 258 | 258 | 291 | 33 | 0 | 0 |
| latest_round_eight | selection | baseline | 180 | 129 | 129 | 147 | 18 | 0 | 0 |
| latest_round_eight | selection | candidate | 180 | 129 | 129 | 144 | 15 | 0 | 0 |

Stored versus maintained strict: 0 full-score discrepancies and 0 exact-match discrepancies. None were attributed silently to parser gains. Original scores were not overwritten.

## Tests and live entrypoint

- Required complete Python suite: 754 tests passed (852.967 seconds).
- Full JavaScript parser suite passed unchanged. C# build succeeded; 206 native checks and 2,757 fixture checks passed.
- Sixteen maintained pure separator tests passed against this source. The separate offline assess-registry test is outside this live integration; corresponding live operation/schema validation has dedicated tests.
- New synthetic tests cover Controller -> Session -> monitored execution -> parser -> persisted result -> resume, default strict preservation, parser-call count, lexical path boundaries, typed-ID ambiguity, atomic errors, oracle isolation, empty output, source rejections, and stale evaluator pins.
- Real preparation CLI copied all current round-eight definitions into a new isolated run: 210 definitions/620 variants, prompts unchanged, inference not started. Existing outputs cannot be overwritten. No GUI layout was changed.

See [live-intent-evaluation.md](live-intent-evaluation.md) for preparation and serving commands. Old frozen runners intentionally continue their own frozen source. Root default test_specs is not the current overnight suite.

## Limitations and preservation

- The historical pinned audit_case_preservation.py still fails at domain.py, as already observed on the unchanged baseline. Its baseline was not rewritten or weakened.
- This delivery is the current-contract parser/evaluator integration plus narrowly required native-port and Perchance companion behavior. It does not import unrelated later optimizer/coverage/UI features or claim whole-app/live-inference parity.
- Native field-value and Ember representations remain on their existing evaluators; the new selector accepts only dot_patch_v1. Their supporting modules were copied because the maintained scorer imports them conditionally.
- Full comparison inventories, original responses, normalized per-case patches, local source paths, process logs, and detailed role-specific records remain outside the public commit.
- Aggregate counts and durable receipt hashes are in [live-intent-validation.json](live-intent-validation.json). Source snapshot provenance is in [intent-live-source-snapshot.json](intent-live-source-snapshot.json).
