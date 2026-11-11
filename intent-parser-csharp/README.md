# Native C# intent parser

A dependency-free .NET 8 port of the JavaScript GrammarForge intent-parser prototype. The native ordered-expression interpreter consumes the embedded `grammar-spec.json`, generated from the included program, operation, and lexical-tree grammars; no Node.js, JavaScript engine, network service, or live model is needed at runtime.

## Run

```sh
dotnet build
dotnet run --no-build -- self-test
dotnet run --no-build -- check fixtures/parity-fixtures.json
dotnet run --no-build -- check fixtures/optional-parity-fixtures.json
dotnet run --no-build -- check robustness-parity-fixtures.json
dotnet run --no-build -- check fixtures/current-revision-fixtures.json
dotnet run --no-build -- check fixtures/current-contract-regressions.json
dotnet run --no-build -- replay fixtures/shared-fixtures.json
dotnet run --no-build -- replay fixtures/shared-fixtures.json --json-patch
```

`check` verifies parsing, custom and RFC6902 conversion, final-state equality, immutability, expected rejection, and an independent RFC6902 interpreter. `replay` preserves original raw output and its SHA-256 hash. Expected answers are evaluated only after normalization/application, never supplied to parsing or conversion. These are offline software checks, not live-model accuracy measurements.

## API

Namespace `Csc592.IntentParser`, class `IntentParser`:

- `BuildPrompt(string request, JsonNode? document, string idKey = "id")`
- `ParseIntent(string text, IntentOptions? options = null)`
- `ParseIntentWithDiagnostics(string text, IntentOptions? options = null)`
- `ConvertIntent(JsonArray ir, JsonNode? input, IntentOptions? options = null)`
- `NormalizeIntent(string text, JsonNode? document, IntentOptions? options = null)`
- `ApplyPatch(JsonNode? input, JsonArray patch, IntentOptions? options = null)`
- `ReplayPrepared(JsonArray records, IntentOptions? options = null)`

`IntentOptions` defaults: `JsonPatch=false`, `IdKey="id"`, `MaxChars=65536` UTF-16 units, `MaxDepth=64`, `MaxOperations=256`, `MaxBoundaryAttempts=4096`, `PathSyntax=null`, `OutputFormat=null`. Return objects preserve the JavaScript/Python wire keys (`op`, `path`, `value`, `from`, `to`, `operations`, `diagnostics`). CLR naming follows C# conventions.

Default normalization returns only custom ID-addressed patches. `JsonPatch=true` returns only RFC6902 output, compiled against the exact input state in sequential order. Copy/move emit append-copy plus optional source removal, not positional insertion. Input objects are cloned; failures never partially mutate the caller's input.

`--json-lines` reads requests from standard input and writes one `{"ok":true,"result":...}` or `{"ok":false,"error":...}` result per line. Actions are `parse`, `diagnostics`, `normalize`, `convert`, `apply`, `prompt`, and `replay`. Options use portable wire names `json_patch`, `idKey`, `maxChars`, `maxDepth`, `maxOperations`, and `maxBoundaryAttempts`, `pathSyntax`, and `output_format` (also accepted as `outputFormat`). This provides a process-level conformance interface for tests and other hosts.

## Current host paths

`PathSyntax="value_patch"` is an explicit CSC592 host option for typed slash paths. Unquoted scalar path parts retain their JSON types; quoted embedded JSON string parts preserve literal strings and slashes. The default remains RFC6901-style quoted pointer strings with string parts. Array-form paths always preserve explicit scalar types. The current host operation `replace` maps to update only in this explicitly selected mode. Generic intent accepts `set` as an update alias; `replace` still requires the host option.

Normalization accepts the documented intent grammar only. RFC6902 remains an output format; no RFC input importer or automatic input-dialect bridge is provided.

One exact enclosing bare/JSON Markdown fence can be removed with `MARKDOWN_FENCE_REMOVED` diagnostics. Prefix/suffix prose is not stripped. The complete program AST determines operation groups and strict JSON values. A bounded newline-partition check rejects ambiguous operation boundaries without discovering or repairing operations.

