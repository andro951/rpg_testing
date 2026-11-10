# Outer-array normalization (offline validator version)

`normalization.normalize_outer_array(text)` is a reusable standard-library parser.
It accepts a strict JSON operation array, or exactly one missing outer opening
bracket, closing bracket, or both. It never repairs internal JSON, invents commas,
changes values/paths, or guesses an empty no-op from incomplete delimiters.

```python
from normalization import normalize_outer_array
result = normalize_outer_array('{"op":"replace","path":"profile.note","value":"hello"}')
json_text = result.to_json()
metadata = result.metadata()
```

`json_text` is valid JSON **in the input dialect**. A custom dot path is still a
custom dot path. This parser does not claim to export a standard JSON Patch.
A stateful exporter must resolve IDs using current state/schema, lower paths to
JSON Pointer sequentially, and independently verify complete patch application.
A host request contract is necessary to establish requested-edit completeness.

The opt-in `dot-outer-arrays-v1` offline validator composes bracket normalization
with `dot-separators-v2` path resolution. Captured operation/schema/type/sequence
and final-state checks remain unchanged. Wrong values/paths, omitted or extra
required changes, malformed JSON and incomplete/error/timeout evidence cannot
become successful merely by restoring brackets. Literal, encoded and quoted ID
semantics are inherited unchanged. Original raw responses/scores are retained.

```powershell
python -m evaluation --source <saved-results> --output <separate-validation-output> --validator dot-outer-arrays-v1
```

Validation identity includes the implementation/dependency hashes and original
output checksum, separate from generation identity. Default generation parsing
and the default evaluator remain strict. A replay of historical final-labelled
data must be validation-only after the rule/tests are frozen, never prompt
selection or tuning. Source evidence must not be overwritten.

Tests cover opening/closing/both, strict internal parsing, whitespace/escaped
brackets, multiple operations, missing requested operations, encoded IDs,
malformed percent escapes, completed-call gates and immutable repeat replay.
New November 9 unordered-array/copy/move/alias product decisions are recorded
separately as discussion only; they are not implemented by this change and must
not be attributed to the frozen three-operation benchmark evidence.
