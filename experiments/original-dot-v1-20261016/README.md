# Original prompt wording with dot output paths: completed experiment

Scope SHA256: `0002ca4aa303b0a627352fa08540e062ef72db3bbfefd30814cc2f828ca5b112`.

**1,860 observations: 1,220 PASS, 640 FAIL; zero timeouts or scored infrastructure errors.** All ten 62-prompt × three-repetition matrices, raw checksums, actual request hashes and detailed/stored score agreement were audited.

| Worker | Model | Strict pass /186 | Original → dot /177 | Optimized control /186 |
|---|---|---:|---:|---:|
| desktop | Qwen3.5-2B Q8_0 | 66 | 63 → 66 | 78 |
| desktop | Qwen3.5-4B Q8_0 | 72 | 51 → 63 | 99 |
| desktop | Qwen3.5-9B Q4_K_M | 138 | 42 → 129 | 186 |
| desktop | Qwen3.5-9B Q4_K_S | 150 | Not available | 186 |
| desktop | Qwen3-VL-8B-Instruct Q4_K_M | 114 | 42 → 105 | 164 |
| desktop | Perchance Text Generator (remote model unknown) | 182 | 161 → 174 | 174 |
| unity | Qwen3.5-27B IQ2_M (Bartowski) | 102 | Not available | 186 |
| unity | Qwen3.5-27B UD-IQ2_XXS | 120 | Not available | 186 |
| unity | Qwen3.5-9B Q4_K_M | 159 | Not available | 180 |
| unity | Qwen3.5-9B Q8_0 | 117 | Not available | 186 |

The paired 177-observation comparison excludes the nine corrected NOOP observations per cohort. Across 885 unchanged paired observations: 359 → 537 passes, 247 corrected failures and 69 regressions. See [NOOP exception](analysis/noop-exception.json). Optimized controls have different guidance and are not notation-only baselines.

## Review the evidence

- [Failure types with exact representative outputs](FAILURE_TYPES.md)
- [All 640 failures, readable index](FAILURE_INDEX.md)
- [Failure index JSON](analysis/failure-index.json)
- [All 1,860 observation checksums and paths](analysis/observation-index.json)
- [Authoritative final report, unchanged](analysis/final-report.original.json)
- [All raw results](results)
- [Exact frozen requests, original controls and complete prompt diff](frozen-prompts)
- [Frozen runtime source and source hashes](runtime/source-manifest.json)
- [738-test validation](validation/full-tests-summary.json)

## Scope and storage

This directory is an isolated experiment snapshot. Root application code, active prompts/results, E: working changes, and unrelated OPRO work are not changed by this publication. The runtime snapshot contains the exact 130 manifest files used by the experiment, including its versioned dot interpreter, original prompt renderer, exporter, evaluator branches and native-port support. Additional test sources are retained for review. The complete preexisting validation used the C: mirror, including historic synthetic test fixtures; the large historic result archives are not duplicated here.

All 1,860 current experiment result JSON files are included byte-for-byte, not only failures. Each failure export links its immutable raw result, preserves exact response text and actual sent messages, and records the exact prompt hash, model/provider identity, repetition, input format, expected state and validator errors. Expected final states, not a single example patch, define correctness.

The active optimized control prompts were not regenerated. Original930 wording was used except the approved unrelated-information NOOP correction; only output method/path notation changed. Input displays remain original. No new inference, optimization, retries or grading changes were performed for this export.

Perchance observations are independent remote service trials. Seed effects, remote model identity and unsupported controls remain unverified; local GPU measurements are not claimed for the provider.

The earlier interrupted native loading attempt and physical-disk Event 7 diagnostics remain in the original local evidence directory. The authorized continuation completed without new storage errors. Raw Windows timestamps run approximately twelve minutes ahead of independent UTC/Unity; timestamps are not rewritten.

Excluded from Git: model weights, local models/settings, browser profiles/session storage/cookies, credentials, virtual environments/dependency caches, runtime executables, unrelated prior results/OPRO sessions, transient locks and temporary directories. Current experiment raw results are fully included. Machine-local absolute paths retained inside immutable provenance are references, not copied private files.

Publication source: existing `main` commit `52800f59b15ddfdd756d555c9fe810c168ab5a66`; dedicated branch `experiment/original-dot-v1-20261017`. See [publication manifest](publication-manifest.json) for every exported file hash.