## Shared line formats

The shared grammar also recognizes header and inline typed operations, two-line JSON values, arrow transfers, and explicit `none`. These use the same operation AST as generic intent rather than separate format readers. Raw slash line paths preserve typed selectors, embedded quoted strings, and literal field spaces, including trailing spaces in header paths.

`OutputFormat` selects only the text value codec: `typed_lines` preserves raw text after removing exactly one separator space; `literal_line` decodes `\\`, `\n`, `\r`, `\t`, `\s`, and `\"`; `end_marked_line` requires and drops only the final `|` and decodes `\\`, `\n`, `\r`, and `\t`. The default preserves the raw remainder after `text:`. Text extends to the physical newline, retaining punctuation and trailing spaces, and must contain valid Unicode. Numeric typed values accept finite safe JSON numbers, including exponent notation and an optional leading plus sign. `object:` and `list:` can denote empty containers; `json:` does not accept string values.

`change` requires a typed number and produces an update with `semantic: "numeric_delta"`. Removals parsed with `OutputFormat="typed_lines"` carry `semantic: "typed_remove"`. A state-aware host must lower these markers before calling the ordinary patch converter. `ConvertIntent` and `NormalizeIntent` deliberately reject unlowered markers rather than silently applying a delta as an absolute update.

The literal verb `add` carries `semantic: "literal_add"` with canonical `op: "append"` in parsed IR. `ConvertIntent` resolves its existing target against the current sequential document state: an array means append; an existing object field means update. Root scalar replacement, whole non-array collection-element replacement, and missing-field creation are rejected. `append` and `insert` remain array-only aliases. Unlabeled path/value candidates retain this marker during uniqueness checks. Returned custom patches have the resolved operation and no semantic marker; `ApplyPatch` rejects unlowered semantic intents.

## Safety and limits

Paths identify unordered object elements by typed ID and primitive elements by their own unique typed value. A primitive `1` and object `{ "id": 1 }` collide in the same collection because both have the same selector. String `"1"`, number `1`, boolean `true`, and `null` remain distinct. Append, replacement, transfers, and identity edits reject ambiguous duplicates.

Literal values require intact strict JSON. Duplicate keys, unpaired UTF-16 surrogates, nonfinite or unsafe integer numbers, and nonzero numbers that underflow to zero reject. Valid Unicode surrogate pairs work. The numeric contract intentionally matches JavaScript binary64, rather than claiming arbitrary-precision JSON arithmetic.

Newly introduced nonscalar object IDs also reject. Objects without IDs remain a host-schema concern.

Root replacement/removal, positional insertion, same-collection transfers, transfer into the source/its descendants, and unresolved role ambiguity reject. One unmatched outer wrapper can recover with a diagnostic; inner malformed JSON is never repaired by guessing. Domain schema validation and whether a patch fulfills the user's actual request remain host responsibilities.

This is a prototype port, not a production-readiness claim. `differential.cjs` is an optional development-only comparison with the reference JavaScript project, and is not a runtime dependency. Error wording can differ across language runtimes; accepted IR/patch/final-state semantics and rejection categories are tested.

## Validation commands

`./run-tests.sh` runs the dependency-free native suite. Optional developer comparisons:

```sh
JS_REFERENCE=../csc592-intent-parser DOTNET=dotnet node differential.cjs
PYTHON_REFERENCE=../rpg_testing DOTNET=dotnet python3 cross-language-test.py
```

These compare acceptance, diagnostics, intent IR, both patch formats, offline replay, hashes, prompt strings, typed host paths, and numeric/Unicode edge cases. Diagnostic/error wording is not a stable cross-language API.

## Grammar source

Edit the authoritative grammar files in `intent-parser-js`, then run `node intent-parser-js/build-grammar-spec.cjs` from the repository root to regenerate all three ports. The generated specification preserves token priority, ordered alternatives, greedy quantifiers, and source hashes. C# interprets these productions directly with capture rollback and zero-progress guards; it does not maintain separate handwritten production methods.
