# Grammar-first revision, November 10

This section supersedes the historical status below. `intent.grammar` now drives the complete program: operation signatures, optional labels and field order, recursive operation groups, typed paths, and recursive JSON values. JavaScript uses GrammarForge; C# and Python use the specification exported from its parsed grammar. See `GRAMMAR-DESIGN.md` for every retained procedural check and the build workflow.

The previous generic structural grammar remains only as the conversion adapter `tokens.grammar`. The compiler now rejects incomplete operations and extra fields before IR conversion. Grammar changes are included in the live evaluator fingerprint and require a separately prepared configuration; frozen experiments and old results are not changed.

The revision also adds portable grammar validation and fixes the new C# evaluator's independently reproduced long-input stack overflow. Its evaluator and AST traversal now use explicit stacks. No changes were made to the upstream GrammarForge source, model prompts, model inference settings, or saved research results.

## Historical implementation checkpoints

# JavaScript implementation status

## Implemented and exercised

- Reusable prompt builder with five operation explanations and no reference answers/example patches.
- Two actual GrammarForge grammars: structural groups/tokens, then operation components/fields/paths/recursive values.
- Public AST-derived intent IR independent of normalization.
- Optional labels and arbitrary component ordering; candidate roles resolved only when unique in the current document.
- Conservative outer-wrapper recovery, with diagnostics and no repair of inner JSON values.
- Unique grammatical partitioning of newline-separated operations; horizontal whitespace cannot swallow a newline.
- Custom patch conversion, atomic clone-based updater, exclusive optional RFC6902 output.
- Typed identity and primitive-value selection, pointer escaping, numeric-precision checks, duplicate rejection and safe identity edits.
- Offline prepared-output replay preserving raw text and hashes; expected answers isolated from normalization.
- Resource bounds; JSON-only data validation without getter execution or discarded properties; reusable entry point; no dependencies or installation required beyond Node.

## Verification scope

`node run-all.cjs` executes 5,602 passing deterministic checks, including replay checks over 2,651 prepared fixtures. These are repeated software assertions and format variations, not 5,602 independent research observations. No live inference, benchmark accuracy claim, or full existing-repository integration test is implied.

## Deliberate boundaries

- Alias expansion needs explicit review; see ALIASES.md. Ambiguous words are not silently accepted.
- Same-collection transfers and positional insertion are outside the existing research contract.
- Paths use one configured identity field (`idKey`, default `id`). A per-collection schema adapter is not included. Host applications still enforce their full domain schema and judge whether the requested change was satisfied.
- Root append works; root replacement/removal is not supported.
- No C# or Python port until JavaScript behavior is accepted.
- Existing research scripts, immutable outputs, approved prompts and benchmark scores remain untouched.

## Publication distinction

The first public checkpoint is commit 975f8a17f647937432f636c947994c10155c6199 on `pip/intent-parser-js-prototype`. Later changes are saved locally; a subsequent publication attempt was rejected by the approval reviewer. Do not confuse the public checkpoint with the newest local implementation.
