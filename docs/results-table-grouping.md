# Results table grouping

Double-click `Open_Results_Table.bat` to rebuild and open the local results viewer.
Keep its console open while reviewing. The saved HTML is a read-only snapshot;
manual judgements require the loopback viewer, which writes `test_judgements.json`.
The table shows objective tests only; dialogue results remain saved for a separate view.

## Manual judgements

Tables appear in this order: **Rejected**, **Needs review**, **Accepted**. All existing
and new definitions start in Needs review until manually judged. Rejected is collapsed
on opening. Each table has separate totals, its own grouping tree and saved presets,
and a grouping panel that starts collapsed. There are no totals mixing judgements.

Click a variant's label to judge that exact definition across all models/repetitions,
or use **Judge…** on a test-version group for its displayed variants. Record status,
reason, reviewer and an optional note; the journal retains timestamped decision history.
Judgements change neither original scoring nor saved responses.

Rejection permanently blocks that exact execution definition in native and Perchance
run planning, targeted selection, and stale Perchance plans. Accepted/Needs review
remain runnable. A rejected definition cannot be reinstated through the UI/API.
An edited prompt, fixture or oracle creates a new definition in Needs review; changing
names, repetitions, enable flags or timeout does not unblock it. Review and running
use an OS lock, preventing a judgement change while inference is active. Do not edit
the judgement journal manually to bypass the run gate.

## Controls

Select a preset, then use the numbered list to move levels up/down, remove a level,
or add an unused level. The table changes immediately. A matching saved combination
is selected automatically. Otherwise the selector shows **Custom grouping**.

There is no Save/update button. **Save as new…** is enabled only for an ordered
combination that does not already exist. Its dialog requires a unique name.
**Delete…** is enabled only for a saved combination, and opens a confirmation dialog.
Deleting a preset keeps its current grouping as a custom combination.

Presets and the selected combination persist in this browser's local storage.
Regenerating the report preserves them. Each judgement has separate browser storage.
The five initial presets
are ordinary presets: deleting one, or deleting all of them, persists. A different
browser/port may have separate storage. Storage failures are displayed in the panel.

## Initial presets

| Preset | Ordered grouping | What it evaluates |
| --- | --- | --- |
| Individual tests (default) | Ability → Task → Prompt comparison → Test version | Places the three presentations beside each other for each version of one test. |
| Presentation overall | Presentation → Ability → Task → Prompt comparison → Test version | Compares overall observed success for the three presentations. |
| Presentation by ability | Ability → Presentation → Task → Prompt comparison → Test version | Compares presentation success within each broad ability. |
| Presentation by task | Ability → Task → Presentation → Prompt comparison → Test version | Compares presentations within a specific operation across scenarios/versions. |
| Presentation by scenario | Ability → Task → Prompt comparison → Presentation → Test version | Compares wording versions within the same scenario and presentation. |

Ability categories currently distinguish **Array evaluation** and **State updating**.
Task types distinguish locating operations, array edits, time/boolean/nested updates,
inventory arithmetic, and clothing removal. A test can have a single primary category;
totals are not duplicated across overlapping tags. Unselected dimensions are sorted
automatically with natural version ordering, then presentation and repetition.

## Rows and totals

Indented headings identify groups. Every group ends with a subtotal; outer subtotals
have stronger separators. Collapsing a heading hides its descendants while retaining
its subtotal. **Group totals only** hides individual result rows. The grand total is
last and follows the evidence scope and search, including collapsed descendants.

All scored cells display percentages. Colors range from red (0%) through yellow
(50%) to green (100%). Hover for counts/statuses; click to inspect original evidence.
A tiny amber triangle marks saved results whose generation timed out; totals and
aggregate cells also show it when they contain such a result. The tooltip
explains the marker. It retains the timeout indication even if a result is later
classified as a confirmed failure.

Each percentage divides unique primary passes by unique primary passes + failures +
timeouts in that group. It is not an average of child percentages. Missing results,
errors, aborted/skipped/invalid/unscored measurements stay outside that denominator.
Groups without scored observations show a dash; reference-only cells show an arrow.
Perchance aliases never add independent observations. Squares remain 24 px wide;
the page itself scrolls without an inner table scrollbar.

Presentation comparisons describe recorded configurations. Existing full-path patch
companions also differ in their prompt delivery; these totals alone do not isolate
a causal presentation effect. Historical evidence remains distinguishable at the
individual row and can be excluded using **Current definitions**.

## Reporting metadata and identity

`reporting/grouping_metadata.json` assigns the five grouping labels to each current
objective test/variant, including companion presentations and wording revisions.
It contains 159 variants organized into 53 version groups, each with all three
presentations. Each entry includes its reviewed execution-definition digest.

This catalog is deliberately separate from executable `test_specs`: reporting labels
do not enter case IDs, execution fingerprints, run planning, or saved results.
`reporting/grouping.py` additionally guards comparison sets with source and oracle
digests. Unknown or edited definitions cannot silently inherit a reviewed comparison
set; they stay separate until their metadata is reviewed. Embedded prompt fixtures
are protected by the reviewed definition digest too. A timeout-only edit preserves
the comparison and identity. Output protocols such as direct vs analyze and JSON
Patch vs semantic updates retain separate comparison sets.

When adding or editing a test, review its category/task/comparison/version/presentation
labels and update the reviewed digest using `digest(experiment_spec(test, variant))`.
Do not merge different actual input values or required results into a prompt comparison
set. Those can share a task type instead.

## Validation (2026-10-02)

