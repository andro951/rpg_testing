# Offline separator validation, version 2

This is a separately versioned interpretation of existing saved `dot_patch_v1`
responses. It does not change model prompts, generation parsing, generation case
IDs, original scores, approval catalogs or archived experiments. No inference is
required. Use:

    python -m evaluation --source PATH_TO_RESULTS --output SEPARATE_OUTPUT --validator dot-separators-v2

Outputs live under a validator-version/source-fingerprint directory. Assessments
carry the original score, source checksum, captured definition hash, original
generation case/workflow identity and a distinct validation ID. Dataset summaries
are named `summary-<dataset-digest>.json`. Conflicting existing artifacts are
refused. Repeating the same replay preserves identical artifacts. Captured
definitions supply the contract, including unregistered research definitions;
current catalog entries supply metadata only. Other representations are recorded
as not applicable. Source records must pass the existing checksum reader.

The default evaluator and generation evaluator retain their original behavior.
The expansion applies only to `path` and `from`: literal characters may select
an existing field or ID when exactly one complete location matches the current
state. Unescaped dots may be structural or literal. All complete interpretations
are considered; multiple locations reject, including a literal dotted ID versus
a nested structural path. The resolver never uses the requested answer or the
operation's proposed value to choose a location.

Explicit percent-encoded and JSON-quoted components keep their original
boundaries. `%HH` still decodes UTF-8; `%_` still means an empty component.
Malformed percent sequences and invalid UTF-8 reject. An ID literally containing
`%` must use `%25` or a quoted component; a literal quote that forms a valid
quoted component retains that syntax rather than being guessed as raw text.
An unresolved path rejects. Values are never repaired or normalized.

Coverage is derived from the actual grammar: dot, percent, underscore, JSON
quote/backslash, slash, colon, comma, braces, brackets and JSON whitespace.
Tests exercise encoded and quoted spellings for every character, plus printable
ASCII/Unicode literal spellings where they do not conflict with explicit escape
syntax, nested collections, primitive IDs and schema fields. Typed-ID collisions
remain rejected. Existing operation roles, schema validation, sequential state
updates, exact operation sequence and redundant-write grading remain unchanged.

Fresh interpretation review covered resolver branching, explicit boundaries,
malformed escapes, operation lowering and evidence lineage. The 13 current
fixed-schema fixture recipes and their rendered dot instruction block were
checked against the update/add/remove/no-change contract. Earlier automated
reference checks covered 100 rendered cases (62 existing value-path and 38 dot
presentations), with schema/reference checks passing. Historical Move/Copy
fixtures remain diagnostics and do not expand current research scope.

This review authorizes no new prompt. No Isaac approval record was created or
rebound, no old catalog approval was copied and no source-compatibility exemption
was added. Prompt-output lineage and validation lineage are separate. Existing
approvals retain only their original meaning.

Residual limits: ambiguous raw paths require an explicit spelling; malformed JSON
and wrong/extra/missing operations still fail. Resolver search follows the actual
state/schema, so very large adversarial states may cost more than strict token
splitting. This validator is intended for captured local research evidence, not
an unbounded public-input service. Its fingerprint records source dependencies,
Python and jsonschema versions for reproducibility.
