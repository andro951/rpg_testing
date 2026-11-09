# JavaScript intent-parser prototype

A standalone, no-install prototype using the actual GrammarForge 2.1.4 runtime. It is not wired into the research acceptor, approved model prompts, or benchmark scoring.

Public entry point: `require("./index.cjs")`. `normalizeIntent(text, document, options)` returns only the selected patch format. Offline replay: `node replay.cjs parity-fixtures.json` (append `--json-patch` for RFC output).

Run all checks with `node run-all.cjs` (or `npm test`). Run `node demo.cjs` for a complete example. Requires Node 18 or newer.

## Independent stages

1. `buildPrompt({request,document,idKey})`: constructs model instructions without expected answers.
2. `parseIntent(text)`: actual GrammarForge structural and operation grammars produce a separate intent IR. `parseIntentWithDiagnostics` also reports recovered outer wrappers.
3. `convertIntent(ir, document, {json_patch:false,idKey:'id'})`: resolves ambiguous roles only when unique, checks current state, and returns custom patches by default.
4. `applyPatch(document, customPatch)`: applies custom operations atomically to a clone.

Setting `json_patch:true` returns standard RFC6902 **instead** of custom patches. Standard paths contain state-dependent indices and must be applied to the matching starting document in their exact generated order. Copy/move compile to append-copy and optional source removal, not positional insertion.

## Supported semantics

- Update an existing value; append to a collection; remove a selected element/field; copy or move to a different collection.
- Arrays select object elements by typed ID and primitive elements by their own unique typed JSON value, never by position. Numeric `1` and string `"1"` are distinct identities.
- Component order and optional labels vary. From/source and to/destination are directional. One directional label can determine the other role. Two unlabeled paths or a path/value pair require one uniquely valid interpretation; ambiguous alternatives reject.
- Quoted strings and recursive JSON values preserve contents and types. Duplicate JSON keys, nonfinite numbers and invalid JSON values reject.
- Parentheses, braces and brackets group intent components. A single missing outer wrapper can be recovered with diagnostics; broken inner JSON is never repaired by guessing.
- Newlines are candidate boundaries. All complete grammatical partitions are considered; accept exactly one. Newlines inside values remain inside values. Explicit groups and semicolons are recommended for clear boundaries.
- Default safety bounds: 65,536 text characters, depth 64, 256 operations, 4,096 boundary attempts. Options can adjust these explicit limits.

## Deliberate limits

This is still a prototype, not a production-readiness claim. Broader alias decisions are listed in ALIASES.md. Per-collection schema-declared ID support is not integrated; the current option is one `idKey`. Root append uses an empty path; root replacement/removal conservatively reject. Identity-field edits preserve scalar types and must maintain collection uniqueness. Same-collection transfers, source-descendant transfers, duplicate identities and positional insertion reject. Domain-schema validity and whether a patch satisfies the original free-form request remain host responsibilities.

The parser is not a JSON repair oracle and does not consult expected answers. Conventional JSON-style operation objects work for the supported operation vocabulary; this is not unrestricted RFC6902 input support.

## Verification

- 57 focused unit checks.
- 2,253 generated/end-to-end checks: field permutations, four delimiters, three group styles, whitespace/comma/newline variants, positive and negative cases. Standard patches are applied by an independent reference interpreter and compared with the custom updater.
- 410 optional-label/order/newline/limit checks.
- 177 whitespace/quoted-value regressions; 21 identity/precision edge checks; 21 public-API checks.
- Offline replay of all 2,651 saved prepared fixtures, preserving raw text and proving expected states do not influence normalization.
- 8 JSON-input safety checks covering accessors, symbols, sparse arrays and other non-JSON inputs.
- 2,651 JSON-representable parity fixtures exported across `parity-fixtures.json` and `optional-parity-fixtures.json`. Some JavaScript-only invalid-value tests cannot be represented in JSON.

These are deterministic software tests with simulated model responses, **not live model trials or measured accuracy gains**. Matching native C# and Python ports are included in `../intent-parser-csharp` and `../intent_parser`. See `ROLLBACK-NOTES.md` for this corrected current-contract checkpoint and regenerated validation.

## Upstream provenance

Runtime: `andro951/GrammarForge`, commit `4bbdff99f6e7224cfca0788b0d34772a1949230c`, version 2.1.4. Its source files are unchanged. `load-forge.cjs` loads the public runtime in a separate Node VM using the upstream bundle order. The author's ZON/test grammars were inspected privately but are not redistributed here. See instructions in `GrammarForge/grammarForge/grammarForge.js`.
