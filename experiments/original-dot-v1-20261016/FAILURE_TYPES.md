# Discussion reference: dot-path experiment

**640 failed observations**, including all three configured repetitions. Counts are observations, not unique prompts or failure mechanisms. Each observation has one primary label; that label can mask additional issues. For example, the DOT-04 representative also omits the `locations` collection prefix, and the DOT-07 representative also uses a positional selector.

All ten model names below are verified against the worker/model rows in the [authoritative final report](analysis/final-report.original.json). IDs remain secondary provenance in the model key, JSON index and immutable raw results.

The exact responses, prompts, validator errors and strict grades are unchanged. Full paths input deliberately retains slash display notation; operation output requires dot notation.

## Primary category by model

| Worker / verified model | DOT-01 | DOT-02 | DOT-03 | DOT-04 | DOT-05 | DOT-06 | DOT-07 | DOT-08 | DOT-09 | DOT-10 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Desktop / Qwen3.5-2B Q8_0 | 12 | 57 | 0 | 0 | 0 | 33 | 12 | 6 | 0 | 0 | 120 |
| Desktop / Qwen3.5-4B Q8_0 | 24 | 12 | 0 | 75 | 3 | 0 | 0 | 0 | 0 | 0 | 114 |
| Desktop / Qwen3.5-9B Q4_K_M | 18 | 27 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 48 |
| Desktop / Qwen3.5-9B Q4_K_S | 21 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 36 |
| Desktop / Qwen3-VL-8B-Instruct Q4_K_M | 60 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 72 |
| Desktop / Perchance Text Generator (remote model unknown) | 1 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 |
| Unity / Qwen3.5-27B IQ2_M (Bartowski) | 39 | 9 | 36 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 84 |
| Unity / Qwen3.5-27B UD-IQ2_XXS | 57 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 66 |
| Unity / Qwen3.5-9B Q4_K_M | 9 | 18 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 27 |
| Unity / Qwen3.5-9B Q8_0 | 57 | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 69 |
| **All models** | 298 | 165 | 39 | 75 | 3 | 33 | 12 | 6 | 3 | 6 | **640** |

## Primary category by input format

| Type | Normal JSON | ID-keyed arrays | Full paths | Total |
|---|---:|---:|---:|---:|
| DOT-01 | 129 | 129 | 40 | 298 |
| DOT-02 | 0 | 0 | 165 | 165 |
| DOT-03 | 26 | 7 | 6 | 39 |
| DOT-04 | 12 | 24 | 39 | 75 |
| DOT-05 | 0 | 3 | 0 | 3 |
| DOT-06 | 33 | 0 | 0 | 33 |
| DOT-07 | 6 | 6 | 0 | 12 |
| DOT-08 | 3 | 3 | 0 | 6 |
| DOT-09 | 0 | 0 | 3 | 3 |
| DOT-10 | 0 | 3 | 3 | 6 |

All 165 DOT-02 primary slash-path failures used Full paths input. All 33 DOT-06 primary identity/positional-selector failures used Normal JSON input. These distributions do not establish causation; primary labels can hide other errors.

## Model provenance key

| Worker | Verified model | Model ID |
|---|---|---|
| desktop | Qwen3.5-2B Q8_0 | `local-2542aed68e6bb077` |
| desktop | Qwen3.5-4B Q8_0 | `local-28df315996a77e69` |
| desktop | Qwen3.5-9B Q4_K_M | `local-81e2a88130ccfa4e` |
| desktop | Qwen3.5-9B Q4_K_S | `local-8c5e666555c53096` |
| desktop | Qwen3-VL-8B-Instruct Q4_K_M | `local-cb6dd200423a32cc` |
| desktop | Perchance Text Generator (remote model unknown) | `perchance-text-generator` |
| unity | Qwen3.5-27B IQ2_M (Bartowski) | `qwen35-27b-iq2_m-bartowski` |
| unity | Qwen3.5-27B UD-IQ2_XXS | `qwen35-27b-ud-iq2_xxs` |
| unity | Qwen3.5-9B Q4_K_M | `qwen35-9b-q4_k_m` |
| unity | Qwen3.5-9B Q8_0 | `qwen35-9b-q8_0` |

## How to read the illustrative patches

Each category below includes one valid illustrative expected patch for the exact representative fixture/schema. It is not the only allowed serialization: equivalent contract-compliant operations are judged by final state. These patches are discussion examples only, never inserted into model prompts. They were validated with the frozen response schema, required operation names and unchanged dot interpreter, with no inference, score changes or edits to raw results. See [the ten validation records](analysis/representative-patch-validation.json).

## DOT-01: Missing collection prefix

