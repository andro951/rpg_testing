# Saved-response strict-format audit: 2026-11-11

## Scope and evidence

Exactly 2,232 observations: six models/providers, 372 conditions each, all 21 current cases and six active output formats. Source selection is exclusively the package full_372_per_model.csv, combining 1,140 fresh missing-condition results and 1,092 replayed current-series results. No older replacement runs, new inference, response repair or semantic rescoring. Every original result file SHA-256 matched its manifest reference, and all original sources plus the package were rehashed after reading and again after writing the supplemental reports. When pipeline outputs.patch was saved, it matched the saved patch call text wherever a call existed. Otherwise the original saved patch call text was used directly; absent evidence is rejected rather than replaced with invented empty text. All original files and scores remain unchanged.

Package: `CSC592-complete-current-results.zip`
Package SHA-256: `e4cba282a9642bf68771ae03718de1a2b87f069d23350604e6b3fad86d3e6167`
Validator: `strict-format-compliance-v1` / `0eedd76b942d7765f2cb7e6f33f30b6b924b42afd77c962800f5eddeaebb9fee`

Semantic pass below is the package current-intent replay verdict, not a new score and not necessarily the older score stored in a source result. The local row ledger preserves both independently. Strict compliance tests syntax alone; database target existence, field/selector roles, operation suitability and final values stay separate semantic checks.

## Results

| Model | N | Semantic pass | Strict pass | Both pass | Semantic pass, strict fail | Strict pass, semantic fail | Both fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Perchance | 372 | 371 | 318 | 317 | 54 | 1 | 0 |
| Qwen3-VL-8B Q4_K_M | 372 | 344 | 332 | 328 | 16 | 4 | 24 |
| Qwen3.5-2B Q8_0 | 372 | 298 | 346 | 292 | 6 | 54 | 20 |
| Qwen3.5-4B Q8_0 | 372 | 366 | 367 | 361 | 5 | 6 | 0 |
| Qwen3.5-9B Q4_K_M | 372 | 351 | 362 | 351 | 0 | 11 | 10 |
| Qwen3.5-9B Q4_K_S | 372 | 357 | 363 | 357 | 0 | 6 | 9 |
| TOTAL | 2232 | 2087 | 2088 | 2006 | 81 | 82 | 63 |

## Model and format counts

