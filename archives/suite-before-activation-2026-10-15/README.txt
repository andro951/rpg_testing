ARCHIVE BEFORE DATABASE-SUITE ACTIVATION — OCTOBER 15, 2026

Archived at Isaac's explicit request while enabling the finalized database suite.
This folder is outside normal Workbench test, result and optimization discovery.
Nothing here should be restored to active folders during ordinary startup.

results/ — 1,740 saved model observations, with their original files and bytes.
optimization_results/ — two prior optimization sessions and all their evidence.
draft-suite/ — 20 superseded draft definitions, 59 prompt-only exports, compiled
  prompts, original input fixtures, templates, builder and review records.
manifest.json — original paths, archive paths, byte counts and SHA-256 hashes.
  Generated Python bytecode/cache files are not part of the source manifest.

The original 61 research definitions, evaluator samples, grouping metadata,
optimization registration and judgement records were already preserved in:
  ../test-suite-2026-10-14/

Current active material stays at the repository root:
  test_builder/ — reusable templates, input data and exact-prompt approvals.
  test_specs/ — only the 14 approved database tests (41 prompt variations).
  prompt-review/ — the exact 41 model prompts, one text file per prompt.
  results/ and optimization_results/ — new runs and sessions only.

No inference was performed by this archive operation. No old observation was
deleted, rescored, changed into a new result, or used to satisfy a new test.

For a separate historical report, run from the repository root:
  python -m reporting.report --source archives/suite-before-activation-2026-10-15/results --specs archives/test-suite-2026-10-14/test_specs --output .local/reports/archived-statistics.html
This writes an offline historical view and does not restore active results.
