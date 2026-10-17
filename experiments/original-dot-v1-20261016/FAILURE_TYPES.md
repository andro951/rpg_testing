# Discussion reference: dot-path experiment

These are primary failure labels, not new grades. Raw scores and responses are unchanged. Full paths input deliberately retains slash display notation; operation output requires dot notation.

## DOT-01: Missing collection prefix

**298 observations.** Models: desktop/local-2542aed68e6bb077: 12, desktop/local-28df315996a77e69: 24, desktop/local-81e2a88130ccfa4e: 18, desktop/local-8c5e666555c53096: 21, desktop/local-cb6dd200423a32cc: 60, desktop/perchance-text-generator: 1, unity/qwen35-27b-iq2_m-bartowski: 39, unity/qwen35-27b-ud-iq2_xxs: 57, unity/qwen35-9b-q4_k_m: 9, unity/qwen35-9b-q8_0: 57.

Representative: [db_v3_copy_record_empty__dot_patch_v1 / id_keyed_arrays / repetition 2](failure-cases/desktop/local-2542aed68e6bb077/1383b7650e1da9c1778768bedcaea808bb18fcffff3fa6e2bd09fcf043bb36c8.json).

**Exact model response:**

````text
[{"op":"copy","from":"item-17","path":"storage"}]
````

**Validator error:**

````text
Missing or undefined property: item-17
````

**Expected final state:**

```json
{
  "items": [
    {
      "item_id": "item-42",
      "name": "Sword",
      "count": 3
    },
    {
      "item_id": "item-17",
      "name": "Sword",
      "count": 8
    },
    {
      "item_id": "item-83",
      "name": "Potion",
      "count": 2
    },
    {
      "item_id": "item-26",
      "name": "Shield",
      "count": 6
    }
  ],
  "storage": [
    {
      "item_id": "item-17",
      "name": "Sword",
      "count": 8
    }
  ]
}
```

## DOT-02: Slash notation in a dot output path

**165 observations.** Models: desktop/local-2542aed68e6bb077: 57, desktop/local-28df315996a77e69: 12, desktop/local-81e2a88130ccfa4e: 27, desktop/local-8c5e666555c53096: 15, desktop/local-cb6dd200423a32cc: 6, unity/qwen35-27b-iq2_m-bartowski: 9, unity/qwen35-27b-ud-iq2_xxs: 9, unity/qwen35-9b-q4_k_m: 18, unity/qwen35-9b-q8_0: 12.

Representative: [db_v3_update_record__dot_patch_v1 / full_paths / repetition 3](failure-cases/desktop/local-2542aed68e6bb077/0340f96787333c793c59da3e33fd4eebe8ff246a73bd39ea93f82b9256c09c3e.json).

**Exact model response:**

````text
[{"op":"replace","path":"/items/item-17/count","value":9}]
````

**Validator error:**

````text
path: Reserved characters in a dot path component must use %HH escapes
````

**Expected final state:**

```json
{
  "items": [
    {
      "item_id": "item-42",
      "name": "Sword",
      "count": 3
    },
    {
      "item_id": "item-17",
      "name": "Sword",
      "count": 9
    },
    {
      "item_id": "item-83",
      "name": "Potion",
      "count": 2
    },
    {
      "item_id": "item-26",
      "name": "Shield",
      "count": 6
    }
  ]
}
```

## DOT-03: Markdown fence around the response

**39 observations.** Models: desktop/perchance-text-generator: 3, unity/qwen35-27b-iq2_m-bartowski: 36.

Representative: [db_v3_remove_record__dot_patch_v1 / normal_json / repetition 1](failure-cases/desktop/perchance-text-generator/4e31c8f2050375f33d665b243f316a067910d1bfa783565bfd92149d77dfcb59.json).

**Exact model response:**

````text
```json
[
  {
    "op": "remove",
    "path": "items.item-83"
  }
]
```
````

**Validator error:**

````text
Expecting value: line 1 column 1 (char 0)
````

**Expected final state:**

```json
{
  "items": [
    {
      "item_id": "item-42",
      "name": "Sword",
      "count": 3
    },
    {
      "item_id": "item-17",
      "name": "Sword",
      "count": 8
    },
    {
      "item_id": "item-26",
      "name": "Shield",
      "count": 6
    }
  ]
}
```

## DOT-04: Missing operation-object braces

**75 observations.** Models: desktop/local-28df315996a77e69: 75.

Representative: [db_v3_move_value__dot_patch_v1 / full_paths / repetition 3](failure-cases/desktop/local-28df315996a77e69/002c70f0e83276cc9b0e04e4760e2e112aca02be2ffdb33fc57ef3a542b03e3e.json).

**Exact model response:**

````text
["op":"move","from":"town-a","path":"archived_locations"]
````

**Validator error:**

````text
Expecting ',' delimiter: line 1 column 6 (char 5)
````

**Expected final state:**

```json
{
  "locations": [
    "town-c",
    "town-b"
  ],
  "archived_locations": [
    "town-z",
    "town-a"
  ]
}
```

## DOT-05: Wrong operation array/object structure

**3 observations.** Models: desktop/local-28df315996a77e69: 3.

Representative: [db_v3_update_nested_collection__dot_patch_v1 / id_keyed_arrays / repetition 2](failure-cases/desktop/local-28df315996a77e69/3d4c2f8edc71037ed193ea360c80d57b8081e364a724c43f9d4b9fa2f62925b6.json).

**Exact model response:**

````text
["replace","workspace.inventory.items.item-26.count",7]
````

**Validator error:**