| Model | Format | N | Semantic pass | Strict pass | Both pass | Semantic pass, strict fail | Strict pass, semantic fail | Both fail |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Perchance | end_marked_line | 62 | 62 | 62 | 62 | 0 | 0 | 0 |
| Perchance | json_dot | 62 | 62 | 35 | 35 | 27 | 0 | 0 |
| Perchance | json_slash | 62 | 62 | 35 | 35 | 27 | 0 | 0 |
| Perchance | literal_line | 62 | 62 | 62 | 62 | 0 | 0 | 0 |
| Perchance | path_list | 62 | 62 | 62 | 62 | 0 | 0 | 0 |
| Perchance | typed_lines | 62 | 61 | 62 | 61 | 0 | 1 | 0 |
| Qwen3-VL-8B Q4_K_M | end_marked_line | 62 | 48 | 47 | 47 | 1 | 0 | 14 |
| Qwen3-VL-8B Q4_K_M | json_dot | 62 | 62 | 62 | 62 | 0 | 0 | 0 |
| Qwen3-VL-8B Q4_K_M | json_slash | 62 | 62 | 62 | 62 | 0 | 0 | 0 |
| Qwen3-VL-8B Q4_K_M | literal_line | 62 | 59 | 56 | 56 | 3 | 0 | 3 |
| Qwen3-VL-8B Q4_K_M | path_list | 62 | 58 | 46 | 46 | 12 | 0 | 4 |
| Qwen3-VL-8B Q4_K_M | typed_lines | 62 | 55 | 59 | 55 | 0 | 4 | 3 |
| Qwen3.5-2B Q8_0 | end_marked_line | 62 | 47 | 61 | 47 | 0 | 14 | 1 |
| Qwen3.5-2B Q8_0 | json_dot | 62 | 62 | 62 | 62 | 0 | 0 | 0 |
| Qwen3.5-2B Q8_0 | json_slash | 62 | 56 | 62 | 56 | 0 | 6 | 0 |
| Qwen3.5-2B Q8_0 | literal_line | 62 | 51 | 61 | 51 | 0 | 10 | 1 |
| Qwen3.5-2B Q8_0 | path_list | 62 | 55 | 49 | 49 | 6 | 0 | 7 |
| Qwen3.5-2B Q8_0 | typed_lines | 62 | 27 | 51 | 27 | 0 | 24 | 11 |
| Qwen3.5-4B Q8_0 | end_marked_line | 62 | 62 | 62 | 62 | 0 | 0 | 0 |
| Qwen3.5-4B Q8_0 | json_dot | 62 | 62 | 62 | 62 | 0 | 0 | 0 |
| Qwen3.5-4B Q8_0 | json_slash | 62 | 61 | 62 | 61 | 0 | 1 | 0 |
| Qwen3.5-4B Q8_0 | literal_line | 62 | 62 | 62 | 62 | 0 | 0 | 0 |
| Qwen3.5-4B Q8_0 | path_list | 62 | 61 | 57 | 56 | 5 | 1 | 0 |
| Qwen3.5-4B Q8_0 | typed_lines | 62 | 58 | 62 | 58 | 0 | 4 | 0 |
| Qwen3.5-9B Q4_K_M | end_marked_line | 62 | 56 | 59 | 56 | 0 | 3 | 3 |
| Qwen3.5-9B Q4_K_M | json_dot | 62 | 62 | 62 | 62 | 0 | 0 | 0 |
| Qwen3.5-9B Q4_K_M | json_slash | 62 | 62 | 62 | 62 | 0 | 0 | 0 |
| Qwen3.5-9B Q4_K_M | literal_line | 62 | 58 | 59 | 58 | 0 | 1 | 3 |
| Qwen3.5-9B Q4_K_M | path_list | 62 | 59 | 59 | 59 | 0 | 0 | 3 |
| Qwen3.5-9B Q4_K_M | typed_lines | 62 | 54 | 61 | 54 | 0 | 7 | 1 |
| Qwen3.5-9B Q4_K_S | end_marked_line | 62 | 56 | 59 | 56 | 0 | 3 | 3 |
| Qwen3.5-9B Q4_K_S | json_dot | 62 | 62 | 62 | 62 | 0 | 0 | 0 |
| Qwen3.5-9B Q4_K_S | json_slash | 62 | 61 | 62 | 61 | 0 | 1 | 0 |
| Qwen3.5-9B Q4_K_S | literal_line | 62 | 57 | 59 | 57 | 0 | 2 | 3 |
| Qwen3.5-9B Q4_K_S | path_list | 62 | 59 | 59 | 59 | 0 | 0 | 3 |
| Qwen3.5-9B Q4_K_S | typed_lines | 62 | 62 | 62 | 62 | 0 | 0 | 0 |

## Rejection errors by model and format

Each rejected response contributes its first strict error; a response may contain additional defects. JSON errors are parser messages, not semantic diagnoses.