- All 419 runnable unit tests have passing results; four platform-specific tests
  are skipped. The full sweep ran 423 tests. Six process tests initially encountered
  an orphaned mock server from a restarted validation run; after stopping that
  identified fixture, the entire eight-test process module passed on rerun.
- Seven new metadata tests cover every objective variant, presentation alignment,
  wording versions, fixture/oracle/protocol separation, embedded fixture changes,
  unknown definitions, and definition/identity preservation.
- Offline browser smoke covers preset matching, controls, duplicate names, dialogs,
  persistence after regeneration, deleting all presets, malformed storage, ungrouped
  display, collapse behavior, bottom subtotal placement, square cells, gradients,
  unequal child sizes, missing/error statuses, and shared-reference deduplication.
- Simulated workbench browser smoke passed its run/resume and existing control checks.
- Real saved-evidence preview checked all five presets: 309 current objective rows,
  1,236 observations, and 24 x 24 pixel cells. All 1,428 saved result records were
  compared by digest and remain unchanged. The native execution fingerprint is
  unchanged. No real benchmark inference was started.

Timeout-marker follow-up: the full 423-test suite passed (four platform skips),
with report browser and simulated workbench run/resume smoke checks passing.
The real report contains 41 individually marked timeout cells, and its original
429 PASS / 766 FAIL / 41 timeout counts and 24 px cell size are preserved.

Manual-judgement follow-up: the full suite ran 433 tests in 691.706 seconds,
with 429 passing and four platform skips. Ten new tests cover persistence, defaults,
permanent rejection, atomic updates, definition edits, timeout/cosmetic neutrality,
run/review locking, stale provider plans, local API authorization and report refresh.
Offline and persistent-review browser smokes passed. The simulated native workbench
run/resume and Perchance worker/workbench smokes passed. The native browser smoke
now allows 60 seconds for the final full-catalog resume scan, matching its other
Windows scan waits; the original five-second assertion raced that scan.
The real report has all 309 objective rows (159 variants) in Needs review, with
1,236 observations, unchanged scores and 41 amber timeout markers. All 1,428 saved
raw results and the native execution fingerprint remain unchanged. No real inference
or real review decisions were made.

## Readable evidence

Click a score to inspect its scoring, model outputs, expected result and each saved
request/response separately. Prompts are displayed as their decoded multiline text;
complete JSON responses are indented. Partial/invalid JSON stays exactly as saved.
Large nested objects and call metadata can be collapsed, and the full raw record
is retained under a collapsed section. The page grows vertically without an inner
evidence scrollbar. Rendering uses text nodes, so saved model HTML is never executed.

The local viewer fetches the complete original file when the report only embeds a
summary. Loading failures retain a clearly labelled limited preview; offline files
identify their 4,000-character previews. Formatting changes presentation only and
does not modify saved prompts, responses, scores or checksums.

Evidence-view validation: 434 unit tests ran in 589.803 seconds (430 passed, four
platform skips). Readable-evidence, offline-report, persistent-judgement and simulated
workbench run/resume browser smokes passed. The real ticket-array prompt was checked
for decoded multiline text, complete calls and unchanged saved evidence.

## Timing triangle

Timing is independent of pass/fail colour and does not change test IDs, scoring,
resume or execution limits. `reporting/timing_expectations.json` holds fixed, authored
whole-test budgets for each of the 159 objective variants, with a rationale and a
reviewed definition digest. These initial budgets are judgement calls, not measured
performance claims: 15 seconds for single time/boolean edits, 20 for short lookups
and simple array/nested edits, 25 for inventory arithmetic, 30 for large-array patch
work and household additions, and 35 for household removals. A separate analysis
call adds 15 seconds. Presentation and wording companions get equal budgets. Edited
definitions require a reviewed expectation; they cannot inherit stale budgets.

The peer comparison is calculated separately per exact definition/workflow revision,
execution class and simulation status. Each model configuration contributes its
median completed whole-test time, and the peer baseline is the median of those
model medians. Completed passes and failures count. Timeouts, infrastructure errors,
invalid measurements, missing/nonfinite timings and alias references add no samples.
At least three completed model configurations are required; the descriptive slow
threshold is strictly more than twice the peer median. This is a visible policy,
not a statistical significance claim. Filtering/collapsing the display does not
change the baseline, and no judgement table totals mix scores from other tables.

A completed result above either threshold gets a small top-right triangle. Its
colour progresses from green just above the earliest breached threshold to amber
at the current timeout. A completion beyond the current timeout stays amber. An
actual timeout is always harsh red, including a later confirmed-failure judgement,
and regardless of current settings. No threshold exceeded means no triangle.
Missing duration is unknown, never zero. A total shows the worst badge, with unique
observation counts and overlapping reasons in its tooltip.

Hover individual cells for elapsed time, static expectation and rationale, peer
median/model count, peer threshold, current timeout and the saved run deadline.
Rebuild using the BAT after editing expectations or executable timeout settings;
Perchance retains its separate 300-second current timeout. Raw saved evidence is
never rewritten by these display calculations.

Timing validation: the full suite ran 442 tests in 556.592 seconds (438 passed,
four platform skips). Eight timing unit tests cover all objective expectations,
equal model weighting, incomplete/error timings, peer coverage, revision isolation,
fixed expectations, recorded versus current deadlines and immutable scores. Timing,
offline report, judgement, readable-evidence and mock workbench run/resume browser
smokes passed. The real report retains 309 rows, 1,236 observations and the original
429 PASS / 766 FAIL / 41 timeout scores. All 41 timeout corners are harsh red;
17 completed observations exceed their static expectation. Peer badges are separate.
The saved raw results and native execution fingerprint remain unchanged.
