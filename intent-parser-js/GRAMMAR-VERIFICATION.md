# Grammar-first verification, November 10, 2026

This revision was developed in an isolated branch from `ec3ca3d88ac186c0330a3600a545230b81017956`. It does not change saved research observations, approved prompts, model settings, archived test suites, or the independently frozen desktop experiment.

## Executed checks

- `node intent-parser-js/build-grammar-spec.cjs --check`: all generated specifications and grammar copies match their source.
- `node intent-parser-js/run-all.cjs`: 5,701 passing deterministic assertions, including 52 new grammar-focused checks. These include direct GrammarForge acceptance/rejection, recursive operation groups and JSON values, ordering, multiline handling, limits, conversion, application and prepared-fixture replay.
- `python -m unittest discover -s tests -v`: all 759 repository tests passed in 250.512 seconds on the final source.
- The focused Python conformance run passed 53 tests, including the shared 2,678-record corpus.
- `intent-parser-csharp/run-tests.sh`: the .NET 8 build passed with no warnings; 219 self-tests and 2,757 fixture checks passed. The detailed output is in `intent-parser-csharp/test-results.txt`.
- `JS_REFERENCE=../intent-parser-js node differential.cjs` from `intent-parser-csharp` (with the local .NET SDK selected): 855 cross-language probes passed, with 372 accepted inputs and zero mismatches.
- The mocked Controller/Session persistence-and-resume integration test was also run twice independently and passed both times. The generated grammar is now part of the evaluator fingerprint, so changed grammar cannot reuse a stale prepared evaluator identity.
- Additional review exercised randomized JavaScript/Python agreement and C#/Python Unicode behavior. A C# stack overflow on large operation lists found during review was fixed with an explicit interpreter stack; 3,000- and 4,000-operation probes now fail safely at the default count limit and can succeed when the caller explicitly raises that limit.
- `git diff --check`: clean.

Counts include repeated fixture variants and assertions. They are software verification, not model trials, accuracy estimates, independent research observations, or proof that arbitrary input cannot expose another bug.

## Existing audit caveat

`python scripts/audit_case_preservation.py` still reports:

```
AUDIT FAILED: Fingerprint-bearing file changed: domain.py
```

This revision does not change `workbench/domain.py`. Its bytes match the starting commit exactly, with SHA-256 `7e824ff9e8a050ca7d3c3a8722f46af093ba88807da4f96e19fc6c4aaa30f6ae`. The existing audit baseline was not rewritten to hide that unrelated failure. Therefore this is not a claim that every repository/CI check is green.

No UI was changed and no live-model inference was performed for this revision. See `GRAMMAR-DESIGN.md` for the exact procedural exceptions and remaining semantic validation.
