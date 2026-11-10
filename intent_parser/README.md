# Native Python intent parser

A dependency-free Python 3 implementation of the JavaScript intent-parser prototype,
with the same grammar-owned program structure, JSON-shaped intermediate representation, options,
state-aware conversion and atomic application stages. The C# port uses the same
contract. It does not invoke Node, a model, a provider, or the desktop.

This is an experimental library with explicit host integrations. The generic
library leaves input schemas and request correctness to its host.
The historical value-patch offline host remains available unchanged.
The current dot-path research host is now selectable in the real Workbench
runner as `dot-intent-v1`; strict baseline scoring remains the default.
See [live integration and immutable validation](../docs/live-intent-evaluation.md).
No approved prompt or saved benchmark score is changed by selecting a new run.

## Grammar ownership

`intent.grammar` defines complete programs and recursive operation groups.
`operation.grammar` defines complete operation signatures and component capture
rules. `tokens.grammar` is only the structural token-tree adapter used by semantic
conversion. Python interprets their generated `grammar-spec.json` with ordered
choice, greedy repetition and rollback; production rules and token priority are
not maintained separately in Python. Regenerate the shared artifact with
`node intent-parser-js/build-grammar-spec.cjs` from the repository root after
changing grammar sources. The bounded newline partition search only rejects
ambiguous interpretations; it does not supply the program grammar.

## API

```python
from intent_parser import build_prompt, normalize_intent, apply_patch

state = {"items": [{"id": "a", "count": 1}], "archive": []}
prompt = build_prompt(request="Raise a's count to two", document=state)
# Obtain an answer separately; this library never performs inference.
raw = 'update path:["items","a","count"] value:2'
patch = normalize_intent(raw, state)  # custom operations only
updated = apply_patch(state, patch)  # original state remains unchanged
standard = normalize_intent(raw, state, {"json_patch": True})  # RFC 6902 only
```

Independent entry points are `parse_intent`, `parse_intent_with_diagnostics`,
`convert_intent`, `apply_patch`, `build_prompt` and `replay_prepared`. Camel-case
aliases (`parseIntent`, `convertIntent`, etc.) are supplied for cross-port callers.
`build_prompt` also accepts the original `{request, document, idKey}` argument.
Errors derive from `ValueError` (`IntentError`). Parser/patch return values use the
same field names as JavaScript and C#, not renamed Python-only schemas.

Exact enclosing JSON/bare Markdown fences are removed with diagnostics. Quoted operations and quoted transfer paths are accepted when roles are unique.
Generic `replace` and `set` aliases are not supported; the current CSC592 host
explicitly maps its approved `replace` name to Update.

Options are `json_patch` (false), `idKey` (`"id"`), `maxChars` (65,536 UTF-16 code
units), `maxDepth` (64), `maxOperations` (256) and `maxBoundaryAttempts` (4,096).
Collection selection uses typed IDs/primitive values, never numeric positions.
`json_patch` selects output format only; RFC 6902 input is not supported.
The optional `pathSyntax="value_patch"` extension decodes CSC592 typed quoted
path segments and enables that current host's `replace` operation name. Full
schema-aware execution belongs to the host adapter, not generic conversion.
Booleans, numbers and strings are distinct identities. One global `idKey` is
supported; schema-declared per-collection dispatch is not inferred.

Conversion validates operations sequentially against cloned state. Emitted RFC
6902 paths are concrete indices valid only against that exact initial state and
operation order. Copy/move compile to append-copy and optional source removal.
They cannot target the same collection or a source descendant. Root append uses
an explicit empty path; root update/removal remain unsupported. JSON values must
be intact, finite and within the safe integer range. Underflowing nonzero numeric
literals, duplicate JSON keys, invalid Unicode surrogates, cycles and non-JSON
Python objects reject. Failure never mutates the caller's state.

## Offline use and verification

```sh
python -m intent_parser prepared-records.json
python -m intent_parser prepared-records.json --json-patch
python -m evaluation.intent_replay --source results --id-key id
python -m unittest tests.test_intent_parser tests.test_intent_replay -v
python -m unittest discover -s tests -v
```

Prepared records contain `text` (or `output`) and `input`. Optional `expected` and
`reject` fields are compared **only after** normalization; they do not influence
parsing/conversion. Replay retains raw text and SHA-256. These are deterministic
software checks, not live trials or accuracy gains. Saved Workbench captures are
handled by `evaluation.intent_replay`: explicit `intent` uses the generic library,
while active `value_patch` uses the schema-aware host. Legacy `json_patch` and
`semantic` captures are marked unsupported by that host adapter. No captured
response is rewritten and historical scores are never changed.

Shared conformance fixtures in `tests/fixtures/intent_parser` cover permutations,
optional labels, grouping/newlines/whitespace, aliases, typed values, ambiguity,
identity updates/collisions and rejection boundaries. Tests compare IR, custom and
RFC patches where available, final state, input immutability and an independent
RFC interpreter. Prototype provenance: JavaScript prototype baseline with independently verified syntax/safety fixes, using
GrammarForge 2.1.4 upstream commit `4bbdff99f6e7224cfca0788b0d34772a1949230c`.
The native lexer/recursive parser follows `intent.grammar` and `operation.grammar`;
it is not a Python wrapper around the JavaScript runtime.