````text
Operations must follow this test's allowed operation types, required fields and path rules. 'replace' is not valid under any of the given schemas; 'workspace.inventory.items.item-26.count' is not valid under any of the given schemas; 7 is not valid under any of the given schemas
````

**Expected final state:**

```json
{
  "workspace": {
    "inventory": {
      "items": [
        {
          "item_id": "item-42",
          "name": "Sword",
          "count": 3
        },
        {
          "item_id": "item-17",
          "name": "Sword",
          "count": 8
        },
        {
          "item_id": "item-83",
          "name": "Potion",
          "count": 2
        },
        {
          "item_id": "item-26",
          "name": "Shield",
          "count": 7
        }
      ]
    },
    "name": "Workshop"
  }
}
```

## DOT-06: Wrong identity or positional selector

**33 observations.** Models: desktop/local-2542aed68e6bb077: 33.

Representative: [db_v3_move_value__dot_patch_v1 / normal_json / repetition 1](failure-cases/desktop/local-2542aed68e6bb077/01b1856905bee5f7a389c5d7377b4ccfa7bef30dc48a02f99a0b89b51ff3f380.json).

**Exact model response:**

````text
[{"op":"move","from":"locations.0","path":"archived_locations"}]
````

**Validator error:**

````text
Plain selector '0' must match exactly one element; found 0
````

**Expected final state:**

```json
{
  "locations": [
    "town-c",
    "town-b"
  ],
  "archived_locations": [
    "town-z",
    "town-a"
  ]
}
```

## DOT-07: Wrong operation name

**12 observations.** Models: desktop/local-2542aed68e6bb077: 12.

Representative: [db_v3_copy_value__dot_patch_v1 / normal_json / repetition 1](failure-cases/desktop/local-2542aed68e6bb077/1016db32a644b12e2b60fdc65b38f8d5a2c454c2d45a1815bc86d0f5a2c9dae0.json).

**Exact model response:**

````text
[{"op":"move","from":"locations.0","path":"archived_locations"}]
````

**Validator error:**

````text
This contract requires these operation names in this exact order, including any test precondition.
````

**Expected final state:**

```json
{
  "locations": [
    "town-c",
    "town-a",
    "town-b"
  ],
  "archived_locations": [
    "town-z",
    "town-a"
  ]
}
```

## DOT-08: Unnecessary change in a NOOP task

**6 observations.** Models: desktop/local-2542aed68e6bb077: 6.

Representative: [db_v3_no_change__dot_patch_v1 / normal_json / repetition 2](failure-cases/desktop/local-2542aed68e6bb077/3d71284c0cbf9375b4f034e6364f7a38b20ec8986a7e4217412db61966f8b749.json).

**Exact model response:**

````text
[{"op":"replace","path":"items.0.name","value":"Blue"}]
````

**Validator error:**

````text
The current data already equals the expected state. Return []; a redundant update is not needed.
````

**Expected final state:**

```json
{
  "items": [
    {
      "item_id": "item-42",
      "name": "Sword",
      "count": 3
    },
    {
      "item_id": "item-17",
      "name": "Sword",
      "count": 8
    },
    {
      "item_id": "item-83",
      "name": "Potion",
      "count": 2
    },
    {
      "item_id": "item-26",
      "name": "Shield",
      "count": 6
    }
  ]
}
```

## DOT-09: Wrong role for an operation path

**3 observations.** Models: desktop/local-81e2a88130ccfa4e: 3.

Representative: [db_v3_remove_value_last__dot_patch_v1 / full_paths / repetition 2](failure-cases/desktop/local-81e2a88130ccfa4e/2b9467b227db5b8472ec63999225aa6295b36c2e74dad5effd8816cf91292e04.json).

**Exact model response:**

````text
[{"op":"remove","path":"locations","from":"town-a"}]
````

**Validator error:**

````text
Remove path must select a collection element
````

**Expected final state:**

```json
{
  "locations": []
}
```

## DOT-10: Wrong element value type

**6 observations.** Models: desktop/local-cb6dd200423a32cc: 6.

Representative: [db_v3_append_value__dot_patch_v1 / id_keyed_arrays / repetition 3](failure-cases/desktop/local-cb6dd200423a32cc/0256ec0260e1215aed21c0924085d9881e0666bacea2c18f52f3a4a22f280df5.json).

**Exact model response:**

````text
[
  {
    "op": "add",
    "path": "locations",
    "value": {
      "town-d": "town-d"
    }
  }
]
````

**Validator error:**

````text
{'town-d': 'town-d'} is not of type 'string'

Failed validating 'type' in schema['properties']['locations']['items']:
    {'type': 'string'}

On instance['locations'][3]:
    {'town-d': 'town-d'}
````

**Expected final state:**

```json
{
  "locations": [
    "town-c",
    "town-a",
    "town-b",
    "town-d"
  ]
}
```

## Unity overlap and wrapper-only diagnostic

All 246 Unity failures were reviewed: 162 prefix-only, 42 slash-only, 33 fence-only, six prefix+slash and three prefix+fence. All 48 slash-containing failures occurred with Full paths input.

For the fenced responses only, an explicitly separate diagnostic parsed the fenced content and applied the unchanged dot interpreter to a copy of the initial state. Thirty-three reached the exact expected state; three still failed for missing collection prefixes. This did not alter a benchmark score, raw response, grader or prompt. No alternative pass total is reported.

The optimized controls contain different wording and are secondary comparisons. Original930 has no Q4_K_S or Unity baseline. The corrected NOOP is separately recorded.