| Model | Format | First error | N |
|---|---|---|---:|
| Perchance | json_dot | Expecting value: line 1 column 1 (char 0) | 27 |
| Perchance | json_slash | Expecting value: line 1 column 1 (char 0) | 27 |
| Qwen3-VL-8B Q4_K_M | end_marked_line | A nonempty original textual response is required | 3 |
| Qwen3-VL-8B Q4_K_M | end_marked_line | Extra data: line 1 column 2 (char 1) | 3 |
| Qwen3-VL-8B Q4_K_M | end_marked_line | Extra data: line 1 column 3 (char 2) | 2 |
| Qwen3-VL-8B Q4_K_M | end_marked_line | Extra data: line 1 column 46 (char 45) | 5 |
| Qwen3-VL-8B Q4_K_M | end_marked_line | Extra data: line 1 column 51 (char 50) | 1 |
| Qwen3-VL-8B Q4_K_M | end_marked_line | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes | 1 |
| Qwen3-VL-8B Q4_K_M | literal_line | A nonempty original textual response is required | 3 |
| Qwen3-VL-8B Q4_K_M | literal_line | Expected one exact literal-text operation per line | 2 |
| Qwen3-VL-8B Q4_K_M | literal_line | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes | 1 |
| Qwen3-VL-8B Q4_K_M | path_list | A nonempty original textual response is required | 3 |
| Qwen3-VL-8B Q4_K_M | path_list | Expecting value: line 1 column 1 (char 0) | 1 |
| Qwen3-VL-8B Q4_K_M | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes | 12 |
| Qwen3-VL-8B Q4_K_M | typed_lines | A nonempty original textual response is required | 3 |
| Qwen3.5-2B Q8_0 | end_marked_line | text: requires a final &#124; end marker | 1 |
| Qwen3.5-2B Q8_0 | literal_line | Expected one exact literal-text operation per line | 1 |
| Qwen3.5-2B Q8_0 | path_list | Expected one exact path-list operation per line | 7 |
| Qwen3.5-2B Q8_0 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes | 6 |
| Qwen3.5-2B Q8_0 | typed_lines | Expected an exact typed-line operation header | 3 |
| Qwen3.5-2B Q8_0 | typed_lines | Expected exactly one typed value line | 1 |
| Qwen3.5-2B Q8_0 | typed_lines | Transfer requires an immediately following to: path | 2 |
| Qwen3.5-2B Q8_0 | typed_lines | Typed-line paths cannot contain empty parts | 1 |
| Qwen3.5-2B Q8_0 | typed_lines | Unterminated string starting at: line 1 column 16 (char 15) | 1 |
| Qwen3.5-2B Q8_0 | typed_lines | Unterminated string starting at: line 1 column 2 (char 1) | 1 |
| Qwen3.5-2B Q8_0 | typed_lines | Unterminated string starting at: line 1 column 7 (char 6) | 2 |
| Qwen3.5-4B Q8_0 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes | 5 |
| Qwen3.5-9B Q4_K_M | end_marked_line | Expected one exact literal-text operation per line | 3 |
| Qwen3.5-9B Q4_K_M | literal_line | Expected one exact literal-text operation per line | 3 |
| Qwen3.5-9B Q4_K_M | path_list | Expected one exact path-list operation per line | 3 |
| Qwen3.5-9B Q4_K_M | typed_lines | Expected an exact typed-line operation header | 1 |
| Qwen3.5-9B Q4_K_S | end_marked_line | Expected one exact literal-text operation per line | 3 |
| Qwen3.5-9B Q4_K_S | literal_line | Expected one exact literal-text operation per line | 3 |
| Qwen3.5-9B Q4_K_S | path_list | Expected one exact path-list operation per line | 3 |

## Response inspection

Reviewed all 247 distinct (requested format, exact raw text) outputs: 85 rejected and 162 accepted. Duplicate texts share the same syntax judgement, but every observation retains its own manifest row and original semantic verdict. Long repetitive outputs were inspected by their complete set of line patterns, opening records and exact trailing fragment; they were not accepted merely because a prefix was valid.

No false rejection was found in this saved-response cohort. The 81 semantic-pass/strict-fail observations are genuine requested-syntax violations, not evidence that their strict validators should relax. Examples include correct operations wrapped in Markdown fences, alternative no-change prose, an extra end marker after JSON, missing operation/type labels, and quoted or dotted components where bracketed unquoted comma-separated components are required. Empty responses and truncated records are not complete requested-format outputs.

No state-independent syntax false acceptance was found in the accepted cohort. This does not assert semantic correctness: 82 strict passes have failing package intent verdicts. Wrong values, wrong operation targets, extra unrelated syntactically valid records, copied examples, scalar/object mismatches, and unquoted collection selectors cannot generally be rejected using syntax alone. Unquoted slash components are also legal object field names, so rejecting them as missing selector quotes would require inspecting state. Similarly quotes in literal text are literal value data; determining that they were unwanted outer quotation marks requires the requested value.

Two particularly long accepted responses (manifest rows 162 and 210) end with `remove: /example`, which is a syntactically complete record even though the generation is evidently repetitive and the target is wrong. Their original semantic failure remains independent. Rejected long typed responses have concrete malformed terminal syntax: incomplete object strings, missing typed value labels, incomplete transfer destinations, or incomplete operation headers. Row 228 additionally copies prompt prose; row 222 rewrites the input display.

