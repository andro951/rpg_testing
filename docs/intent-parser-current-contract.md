# Current-contract intent parser checkpoint

This branch collects the current cloud JavaScript implementation, native C# port,
and Python CSC592 integration after the legacy-influenced rollback. It is an
opt-in offline implementation, not a replacement for approved benchmark prompts,
scoring, or the desktop's separate normalization experiments.

## Locations

- `intent-parser-js/`: readable JavaScript source, GrammarForge runtime, tests.
- `intent-parser-csharp/`: native .NET 8 source and shared conformance fixtures.
- `intent_parser/`: native Python library.
- `evaluation/value_intent.py`: explicitly selected current `value_patch` host.
- `evaluation/intent_replay.py`: offline replay entry point.

The generic language supports add/append/insert, update, remove/delete, copy and
move. Generic `replace` and `set` aliases and RFC input-dialect bridges are absent.
The current CSC592 host explicitly supports its own `replace` name. RFC 6902 is
an optional output format only. Historical archives have not been modified.

## Checks

From the repository root:

```sh
python -m unittest discover -s tests -v
(cd intent-parser-js && npm test)
(cd intent-parser-csharp && dotnet build && dotnet run --no-build -- self-test)
(cd intent-parser-csharp && PYTHON_REFERENCE=.. python cross-language-test.py)
(cd intent-parser-csharp && JS_REFERENCE=../intent-parser-js node differential.cjs)
```

The last two commands require a built C# project and `dotnet` on PATH. The
`DOTNET` environment variable can select a specific .NET executable. These are
deterministic software checks, not new model inference or accuracy measurements.

This checkpoint preserves the previously published JavaScript branch history and
the corrected Python integration. It does not include unrelated uncommitted
desktop changes; use a separate worktree when the existing desktop checkout has
work in progress.
