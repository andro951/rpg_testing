# Offline statistics report

From the repository root, using the same Python environment as the Workbench:

```powershell
python -m reporting.report
python -m reporting.report --source evidence.zip --output .local/reports/another-run.html
```

Open the resulting HTML in a current Edge, Chrome or Firefox browser. It opens on the **Objective results matrix**, covering tests with fixed expected answers or expected final states with models as columns and variants/repetitions as rows. Dialogue and other open-ended generation are excluded from the table and all its totals; their saved evidence remains intact for a separate view later. Result cells are 24-pixel squares: green P for pass, red F/T for fail/timeout, amber for other statuses, gray for not recorded, and blue arrows for provider references. Short model nicknames sit above the squares and test labels on the left. Full filenames, execution details and configuration identities are available on hover; duplicate nicknames get numbered suffixes. Hover for full status/counts and click to inspect evidence. Test subtotal rows, model total rows and a grand total use the original saved exact-match scores. Scored subtotal and total cells use a continuous pass-rate gradient from red at 0%, through yellow at 50%, to green at 100%; timeouts count as unsuccessful, while missing and unscored observations are excluded from that rate and stay separately labeled.

Use **Rows → Tests with totals** for a shorter overview, **Evidence scope** to separate current and historical definitions, and **Find test** to filter rows. Totals follow the visible rows and count unique primary observations; Perchance reference cells do not become extra trials. Differing saved runs in the same cell remain accessible as MULTIPLE rather than choosing the best/latest answer. All-results percentages are descriptive across recorded conditions, not a controlled comparative ranking. Missing, skipped, invalid and infrastructure outcomes remain separately labeled.

The file embeds JavaScript, compact all-suite summaries, and the original records used by the existing long-array views. It needs no server, CDN, chart library, network or inference. For directory input, cell inspection links to the complete original JSON on this computer; keep the results directory available. These local links will not follow a report copied to another computer. ZIP input identifies the archive/member containing complete evidence. Output/oracle previews outside the long-array views are explicitly truncated to 4,000 characters; saved evidence is never trimmed. This avoids embedding hundreds of megabytes of raw streams solely to display a compact matrix. Generating a report does not publish it.

`--source` accepts a results directory (`model-id/case-id.json`) or a Workbench evidence ZIP. ZIP members are validated without extraction; checksums and path identities are checked. Invalid evidence is listed, not silently scored. Conflicting records sharing a case ID stop generation. Output must be outside the input evidence and test-spec directories. `--specs` defaults to current `test_specs`; the current workflow fingerprint is used to separate historical evidence.

The all-suite matrix is built in `matrix.py`; it includes active expected rows even when entire repetitions are unrecorded, and historical rows for saved definitions/workflows. Model artifacts, execution classes and simulation status have separate columns. Different configurations within a column remain in their original evidence. Raw case IDs are deduplicated before counting. The existing chart views retain the versioned long-array mapping in `report.py` for patch tests 004–009 and locating tests 010–015. Full-path companions are explicit mappings; the stored presentation flag alone cannot distinguish these.

Each current cohort requires exact current test/variant definitions, workflow fingerprint, hardware/software target, policy, allocated context, execution class and simulation status. Only volatile logger lines preceding explicit backend version/build lines are removed from the derived cohort key. Original target text stays intact. Model artifact/native-context/placement configurations have separate identities. The report cannot discover a model that has never produced any mapped evidence. A missing repetition is represented when another current case has that repetition; entirely unobserved repetitions/models are not inferred from machine-local catalogs.

Representation accuracy uses only operation/repetition pairs present exactly once in all three representations and every model configuration in that cohort. Timeouts count as unsuccessful. Infrastructure failures, invalid measurements, unscored outputs, missing and ambiguous cells stay visible in coverage and are excluded from matched scoring. An incomplete patch matrix may therefore have no comparative rate even though its individual results remain inspectable. No selective latest-result picking is performed.

Locating and patch construction have separate views. Strict accuracy preserves original `score.exact_match`. The separately labeled index diagnostic v1 compares ordered integer tokens; a sentence identifying the expected index can be distinguished from a strict-format success. This is a conservative lexical diagnostic, not a semantic grader: negatives, decimals, additional/conflicting numbers and unrecognized answers are marked wrong or ambiguous. It never changes stored scores.

The full-path patch companions use a different prompt style from the raw/indexed patches. Their recorded configurations can be compared descriptively; the report does not claim an isolated representation effect. Historical definitions/workflows remain inspectable in their own view and original summaries, never pooled into current charts.

Latency shows observed current completed-response distributions, per-case accuracy versus latency, median/counts and separate timeout counts. It is descriptive and can have different task coverage across configurations. Timeouts have no completed-response latency. Missing timing is unavailable, not zero. Each point/button opens the exact original record with messages, response/partial stream, expected answer/state, score, load/settings, call timing/usage and checksum. Those include prompt-processing/generation measurements only when the backend recorded them.

Tests:

```powershell
python -m unittest tests.test_reporting -v
python -m unittest discover -s tests -v
python scripts/audit_case_preservation.py
python -m pip install playwright
python -m playwright install chromium
python -m tests.report_browser_smoke
```

On a Windows host with Edge already installed, set `REPORT_BROWSER_EXECUTABLE` to its executable instead of downloading Chromium. The smoke test uses deterministic synthetic evidence, exercises all views, missing/timeout distinctions and original-record drilldown, checks narrow-screen rendering, and asserts no browser errors or HTTP requests. It is not real model inference. CI runs it alongside the existing Workbench checks.


Timeout is an execution watchdog, excluded from case identity, experiment comparison and matrix row grouping. Its actual value is preserved in raw run metadata. Changing it does not create another row, add references or reopen a completed result, including a timed-out completion. The approved clean reset deleted all saved results and removed the deadline-specific comparison catalog before adopting this policy. Fresh runs populate the ordinary active-suite rows.