Code review outside this saved cohort identified synthetic edge cases involving interior quotation marks and outer-JSON-escaped control characters in slash property names, plus JSON integers longer than Python's default 4,300-digit conversion limit. The implementation owner fixed these with focused tests before the final replay reported here. They do not occur among the cohort rejections. General adversarial correctness is established by tests/code review, not by claiming this finite sample proves all future outputs.

## Portable row-level evidence

The adjacent `strict-format-cohort-audit-2026-11-11/cohort-rows.jsonl` contains all 2,232 row-level strict outcomes, original package semantic labels, result hashes and relative source-run/result references. `cohort-response-groups.jsonl` contains all 247 exact original synthetic response variants and their row memberships. The stable group identifier is requested format plus SHA-256 of the UTF-8 raw response. No user directory paths, credentials or runtime settings are included in these portable companions.

## Inspection index

Rows refer to one-based data rows of the original manifest. Full original text, source path/hash, package semantic verdict, frozen source score and strict result are preserved in `.local/reports/strict-format-audit-final/rows.jsonl`. `unique-responses.txt` groups only exact format/text duplicates. `audit.json` provides machine-readable counts. The reproducible replay entry point is `scripts/audit_format_cohort.py --package <exact-package-path> --output <report-directory>`. These are supplemental reports, not replacements for historical results.

