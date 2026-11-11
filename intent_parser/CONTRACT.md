# Shared JavaScript, C# and Python behavior

This contract separates parsing, semantic normalization, patch application and evaluation. Expected/reference answers must never enter the first three stages.

## Intent semantics and output format

The generic intent language has five operations. Append/insert mean append to
an existing collection. Literal add carries `semantic: "literal_add"` in the
parsed IR: conversion appends when the target is a collection and updates when
it is an existing object field. It cannot replace a whole collection element
or create a field. Update/set replace an existing target and never create a
missing field. Remove/delete removes the selected value. Copy/move append a
complete independent source copy to a different collection; move then removes the
original. Generic `replace` is not supported; `set` is an Update alias.

`json_patch: false` returns only custom patches. `json_patch: true` returns only
standard RFC 6902 output representing the intent correctly, with state-dependent
indices and sequential order requirements. This selects output format only; it
does not add support for RFC 6902 input. Parsing, state-aware conversion and patch
application remain independent stages.

The explicitly selected CSC592 current host (`pathSyntax: "value_patch"`) maps
its approved operation name `replace` to Update and decodes typed quoted path
segments. This mapping is scoped to that current format, never enabled in the
generic intent parser. The Python host also enforces per-collection schema IDs
and operation scopes through CSC592's existing schema-aware lowerer.

## Shared structured output syntax

The same grammar recognizes JSON operation objects, bracketed path-list lines,
literal/end-marked text lines, typed value lines and historical two-line JSON
values. `none` and an empty list express no change. Transfers can use explicit
`from`/`to`, a colon header followed by `to:`, or an arrow between paths.

`output_format` chooses only the codec of a grammar-declared text value:
`typed_lines` removes exactly one separator space and preserves the remainder;
`literal_line` decodes its documented escapes; `end_marked_line` removes the
required final pipe and decodes its documented escapes. Other values use JSON
or typed grammar productions, independent of format metadata. Text punctuation,
unmatched brackets and quotes are data; leading/trailing spaces are preserved.

`change` is parsed as Update with `semantic: "numeric_delta"`, and removals in
`typed_lines` carry `semantic: "typed_remove"`. These require host-specific
state-aware lowering; standalone conversion rejects them rather than silently
changing their meaning. Only `literal_add` is lowered by the native converter.
Concrete patches never retain semantic annotations.

## Generic syntax recovery

A single whole-response triple-backtick fence with `json` or no language label can be removed. Text before/after a fence is not discarded. The diagnostic is `MARKDOWN_FENCE_REMOVED` with detail `single enclosing JSON code fence`.

A bare operation word takes precedence over quoted words. When there is no bare operation word, one unique quoted operation alias can supply the operation. Multiple plausible quoted aliases reject.

Unlabeled transfer paths can be explicitly grouped or quoted. A source/destination interpretation must be uniquely determined by the current document. Two collections without direction remain ambiguous.

The whole-token-stream interpretation and grouped-operation interpretation are both checked. An object containing an `op` key may be a literal value, including when it precedes the append operation. One complete interpretation is required; two distinct successful interpretations reject.

Newlines are candidate boundaries, not unconditional terminators. Separator-only runs are compacted without changing quoted values. Empty lines cannot trigger unbounded recursive processing.

## Lossless JSON and identities

Strings and object keys must have valid Unicode scalar sequences: reject unpaired UTF-16 surrogates, retain valid surrogate pairs. Reject nonfinite numbers, unsafe integer values and nonzero numeric tokens that underflow to zero. A lexical zero with an extreme exponent remains zero.

Collection identities share one typed namespace: a primitive value and an object's configured ID with the same JSON type/value collide. Check this for append, whole-element replacement, identity-field edits, copy and move. Numeric 1 and string "1" remain distinct. Supplied object identities must be scalar JSON values; object/array-valued IDs reject. Objects lacking an ID are not automatically schema-invalid, but cannot be selected by an absent identity; full schema enforcement remains the host's responsibility.

## Replay integrity

Offline replay preserves each raw response and its hash. Expected states are
compared only after parsing, conversion and application; they never influence
those stages. No legacy input importer, automatic source-dialect inference or
per-record legacy-dialect override is present. The schema-aware current host is
selected explicitly by captured current-format metadata, not expected answers.
