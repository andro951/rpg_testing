# Results table evidence tabs — completed October 14, 2026

Paused at Isaac's request at approximately 2:39 PM EDT, then resumed at his request. Implementation and verification are now complete.

## Current request

Clicking a recorded results-table square must open a new tab, never scroll to evidence at the bottom of the table. The new tab must put the saved pass/fail or execution status first, then full sent prompts, full text responses, expected result, and failure reason as consecutive sections. All other information follows below.

## Implementation completed locally

- reporting/report.js: separate evidence tab initialized from #results=case-id; synchronous new-tab opening with noopener; no drilldown section in the matrix. Every call and message displayed in order. Actual adapted request_messages take precedence over the original messages. Full response text and expected oracles displayed without shortening when loaded through the BAT viewer. JSON output/oracles pretty printed. Compact JSON lines in prompts expanded for reading, with an exact-sent-text toggle. Partial responses labeled. Failure reason above detailed evaluator checks. Additional timing, metadata, reasoning, definitions, captured outputs and raw JSON below. Hash navigation, refresh, missing-result and loading-error handling included. Long identifiers wrap on narrow screens.
- reporting/matrix.js: totals/multiple-result squares open a selection list in a separate tab. No bottom evidence block or scrollIntoView calls remain in reporting JavaScript.
- reporting/server.py: /result/ serves a compact evidence-tab document containing summaries, rather than duplicating all embedded raw streams. Complete record fetched from the existing /evidence/case-id endpoint.
- reporting/README.md: updated usage and layout, including the pre-existing offline export limitation. The live BAT viewer loads full evidence for all objective records; direct offline HTML can show complete embedded long-array records but only explicitly labeled previews for other records.
- tests/evidence_browser_smoke.py, tests/report_browser_smoke.py and tests/test_judgements.py updated with coverage for new tabs, exact adapted messages, long responses, JSON formatting, expected state, adjacent section order, immutable saved evidence, unchanged table scroll position, partial output, reload, totals selection navigation, load errors, unknown IDs, narrow screens, and compact server payload/host checks.

## Verification completed

- Latest evidence browser smoke passed using headless installed Edge with synthetic evidence.
- Offline report browser smoke passed.
- Persistent judgement browser smoke passed.
- Timing badge browser smoke passed.
- JavaScript syntax checks passed for report.js and matrix.js.
- New compact-result-document unit test passed individually and in the running full suite.
- Existing reporting/evaluator unit tests passed during the first focused run. That focused run initially failed only the new test due to a missing slash in its test URL; this was corrected and verified.
- Actual saved result visually reviewed on desktop and at 420px width. Section order and full readable prompt confirmed. Screenshots: .local/result-tab-desktop.png, .local/result-tab-result-sections.png, .local/result-tab-narrow.png.
- Regenerated .local/reports/statistics.html successfully: 1545 objective records, 180 embedded long-array records, 2 current cohorts, 0 unreadable files.
- git diff --check passed. No benchmark inference was run; saved benchmark evidence was not modified. No commits or pushes made.

## Full-suite status and remaining work

The final full unittest run was explicitly STOPPED for this pause. It must not be described as a completed or passing full-suite run. Its log is .local/result-tabs-final-tests.log. At pause it had reached test_workbench_reproducibility with passing results through the distinct repetition seed schedule check. A ResourceWarning about an unclosed socket appeared; no unittest failure summary had appeared. An earlier full run was also interrupted to restart against the revised implementation; .local/result-tabs-full-tests.log is not a completed passing run either.

When Isaac asks to resume:

1. Run the required full suite to completion with Git available on PATH:
   $env:PATH = 'D:\Program Files\Git\bin;' + $env:PATH
   .venv-workbench\Scripts\python.exe -m unittest discover -s tests -v
2. Address any failures and recheck affected behavior. All four browser smokes currently pass; repeat only if changes justify it.
3. Check final diff and report actual finished test count/outcome.
4. Tell Isaac to close an old results-viewer console and reopen Open_Results_Table.bat so an older running server picks up the new /result/ route. No existing listener on port 8876 was found on this computer during checks. The regenerated report is ready here. Host E:\Source\Repos\rpg_testing is not available in this environment; do not claim updates deployed there.

## Scope and repository state

Uncommitted changes are the seven files listed above plus this pause note. Preserve them. The separate OPRO/LPIL discussion remains discussion only; no optimizer changes were made for this task. The user has not authorized simplifying the LPIL writer contract. Repository AGENTS.md requires the full unittest suite. No active goal or subagents.


## Resume completion

- Required full suite completed: 630 tests, OK, 628.521 seconds. Log: .local/result-tabs-resumed-tests.log. The interrupted earlier runs remain archived and are not counted as completed checks.
- Final JavaScript syntax checks and git diff --check passed. No implementation changes were needed after the pause.
- All four browser smoke checks and actual-record visual review from before the pause remain applicable. The generated results table is ready at .local/reports/statistics.html.
- User should close an older results-viewer console and run Open_Results_Table.bat again to start the updated server.
- Changes remain local and uncommitted. No benchmark inference, result deletion, commit or push was performed. No work remains for this results-tab request.


## Compatibility follow-up

Isaac reported Not found after clicking a square, then confirmed he had the old viewer open and that the current table works. Independently reproduced the same HTTP 404 using the actual reporting/server.py code from commit 14fb8c4 serving the updated JavaScript. The launcher reuses that older process, whose routes do not include /result/.

New viewers now advertise result_tab_url in their rendered payload. The browser uses the dedicated compact page only when advertised; older viewers open their existing page with the result hash and load complete evidence through the existing endpoint. No process termination, extra port or inference retries are involved. Refresh after updating the code.

Added browser coverage for the legacy route/payload contract, including actual square clicks, full responses, unchanged table position, refresh and totals selection navigation. Also verified the fixed behavior against the actual older server implementation. All four browser smoke checks passed; the required full unit suite passed: 630 tests, OK, 712.691 seconds. Log: .local/result-tabs-compatibility-tests.log. Changes are local and uncommitted; saved benchmark evidence is unchanged.


## Expected-answer display correction

Isaac requested the expected answer itself, such as 62, instead of the internal expected_answers/index JSON wrapper. The result tab now unwraps answer values, expected patches and expected final states while preserving genuine JSON payloads. Multiple expected answers get step labels; a single answer has no extra label. Complete records and parseable limited previews both use this display. Original definitions and raw storage wrappers remain under Additional information. Scoring and raw result files are unchanged.

Browser coverage now clicks through a synthetic index case and checks the expected block equals 62 before and after reload, checks a state oracle equals the unwrapped complete state, verifies raw metadata is still available, and exercises the legacy viewer path. All four browser smoke checks passed. Full unit suite passed: 630 tests, OK, 613.706 seconds; log .local/expected-answer-display-tests.log. Refreshed .local/reports/statistics.html using the existing report data and current scripts. Changes remain local and uncommitted.