**298 observations.** Models: Desktop Qwen3.5-2B Q8_0: 12, Desktop Qwen3.5-4B Q8_0: 24, Desktop Qwen3.5-9B Q4_K_M: 18, Desktop Qwen3.5-9B Q4_K_S: 21, Desktop Qwen3-VL-8B-Instruct Q4_K_M: 60, Desktop Perchance Text Generator (remote model unknown): 1, Unity Qwen3.5-27B IQ2_M (Bartowski): 39, Unity Qwen3.5-27B UD-IQ2_XXS: 57, Unity Qwen3.5-9B Q4_K_M: 9, Unity Qwen3.5-9B Q8_0: 57.

Representative: **Desktop Qwen3.5-2B Q8_0** (`local-2542aed68e6bb077`), [db_v3_copy_record_empty__dot_patch_v1 / ID-keyed arrays / repetition 2](failure-cases/desktop/local-2542aed68e6bb077/1383b7650e1da9c1778768bedcaea808bb18fcffff3fa6e2bd09fcf043bb36c8.json).

**Exact model response:**

````text
[{"op":"copy","from":"item-17","path":"storage"}]
````

**Validator error:**

````text
Missing or undefined property: item-17
````

**One valid illustrative expected patch (other equivalent serializations may be valid):**

```json
[
  {
    "op": "copy",
    "from": "items.item-17",
    "path": "storage"
  }
]
```

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

**165 observations.** Models: Desktop Qwen3.5-2B Q8_0: 57, Desktop Qwen3.5-4B Q8_0: 12, Desktop Qwen3.5-9B Q4_K_M: 27, Desktop Qwen3.5-9B Q4_K_S: 15, Desktop Qwen3-VL-8B-Instruct Q4_K_M: 6, Unity Qwen3.5-27B IQ2_M (Bartowski): 9, Unity Qwen3.5-27B UD-IQ2_XXS: 9, Unity Qwen3.5-9B Q4_K_M: 18, Unity Qwen3.5-9B Q8_0: 12.

Representative: **Desktop Qwen3.5-2B Q8_0** (`local-2542aed68e6bb077`), [db_v3_update_record__dot_patch_v1 / Full paths / repetition 3](failure-cases/desktop/local-2542aed68e6bb077/0340f96787333c793c59da3e33fd4eebe8ff246a73bd39ea93f82b9256c09c3e.json).

**Exact model response:**

````text
[{"op":"replace","path":"/items/item-17/count","value":9}]
````

**Validator error:**

````text
path: Reserved characters in a dot path component must use %HH escapes
````

**One valid illustrative expected patch (other equivalent serializations may be valid):**

```json
[
  {
    "op": "replace",
    "path": "items.item-17.count",
    "value": 9
  }
]
```

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

**39 observations.** Models: Desktop Perchance Text Generator (remote model unknown): 3, Unity Qwen3.5-27B IQ2_M (Bartowski): 36.

Representative: **Desktop Perchance Text Generator (remote model unknown)** (`perchance-text-generator`), [db_v3_remove_record__dot_patch_v1 / Normal JSON / repetition 1](failure-cases/desktop/perchance-text-generator/4e31c8f2050375f33d665b243f316a067910d1bfa783565bfd92149d77dfcb59.json).

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

**One valid illustrative expected patch (other equivalent serializations may be valid):**

```json
[
  {
    "op": "remove",
    "path": "items.item-83"
  }
]
```

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

**75 observations.** Models: Desktop Qwen3.5-4B Q8_0: 75.

Representative: **Desktop Qwen3.5-4B Q8_0** (`local-28df315996a77e69`), [db_v3_move_value__dot_patch_v1 / Full paths / repetition 3](failure-cases/desktop/local-28df315996a77e69/002c70f0e83276cc9b0e04e4760e2e112aca02be2ffdb33fc57ef3a542b03e3e.json).

**Secondary issue:** the actual response also lacks the `locations` collection prefix. Supplying braces alone does not make this response valid.

**Exact model response:**

````text
["op":"move","from":"town-a","path":"archived_locations"]
````

**Validator error:**

````text
Expecting ',' delimiter: line 1 column 6 (char 5)
````

**One valid illustrative expected patch (other equivalent serializations may be valid):**

```json
[
  {
    "op": "move",
    "from": "locations.town-a",
    "path": "archived_locations"
  }
]
```

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

**3 observations.** Models: Desktop Qwen3.5-4B Q8_0: 3.

Representative: **Desktop Qwen3.5-4B Q8_0** (`local-28df315996a77e69`), [db_v3_update_nested_collection__dot_patch_v1 / ID-keyed arrays / repetition 2](failure-cases/desktop/local-28df315996a77e69/3d4c2f8edc71037ed193ea360c80d57b8081e364a724c43f9d4b9fa2f62925b6.json).

**Exact model response:**

````text
["replace","workspace.inventory.items.item-26.count",7]
````

**Validator error:**

````text
Operations must follow this test's allowed operation types, required fields and path rules. 'replace' is not valid under any of the given schemas; 'workspace.inventory.items.item-26.count' is not valid under any of the given schemas; 7 is not valid under any of the given schemas
````

**One valid illustrative expected patch (other equivalent serializations may be valid):**

