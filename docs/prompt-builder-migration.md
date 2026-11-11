# Template-builder replacement verification

This change replaces the old executable `test_builder` with `prompt_builder` and activates the new schema-free suite in root `test_specs`.

## Ordered verification

1. Before changing wording or schema behavior, independent template assembly reproduced all 38 current base messages exactly and reconstructed 24 captured researched-format messages. `archives/prompt-builder-parity/parity-report.json` and `legacy-messages.json` preserve the scope, content and hashes. This is 62 checks, not a claim to rebuild every historical optimized experiment.
2. Removed per-case schemas and schema descriptions, renamed `ember_typed_lines` to `typed_lines`, and used data-derived container markers where array/object distinctions would otherwise be lost. These intentional changes use a new evaluator/definition identity; historical scores are not reused.
3. Checked 372 supported synthetic case/input/output combinations across 13 cases, four input views and eight output readers. Nine typed-line combinations are explicitly unsupported. This is deterministic software verification, not model accuracy.
4. Activated 13 default definitions, 38 unique prompts and 114 configured observations per model. Old root definitions and previews were retained byte-for-byte under `archives/pre-template-builder`; old builder code was deleted. Original builder regression test sources and frozen synthetic definitions remain test data, not executable archived builder code.
5. Full Python discovery passed **911 tests**. Subsequent targeted checks cover editable-selection behavior, build inventory validation and the migration audit. JavaScript `build-grammar-spec.cjs --check` and `run-all.cjs` passed. No model inference or Unity job was started.

## Archived evidence audit

The read-only audit against pinned commit `a64cc029837a33d4b67a6a8e4b5d686497ef943c` passed: 21 prior definitions, 126 patch-suite files and 62 review files are preserved; 20,052 existing evidence files are unchanged; all 13 current definitions match freshly compiled templates/evaluator and 95 catalog pointers/hashes/variant lists validate. Seven migration-audit tests and the three unchanged loading-only audit tests pass.

CI now runs this explicit migration audit instead of falsely requiring source/scoring equivalence to the old root suite. The earlier loading-only audit and its tests remain unchanged for their original purpose. No compatibility mapping was added to relabel new semantics as old results.

## Independent review corrections

Review identified and verified fixes for editable-heading parsing, literal task text that resembles template comments, stale files after narrowing a build, format-specific synthetic responses, Unity dependency packaging, optimizer task routing and portable source pins. OPRO bindings preserve common system restrictions; saved promotions only replay against their exact base and stale recipes reject edits.

New builds are staged and published only after success. Install checks the exact definition inventory/hashes and each preview's request digest before activating it. A failed build leaves the preceding complete artifact in place. Prior generated data is retained in build histories/archives.

## Grading and limits

Final-state equality ignores database-array order. Output operation order remains significant. Expected-patch mismatch is separate and cannot turn a correct final state into failure. Unrecognized free-format prose is a parser gap with unknown semantic correctness, not an asserted model failure.

Current builds select `array-identities-intent-v1` with ID-only `array_identities.json` per case. Custom ID names and multiple ID-looking fields are supported by explicit metadata. The user subsequently approved consulting this same map internally for the ID-keyed and full-path input conversions only. No map, schema description or reference answer is inserted into model prompts. Normal JSON rendering does not need the map; the separate named-table view retains its data-only convention. No full shape schema or reference answer is passed to normalization. The original `schema-free-intent-v1` audit above is historical evidence, not a claim about the new evaluator.

The evaluator source pin is portable across Python patch versions and normalizes checkout line endings. Actual Python version remains runtime provenance. Old evaluator definitions keep their own historical rules.

## Browser verification limitation

The new results-table smoke test could not launch Chromium in the local execution environment because socket access was restricted. No local browser UI assertions are claimed. Node-based result-marker/count logic and JavaScript syntax checks passed; `tests/schema_free_report_browser_smoke.py` is included in browser CI for a supported environment.
