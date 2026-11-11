# Typed lines

This folder owns its requested output wording. `format.json` chooses the reader.

The array-identities-intent-v2 host uses `evaluation/typed_lines.py`: records execute in written order, slash paths support JSON-scalar ID/value selectors, and object/list labels accept complete single-line JSON payloads. Append accepts complete object elements, including into empty arrays. Remove deletes an array element; targeting an existing scalar object field instead retains legacy nullification. Set plus null is explicit null assignment. Set selects existing object fields and accepts complete object values; replacing a whole collection or collection element remains forbidden. Numeric change and legacy remove-field nullification are scalar-only. List syntax does not permit nested-array elements or override collection restrictions. Missing paths, extra value lines, wrong typed values, duplicate identities and ambiguous identities are rejected.

The original `workbench/ember_text.py` and schema-free-intent-v1 reader retain their published grammar, scalar/primitive subset and grouped execution. Saved fixtures and results are not migrated.

Move and Copy use `move: /source/"id"` or `copy: /source/"id"` followed immediately by `to: /destination`. Both append a deep copy to a different collection; Move also removes the original. There is no value line. IDs stay unique in each collection, and same-collection or descendant transfers are rejected.
