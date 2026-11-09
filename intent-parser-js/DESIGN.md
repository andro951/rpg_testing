# CSC592 intent parser: implementation contract
Source: Isaac's November 9 2026 voice discussion. Implement directly as Pip, not a Codex task.

## Architecture
Use Isaac's GrammarForge grammar/parser initially; inspect grammar grammar, ZON grammar, documentation and examples before claiming compatibility. Expose independent parse-to-IR, convert-to-custom-patch, apply-custom-patch functions. Optional json_patch=false flag switches converter output to standard RFC6902 instead of custom patch, never both. RFC indices require the matching starting document and sequential operation application. Arrays are unordered; user-facing addressing is identity based, not arbitrary insertion indices.

## Semantics
Top-level zero or more operations. Supported operations: update existing field with value; append value to collection; remove; copy existing source value and append to destination collection; move as append-copy then remove original. Preserve value types and source data. Component order arbitrary; labels reliable, ordering not. Copy/move labels from/source and to/destination; one unique directional label can determine remaining role. Unlabeled paths require uniquely determined roles; reject array-to-array without direction. Never guess intent using expected answers.

## Syntax
Generic path-token parsing for slash, dot, token arrays, separators; quote/escape semantics preserved. Explicit label delimiters distinct from path separators. Parentheses/braces/brackets may group intent components. Missing closer may discard unmatched grouping role only when unique interpretation survives, never discard contents or modify actual JSON values. Newline/whitespace rules and ambiguous aliases require explicit review. Add/update require distinct value component. Root-array path versus literal array ambiguity must fail closed.

## Vocabulary
Clear initial aliases: add/append; remove/delete; update; copy; move. Insert means append only without positional/index/before/after intent. Review synonyms from programming/patch conventions; do not silently enable ambiguous aliases (set, push, pop, clear, merge, replace, etc.). Label path1/path2 alone does not establish source/destination. Proposed value/array/collection/list roles require unambiguous typed interpretation. Semicolon and plain space as label delimiters unresolved.

## Acceptance and research integrity
Normalize mechanically recoverable syntax, not guessed values. Preserve original raw outputs and old scores; replay validator on saved outputs, no model rerun solely for parser changes. Test correct parses plus ambiguous and adversarial near misses. No benchmark-specific exceptions or oracle access. Keep incremental artifacts and actual command/test receipts here.

## Permissions and status
Desktop cutoff November 9 2026 15:00 UTC; cloud work may continue. No claim of existing-parser execution until actual source obtained and executed. Current stage: source discovery and contract captured; not yet implemented.

## Latest implementation-language direction
Isaac: all components JavaScript first so he can read and work on them, including grammar, parser, prompt builder, conversion and custom updater. Once the JS implementation works, personally port to Python using identical fixtures and behavior; Python is for broader AI audience, not his preferred development language. Do not substitute a Python-first implementation. Current implementation is JavaScript.

## Superseding language and test sequence
Isaac's latest direction: JavaScript first until fully happy; C# second; Python third. Extensive JS unit and full end-to-end prompt-builder, parse, normalize, apply, output tests including edge/error cases. Only after JS acceptance port shared fixtures/test package and run equivalent comprehensive suites in C#, then Python. Do not start ports prematurely.

## Verified existing repository constraints (not new research claims)
Read andro951/rpg_testing/AGENTS.md at default branch 52800f59 before integration: primitive collection members use their unique typed JSON value, object members use schema-declared IDs; no positional indices. Copy/move target a different collection, never the source element's descendants. Prompt wording uses element consistently. Existing tests grade equivalent patches by final state, not textual equality. Preserve immutable outputs, approvals and benchmark settings. Prototype now preserves scalar JSON identity types and implements primitive selection; schema-specific per-collection ID configuration remains to integrate. The generic default idKey is not a claim of full schema support.

## Current limits requiring further work, not silently decided user rules
Unlabeled operation boundaries without group/semicolon remain conservative. Alias expansion and ambiguous delimiter decisions remain pending. Root append is supported via explicit empty path; root replacement/removal and identity-field edits are conservatively rejected, not asserted to be forbidden by Isaac. Structural grammar currently recognizes groups/tokens; separate IR extraction resolves labels and operations. Full grammar-level operation productions remain an architectural refinement before calling the grammar complete. Node tests simulate model responses and are not live model trials.

## Later implementation checkpoint (supersedes earlier architecture limitation)
A second actual GrammarForge grammar, operation.grammar, now parses operation components, labeled fields, typed paths, and recursive JSON literals before IR conversion. Optional unlabeled path/value components are represented as candidate roles; normalization accepts only one state-valid interpretation, rejecting two plausible meanings. Quoted operation words remain literal values. 57 focused tests and 2,253 generated end-to-end checks pass; no live model trial. Public publication was attempted on an isolated branch but auto-review rejected content upload pending explicit repository/payload approval; no source payload was uploaded. Local work is preserved.

## Resumption and final JavaScript verification
A publication orchestration call stalled for 11,998 seconds before cancellation; this was an actual interruption, not progress. Resumed November 9 at 18:29 UTC. At resumption the old branch still pointed to its base. A bounded/nonblocking authorized push then succeeded and was verified at remote commit 975f8a17f647937432f636c947994c10155c6199. A later incremental public tree upload was rejected again by auto-review; no bypass attempted and root notified immediately. Independent cloud work continued.

JavaScript now includes reusable public API, prompt builder with all five operation explanations and no answer/examples, actual two-stage GrammarForge AST processing, IR, custom converter/updater, optional RFC6902 output, and offline prepared-response replay. Literal data and identity safety covered. Full deterministic suite: 5,602 checks, including repeat replay over 2,651 prepared fixtures. No live inference or accuracy claims. Alias expansion stays an explicit review decision; same-collection transfers/positional insertion remain out of scope. Root replacement/removal and per-collection schema adapters are not implemented; documented rather than silently assumed. No C# or Python work started.
