# ID-keyed array input display

The `id_keyed_arrays` input presentation is deliberately **not valid JSON**. It
keeps braces for objects, uses square brackets for arrays, and writes each array
element as `"identity": element`. For example:

```text
{
  "items": [
    "a": {"id": "a", "count": 2}
  ],
  "empty_array": [],
  "empty_object": {}
}
```

Arrays are accessed by identity, never position. The displayed key does not add
another path level: the element above is at `items.a`, and its count is at
`items.a.count`. The array itself is at `items`.

The ID-only mapping selects the identifying field of object elements. Primitive
array elements identify themselves. Display keys are quoted strings, using the
same identity-to-text conversion as before. The original element still retains
its exact JSON type and all fields, including its ID field. For example a numeric
element is displayed as `"7": 7`, not as a string value. Colliding identity text
is rejected rather than overwriting an element.

Fields, keys, and string values use JSON escaping. Nested arrays use the same
bracket notation recursively. No `$array` or `$object` wrapper fields are added;
if either name actually exists in the data, it is preserved as ordinary data.
The mapping is used internally for conversion, never printed as schema guidance.

Normal JSON, full-path and named-table input presentations are unchanged. This
is an input display convention and does not change any requested output format,
allowed operation, path semantics, or evaluator.