| Rejected unique output | Manifest rows | Format | Checked defect |
|---:|---|---|---|
| 1 | 217 | end_marked_line | text: requires a final &#124; end marker. Original: 'set sample.headings: text:blue\nset sample.headings: text:serif' |
| 2 | 961 | end_marked_line | No-change response must be exactly none. |
| 3 | 967, 973, 1339, 1345 | end_marked_line | No-change response must be exactly none. |
| 4 | 1333 | end_marked_line | No-change response must be exactly none. |
| 5 | 1489 | end_marked_line | Extra data: line 1 column 51 (char 50). Original: 'append items: json:{"item_id": "item-5", "name": "Sword", "count": 1}&#124;' |
| 6 | 1495, 1501, 1507, 1513, 1519 | end_marked_line | Extra data: line 1 column 46 (char 45). Original: 'append items: json:{"item_id":"item-5","name":"Sword","count":1}&#124;' |
| 7 | 1705, 1711, 1717 | end_marked_line | Empty original response. |
| 8 | 1747 | end_marked_line | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'remove locations."town-a"' |
| 9 | 1813, 1819 | end_marked_line | Extra data: line 1 column 3 (char 2). Original: 'set items.item-17.details.durability: json:80&#124;' |
| 10 | 1837 | end_marked_line | Extra data: line 1 column 2 (char 1). Original: 'set items.item-17.count: json:9&#124;' |
| 11 | 1849, 1855 | end_marked_line | Extra data: line 1 column 2 (char 1). Original: 'set workspace.inventory.items.item-26.count: json:7&#124;' |
| 12 | 1868 | json_dot | Markdown fences around JSON are explicitly forbidden. |
| 13 | 1934, 1952 | json_dot | Markdown fences around JSON are explicitly forbidden. |
| 14 | 1940, 1958, 1964 | json_dot | Markdown fences around JSON are explicitly forbidden. |
| 15 | 1970, 1988 | json_dot | Markdown fences around JSON are explicitly forbidden. |
| 16 | 1976, 1982, 1994, 2000 | json_dot | Markdown fences around JSON are explicitly forbidden. |
| 17 | 2006, 2012, 2018, 2024, 2030, 2036 | json_dot | Markdown fences around JSON are explicitly forbidden. |
| 18 | 2042 | json_dot | Markdown fences around JSON are explicitly forbidden. |
| 19 | 2048, 2054, 2060, 2066 | json_dot | Markdown fences around JSON are explicitly forbidden. |
| 20 | 2132 | json_dot | Markdown fences around JSON are explicitly forbidden. |
| 21 | 2168 | json_dot | Markdown fences around JSON are explicitly forbidden. |
| 22 | 2204 | json_dot | Markdown fences around JSON are explicitly forbidden. |
| 23 | 2222 | json_dot | Markdown fences around JSON are explicitly forbidden. |
| 24 | 1887 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 25 | 1935, 1959 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 26 | 1965 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 27 | 1971 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 28 | 1977, 1989, 1995 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 29 | 2007, 2013 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 30 | 2025 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 31 | 2043, 2061 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 32 | 2049, 2055, 2067 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 33 | 2103, 2133, 2145 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 34 | 2139 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 35 | 2157 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 36 | 2181, 2193 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 37 | 2205 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 38 | 2211 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 39 | 2217, 2229 | json_slash | Markdown fences around JSON are explicitly forbidden. |
| 40 | 316 | literal_line | Expected one exact literal-text operation per line. Original: 'dot.profile.hair: text:black' |
| 41 | 964 | literal_line | No-change response must be exactly none. |
| 42 | 970, 976, 1342, 1348 | literal_line | No-change response must be exactly none. |
| 43 | 1336 | literal_line | No-change response must be exactly none. |
| 44 | 1708, 1714, 1720 | literal_line | Empty original response. |
| 45 | 1750 | literal_line | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'remove locations."town-a"' |
| 46 | 1828 | literal_line | Expected one exact literal-text operation per line. Original: 'set items.item-17.count: 9' |
| 47 | 1846 | literal_line | Expected one exact literal-text operation per line. Original: 'set workspace.inventory.items.item-26.count: 7' |
| 48 | 221 | path_list | Expected one exact path-list operation per line. Original: '[items.item-42.name]: "Blue"\n[items.item-17.name]: "Serif"\n[items.item-83.name]: "Blue"\n[items.item-26.name]: "Serif"' |
| 49 | 227 | path_list | Expected one exact path-list operation per line. Original: '[items]: [\n  "item-42": {\n    "item_id": "item-42",\n    "name": "Sword",\n    "count": 3\n  },\n  "item-17": {\n    "item_id": "item-17",\n    "name": "Sword",\n    "count": 8\n  },\n  "item-83": {\n    "item_id": "item-83",\n    "name": "Potion",\n    "count": 2\n  },\n  "item-26": {\n    "item_id": "item-26",\n    "name": "Shield",\n    "count": 6\n  }\n]' |
| 50 | 233 | path_list | Expected one exact path-list operation per line. Original: '[items]: {\n  "item_id": "item-42",\n  "name": "Sword",\n  "count": 3\n},\n{\n  "item_id": "item-17",\n  "name": "Sword",\n  "count": 8\n},\n{\n  "item_id": "item-83",\n  "name": "Potion",\n  "count": 2\n},\n{\n  "item_id": "item-26",\n  "name": "Shield",\n  "count": 6\n}\n}' |
| 51 | 311, 317 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'set [profile.hair]: "black"' |
| 52 | 323 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'set [items.item-17, details.durability]: 80' |
| 53 | 329 | path_list | Expected one exact path-list operation per line. Original: '[items, item-17, details.durability]: 80' |
| 54 | 335 | path_list | Expected one exact path-list operation per line. Original: '[items, item-17, details, durability]: 80' |
| 55 | 341 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'set [items.item-17, count]: 9' |
| 56 | 347 | path_list | Expected one exact path-list operation per line. Original: '[items, item-17, count]: 9' |
| 57 | 359 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'set [workspace.inventory.items.item-26, count]: 7' |
| 58 | 365 | path_list | Expected one exact path-list operation per line. Original: '[workspace.inventory.items, item-26, count]: 7' |
| 59 | 371, 731, 1847 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'set [workspace.inventory.items, item-26, count]: 7' |
| 60 | 635, 671, 1745, 1751, 1787 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'remove [locations, "town-a"]' |
| 61 | 701, 707 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'set [items, item-17, details.durability]: 80' |
| 62 | 965 | path_list | No-change response must be exactly none. |
| 63 | 971, 977 | path_list | No-change response must be exactly none. |
| 64 | 1337 | path_list | No-change response must be exactly none. |
| 65 | 1343 | path_list | No-change response must be exactly none. |
| 66 | 1349 | path_list | No-change response must be exactly none. |
| 67 | 1607, 1625 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'copy [locations, "town-a"] -> [archived_locations]' |
| 68 | 1643, 1661 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'move ["items", "item-17"] -> ["storage"]' |
| 69 | 1679, 1697 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'move ["locations", "town-a"] -> ["archived_locations"]' |
| 70 | 1709, 1715, 1721 | path_list | Empty original response. |
| 71 | 1733, 1769 | path_list | Path components require unquoted letters, digits, hyphens, underscores or %HH escapes. Original: 'remove [items, "item-83"]' |
| 72 | 1841 | path_list | Expecting value: line 1 column 1 (char 0). Original: 'set [items, item-17]: count: 9' |
| 73 | 78 | typed_lines | Inspected repeated line patterns and exact tail; Unterminated string starting at: line 1 column 7 (char 6). Tail: 'em-90\nobject: {"id":"item-90","status":"active"}\n\nappend: /storage/item-90\nobject: {"id":"' |
| 74 | 84 | typed_lines | Inspected repeated line patterns and exact tail; Expected exactly one typed value line. Tail: 'nt\nnumber: 1\n\nset: /example_copy/status\ntext: ready\n\nappend: /example_copy_elements\nobject' |
| 75 | 102 | typed_lines | Inspected repeated line patterns and exact tail; Typed-line paths cannot contain empty parts. Tail: 'ample_elements/"transfer-id"\nto: /example_archive\n\ncopy: /example_elements/"keep-id"\nto: /' |
| 76 | 120 | typed_lines | Inspected repeated line patterns and exact tail; Transfer requires an immediately following to: path. Tail: '"transfer-id"\n\nchange: /example/count\nnumber: 1\n\nmove: /example_elements/"transfer-id"\nto:' |
| 77 | 150 | typed_lines | Inspected repeated line patterns and exact tail; Transfer requires an immediately following to: path. Tail: 'ount\nnumber: 1\n\nmove: /example_elements/"transfer-id"\nto: /example_archive\n\ncopy: /example' |
| 78 | 156 | typed_lines | Inspected repeated line patterns and exact tail; Unterminated string starting at: line 1 column 2 (char 1). Tail: '/example_backups\n\nset: /example/status\ntext: ready\n\nappend: /example_elements\nobject: {"id' |
| 79 | 168 | typed_lines | Inspected repeated line patterns and exact tail; Unterminated string starting at: line 1 column 7 (char 6). Tail: 'backups\n\nset: /example/status\ntext: ready\n\nappend: /example_elements\nobject: {"id":"new-id' |
| 80 | 174 | typed_lines | Inspected repeated line patterns and exact tail; Unterminated string starting at: line 1 column 16 (char 15). Tail: 'kups\n\nset: /example/status\ntext: ready\n\nappend: /example_elements\nobject: {"id":"new-id","' |
| 81 | 222 | typed_lines | Inspected repeated line patterns and exact tail; Expected an exact typed-line operation header. Tail: 'bject>\nitems.item-26.item_id: "item-26"\nitems.item-26.name: "Shield"\nitems.item-26.count: ' |
| 82 | 228 | typed_lines | Inspected repeated line patterns and exact tail; Expected an exact typed-line operation header. Tail: '      "count": 6\n    }\n  ]\n}\n\nTask:\nThe documentation uses blue headings and a serif font.' |
| 83 | 234 | typed_lines | Inspected repeated line patterns and exact tail; Expected an exact typed-line operation header. Tail: '94/name\ntext: Blue\n\nset: /items/595/name\ntext: Serif\n\nset: /items/596/name\ntext: Blue\n\nset' |
| 84 | 978 | typed_lines | No-change response must be exactly none. |
| 85 | 1710, 1716, 1722 | typed_lines | Empty original response. |

## Replay safeguards and tests

The importable audit utility rejects wrong cohort size, duplicate conditions, incomplete model/format coverage, checksum mismatches, missing/nontext original responses and output/call disagreement. Its output directory must be outside package and source-run evidence directories. Existing conflicting output artifacts are never replaced; identical reruns are idempotent. Ten focused tests in `tests/test_format_cohort_audit.py` passed, including explicitly saved empty responses and original call-only partial outputs.
