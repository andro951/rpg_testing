# Validation for new template-built tests

1. Read raw model output and starting data only. The selected deterministic reader and intent parser produce canonical ID-based dot operations. No schema, requested task, expected result or expected patch enters normalization.
2. Apply operations sequentially, checking valid identity-based targets and unique IDs. Do not guess ambiguous paths, silently repair wrong values, or use array positions as identities.
3. Compare the final database with expected_result.json. Database arrays are order-insensitive at every depth; object fields, types and values still matter. Correct final state determines pass/fail. An invalid operation or unparseable response cannot pass automatically.
4. Separately normalize expected_patch.json and compare the ordered normalized operation list. Record expected_patch_mismatch without changing pass/fail. Different valid operation sequences may pass while this flag is true. A missing/unusable reference is unavailable, not a mismatch or an automatic fail.

The reference is a diagnostic, not a unique solution. Patches are valid against the starting snapshot and execute in order; do not apply them later to a changed database or reorder them.

Frozen historical definitions retain their old evaluator, schemas, order-sensitive grading and operation-count restrictions. Only newly compiled tests opt into schema-free behavior; no saved model response/result is overwritten or rescored in place.

Free-format output is not the dot contract. Recognized structured intent can be recovered; unrecognized prose has unknown semantic correctness. Clear prose no-change is reported as a parser gap, not evidence that the model misunderstood the task. No assistant judgment is called human annotation.
