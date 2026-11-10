# Port provenance and verification

Baseline JavaScript checkout: `69a17faa2e4b0d14d69178898ffa89af2398e667`. Independent safety and grammar revisions were synchronized from the working contract after that baseline. Legacy-case-driven replace/set aliases and the RFC input-dialect bridge have been removed. Explicit current-contract value_patch replace remains supported.

The original JavaScript implementation uses GrammarForge 2.1.4, upstream commit `4bbdff99f6e7224cfca0788b0d34772a1949230c`. This C# port is a native interpreter of the generated ordered-expression specification, not a port or redistribution of the GrammarForge engine. Program structure, recursive operation groups, complete signatures, and component ranges are grammar-driven.

Verification reports are regenerated for the rollback from only the current contract and independently derived synthetic fixtures. Previous pre-rollback counts and fixture hashes do not describe this version. No archived model responses are used for the rollback tests.

Verified rollback with .NET SDK 8.0.415:

- Clean build with warnings treated as errors.
- 219 native self-tests (including the grammar-first revision).
- 2,757 synthetic fixture records, including 44 independently derived current-revision cases and 9 explicit current-contract regressions.
- 8,385 direct native Python/C# conformance requests: zero differences.
- 855 current JavaScript/C# differential probes: zero differences.

These are offline software checks, not live-model trials or accuracy measurements. Generic intent aliases remain add/append/insert, update, remove/delete, copy and move. Current host replace is supported only with explicit pathSyntax=value_patch. RFC6902 is output-only; no input dialect adapter or automatic guard remains.

Fixture and grammar SHA-256:

- `fixtures/current-contract-regressions.json`: `0632d12c06dffa044ef34b366590820f7626180bf1899a2374d8f42eb109b44d`
- `fixtures/current-revision-fixtures.json`: `969f2053c601dbe9ece1fb38506a6a3a99c266f75816eb55752dbb633c3eec10`
- `fixtures/optional-parity-fixtures.json`: `27e63532bb6da740faed2eea13b5a3118a69256178233898b58be76a64fd061f`
- `fixtures/parity-fixtures.json`: `b9b2c18ba0c2ba7de009a80243033cf96fe2dbe5ee756271e17c1d27a9967add`
- `fixtures/shared-fixtures.json`: `95bdb4897cefeee7e267a38f1a916558fa5d6bf9d57b3dfb41fd5aa343c2a418`
- `robustness-parity-fixtures.json`: `dccabb83781a0b92b6e449322f694fb12b6b7ed5e7a4bfd05564647265eadde0`
- `intent.grammar`: `8756049ee49517c3f0f1242b2a2fe1e863aad708ea1532de4c7169ccf5ec01ef`
- `operation.grammar`: `af5b3c422fff5b98700a54bee69b0cfcf803f3569f6b46ced230ba3433ce8e0a`

Grammar-first verification: clean .NET build, all 219 self-tests and 2,757 existing fixture records pass; all 855 direct JavaScript/C# probes agree. These remain synthetic offline checks.

Resource-bound regressions exercise 4,000-operation normal limit errors, a valid 256-operation program, 10,000 JSON array elements, and an explicit 4,000-operation override. Grammar descent, continuations, and program traversal use explicit stacks rather than the CLR call stack.