```json
[
  {
    "op": "replace",
    "path": "workspace.inventory.items.item-26.count",
    "value": 7
  }
]
```

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

**33 observations.** Models: Desktop Qwen3.5-2B Q8_0: 33.

Representative: **Desktop Qwen3.5-2B Q8_0** (`local-2542aed68e6bb077`), [db_v3_move_value__dot_patch_v1 / Normal JSON / repetition 1](failure-cases/desktop/local-2542aed68e6bb077/01b1856905bee5f7a389c5d7377b4ccfa7bef30dc48a02f99a0b89b51ff3f380.json).

**Exact model response:**

````text
[{"op":"move","from":"locations.0","path":"archived_locations"}]
````

**Validator error:**

````text
Plain selector '0' must match exactly one element; found 0
````

**One valid illustrative expected patch (other equivalent serializations may be valid):**

```json
[
  {
    "op": "move",
    "from": "locations.town-a",
    "path": "archived_locations"
  }
]
```

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

**12 observations.** Models: Desktop Qwen3.5-2B Q8_0: 12.

Representative: **Desktop Qwen3.5-2B Q8_0** (`local-2542aed68e6bb077`), [db_v3_copy_value__dot_patch_v1 / Normal JSON / repetition 1](failure-cases/desktop/local-2542aed68e6bb077/1016db32a644b12e2b60fdc65b38f8d5a2c454c2d45a1815bc86d0f5a2c9dae0.json).

**Secondary issue:** the actual response also uses `locations.0`, a positional selector, instead of the value-selected `locations.town-a`. Changing only Move to Copy is insufficient.

**Exact model response:**

````text
[{"op":"move","from":"locations.0","path":"archived_locations"}]
````

**Validator error:**

````text
This contract requires these operation names in this exact order, including any test precondition.
````

**One valid illustrative expected patch (other equivalent serializations may be valid):**

```json
[
  {
    "op": "copy",
    "from": "locations.town-a",
    "path": "archived_locations"
  }
]
```

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

**6 observations.** Models: Desktop Qwen3.5-2B Q8_0: 6.

Representative: **Desktop Qwen3.5-2B Q8_0** (`local-2542aed68e6bb077`), [db_v3_no_change__dot_patch_v1 / Normal JSON / repetition 2](failure-cases/desktop/local-2542aed68e6bb077/3d71284c0cbf9375b4f034e6364f7a38b20ec8986a7e4217412db61966f8b749.json).

**Exact model response:**

````text
[{"op":"replace","path":"items.0.name","value":"Blue"}]
````

**Validator error:**

````text
The current data already equals the expected state. Return []; a redundant update is not needed.
````

**One valid illustrative expected patch (other equivalent serializations may be valid):**

```json
[]
```

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

**3 observations.** Models: Desktop Qwen3.5-9B Q4_K_M: 3.

Representative: **Desktop Qwen3.5-9B Q4_K_M** (`local-81e2a88130ccfa4e`), [db_v3_remove_value_last__dot_patch_v1 / Full paths / repetition 2](failure-cases/desktop/local-81e2a88130ccfa4e/2b9467b227db5b8472ec63999225aa6295b36c2e74dad5effd8816cf91292e04.json).

**Exact model response:**

````text
[{"op":"remove","path":"locations","from":"town-a"}]
````

**Validator error:**

````text
Remove path must select a collection element
````

**One valid illustrative expected patch (other equivalent serializations may be valid):**

```json
[
  {
    "op": "remove",
    "path": "locations.town-a"
  }
]
```

**Expected final state:**

```json
{
  "locations": []
}
```

## DOT-10: Wrong element value type

**6 observations.** Models: Desktop Qwen3-VL-8B-Instruct Q4_K_M: 6.

Representative: **Desktop Qwen3-VL-8B-Instruct Q4_K_M** (`local-cb6dd200423a32cc`), [db_v3_append_value__dot_patch_v1 / ID-keyed arrays / repetition 3](failure-cases/desktop/local-cb6dd200423a32cc/0256ec0260e1215aed21c0924085d9881e0666bacea2c18f52f3a4a22f280df5.json).

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

**One valid illustrative expected patch (other equivalent serializations may be valid):**

```json
[
  {
    "op": "add",
    "path": "locations",
    "value": "town-d"
  }
]
```

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

All 246 Unity failed observations were reviewed: 162 prefix-only, 42 slash-only, 33 fence-only, six prefix+slash and three prefix+fence. All 48 slash-containing Unity failures occurred with Full paths input. These overlap counts differ from the primary-label totals because one response can have several issues.

For fenced responses only, a separate diagnostic parsed the fenced content and applied the unchanged dot interpreter to a copy of the initial state. Thirty-three reached the exact expected state; three still failed for missing collection prefixes. This did not alter a benchmark score, response, grader or prompt. No alternative pass total is reported.

Optimized controls contain different wording and are secondary comparisons. Original930 has no Q4_K_S or Unity baseline. The corrected NOOP remains separately recorded.
