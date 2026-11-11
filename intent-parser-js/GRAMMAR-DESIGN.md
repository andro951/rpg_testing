# Grammar-first intent language

## Source of truth

`intent.grammar` is the complete readable GrammarForge grammar. Its top level is a program containing zero or more operations, recursively grouped operation lists, and an optional enclosing Markdown fence. It recognizes remove, add, update, and move/copy as different productions, with the required components in every supported order.

`operation.grammar` is generated from the operation section of that file. It is used when checking alternative newline partitions. `tokens.grammar` is a structural token-tree adapter used by conversion and ambiguity checks; it is **not** the grammar which decides whether a complete program is valid.

JavaScript runs the actual bundled GrammarForge parser. `build-grammar-spec.cjs` exports GrammarForge's own parsed productions and token definitions to `grammar-spec.json`. C# and Python interpret that same generated specification. Their syntax rules are no longer separately handwritten production functions. C# embeds the specification in its assembly; a Python distribution must include it beside `parse.py`.

After editing `intent.grammar` or `tokens.grammar`, run:

```
node intent-parser-js/build-grammar-spec.cjs
node intent-parser-js/build-grammar-spec.cjs --check
node intent-parser-js/run-all.cjs
python -m unittest discover -s tests -v
```

The exporter preserves alternative order and greedy repetition. It rejects unsupported exporter constructs rather than approximating them, verifies references, and independently checks nullable repetitions and nullable-prefix left recursion. This supplements the upstream GrammarForge checks without changing its bundled source.

## What the grammar now decides

- A remove operation requires an operation name and one path.
- Add/update require an operation name, a path, and a JSON value. The illustrative two-part update sketch does not remove its required new value.
- Move/copy require an operation name and two paths. Source and destination labels have separate productions. At least one directional label can identify both roles. The existing limited two-unlabeled-path case remains available only when conversion finds one uniquely valid source/destination assignment.
- `arr_path` and `explicit_arr_path` identify array-target candidates in the AST. The syntax alone cannot prove the type of the selected state value. Unlabeled path/value roles also require a unique semantic assignment. Consumers must not treat the first AST branch as a validated state-type judgment; use the converted patch for that.
- Literal `add` appears in both add and update name groups. Its IR retains `semantic: "literal_add"`; conversion appends when the selected node is an array and updates when it is an existing object field. Root scalars and whole collection elements reject. `append` and `insert` remain append-only, while `set` canonicalizes to update.
- Parentheses, brackets, and braces can recursively group operation lists, but their pairs must match. Structured JSON values recurse separately, protecting their fields and operation-like words as data.
- Path/value/operation components have their own grammar roles and supported order permutations. No generic `component+` production accepts arbitrary collections of fields as complete operations.
- An ungrouped operation needs an explicit boundary before another ungrouped operation. Newlines, commas, and semicolons are recognized; a newline can also occur between fields of one operation. Adjacent explicit groups remain valid boundaries.
- Pretty-printed JSON values and grouped paths can contain newlines. Quotes and escapes keep their normal JSON meaning.

## Deliberately retained procedural work

These are not additional grammars hidden in parser functions:

1. **AST-to-IR conversion.** Token strings become typed paths, labels, operation names, and JSON values. Aliases are canonicalized and the public independent IR/converter/updater APIs remain unchanged.
2. **State-dependent semantics.** Resolving IDs, checking that `arr_path` selects an array, selecting a unique unlabeled path/value assignment, enforcing uniqueness and legal transfers, and applying patches require the actual document. A text grammar has no such information.
3. **JSON data safety.** Duplicate object keys, safe numeric ranges, Unicode validity, and JSON-only input checks remain semantic validation. The grammar already recognizes recursive object/array syntax; these checks prevent data loss or inconsistent cross-language results.
4. **Newline ambiguity proof (complexity exception).** GrammarForge uses ordered choice. A successful first parse is not proof that there is only one meaning. A bounded search still checks alternative complete partitions at newlines and rejects competing operation lists. Encoding every partition in grammar productions would not make this ordered-choice engine enumerate them; changing it into a parse-forest engine would be a substantially larger parser project. This code verifies the grammar's result, not repairs it. In mixed lists, explicit records and groups delimit generic runs, and each generic run retains the same proof; raw text bodies are not relexed.
5. **Conservative envelope recovery (complexity/safety exception).** The existing quote-aware scanner still recovers only one unmatched outer wrapper and reports a diagnostic. Inner broken JSON and mismatched pairs reject. Making every closer optional would permit value boundaries to move. Optional outer alternatives also interact with ordered choice and root array paths such as `[] append 3`. The tested narrow scanner remains preferable to broadening acceptance without an ambiguity proof.
6. **Resource limits.** Text length, nesting depth, operation count, and boundary-search work remain explicit limits outside language syntax.

The grammar intentionally does not decide whether an update satisfies the original natural-language request, consult expected answers, invent missing values, or repair arbitrary malformed JSON.

## Compatibility and verification

The existing shared fixtures, optional label/order tests, host path adapters, contextual literal-add semantics, and current-contract negative cases remain required. New tests exercise grammar-level rejection before conversion, recursive wrappers, nested keyword-bearing values, multiline JSON, generated-source freshness, and loop guards. A malformed bare multi-line sequence may now reject immediately as syntax rather than reaching the older ambiguous-boundary diagnostic; it still fails closed.

No new model trials, prompt edits, archived-suite activation, or research score changes are part of this revision. The separately running free-format experiment uses its frozen source copy, not this grammar.

## Explicit structured records

The shared grammar also recognizes header writes, inline writes, header and arrow transfers, typed values, and `none`. Conversion uses their named path/value AST nodes rather than a format-specific line reader. Typed slash paths preserve field whitespace and distinguish quoted selectors from numbers.

`parseIntent(text, {output_format})` uses the option only for declared text decoding and typed-remove semantics. Default text retains the exact content after its colon. `typed_lines` removes exactly one leading separator space. `literal_line` decodes backslash, newline, carriage return, tab, space and quote escapes. `end_marked_line` requires and removes a final pipe and decodes backslash, newline, carriage return and tab escapes. Other characters, quotes and brackets remain text data.

`change` requires a typed finite, safe JSON number (including exponent notation) and yields an update with `semantic: "numeric_delta"`. Removes in `typed_lines` carry `semantic: "typed_remove"`. These are host-lowering markers, not ordinary standalone patches: `convertIntent` and `normalizeIntent` reject IR bearing either of these two markers until a suitable host lowers it. This prevents silently treating a delta as replacement.

### Contextual literal add

Only the original verb `add` produces `semantic: "literal_add"` on append-shaped IR. Standalone conversion resolves the target against the current sequential document: an array receives an append; an existing object field receives an update. Root scalar replacement and whole collection-element replacement reject. Unlabeled path/value candidates are tested with this same rule before choosing a unique interpretation. `append` and `insert` remain append-only.

Conversion removes the resolved marker from custom patches. `applyPatch` rejects unresolved markers, and unknown semantics still reject. The `numeric_delta` and `typed_remove` markers continue to require host lowering.
