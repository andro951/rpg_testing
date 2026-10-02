"use strict";

//#region Objective results matrix
const ResultsMatrix = {
    Empty: { ids: [], primary_ids: [], reference_ids: [] },
    Palette: { pass: "hsl(120, 75%, 80%)", fail: "hsl(0, 75%, 80%)", timeout: "hsl(0, 75%, 80%)", reference: "#dbeafe", multiple: "#ede9fe", missing: "#f1f5f9", other: "#fef3c7" },
    Sections: {},
    Statuses: [["rejected", "Rejected"], ["needs_review", "Needs review"], ["accepted", "Accepted"]],
    Compare: (left, right) => left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }),
    RateColor: rate => `hsl(${Math.max(0, Math.min(1, rate)) * 120}, 75%, 80%)`,
    Initialize: parent => {
        ResultsMatrix.Scope = StatisticsReport.Select(parent, "Evidence scope", [["all", "All saved results"], ["current", "Current definitions"], ["historical", "Historical definitions"]]);
        ResultsMatrix.Rows = StatisticsReport.Select(parent, "Rows", [["cases", "Every variant / repetition"], ["tests", "Group totals only"]]);
        const label = StatisticsReport.Element("label", parent, "Find test ");
        ResultsMatrix.Search = StatisticsReport.Element("input", label);
        ResultsMatrix.Search.type = "search";
        ResultsMatrix.Search.setAttribute("aria-label", "Find test");
        ResultsMatrix.Search.addEventListener("input", StatisticsReport.Render);
        ResultsMatrix.Controls = [ResultsMatrix.Scope.parentElement, ResultsMatrix.Rows.parentElement, label];
        for (const [status] of ResultsMatrix.Statuses) {
            ResultsMatrix.Sections[status] = { groupings: MatrixGroupings.Create(status), collapsed: new Set(), open: status !== "rejected", groupingOpen: false };
        }
    },
    Counts: cells => {
        const records = StatisticsReport.Data.matrix.records;
        const ids = new Set(cells.flatMap(cell => cell.primary_ids));
        const counts = { pass: 0, fail: 0, timeout: 0, error: 0, aborted: 0, skipped: 0, invalid: 0, unscored: 0,
            observations: ids.size, references: cells.reduce((count, cell) => count + cell.reference_ids.length, 0), not_run: cells.filter(cell => !cell.ids.length).length };
        for (const id of ids) {
            const state = records[id].outcome;
            counts[state in counts ? state : "unscored"]++;
        }

        return counts;
    },
    CountsText: counts => {
        const scored = counts.pass + counts.fail + counts.timeout;
        const extras = [["timeout", "timeout"], ["error", "error"], ["aborted", "aborted"], ["skipped", "skipped"], ["invalid", "invalid"], ["unscored", "unscored"], ["not_run", "not recorded"]];
        const text = `${counts.pass} PASS / ${counts.fail} FAIL${scored ? ` · ${(counts.pass / scored * 100).toFixed(1)}%` : " · unscored"}`;
        return text + extras.filter(([key]) => counts[key]).map(([key, label]) => `\n${counts[key]} ${label}`).join("");
    },
    Inspect: (ids, heading) => {
        const parent = StatisticsReport.Details;
        parent.replaceChildren();
        StatisticsReport.Element("h2", parent, heading);
        StatisticsReport.Element("p", parent, `${ids.length} unique saved result(s). Open a result for its score and original evidence. Only independently executed observations contribute to totals.`);
        for (const id of ids) {
            const summary = StatisticsReport.Data.matrix.records[id];
            const record = summary.metadata;
            StatisticsReport.EvidenceButton(parent, id, `${summary.outcome.toUpperCase()} · ${record.test_id} / ${record.variant_id} / repetition ${(record.repetition || 0) + 1} · ${id.slice(0, 8)}`);
        }

        parent.scrollIntoView({ behavior: "smooth" });
    },
    //#region Timing badge
    TimingMarker: (cell, ids) => {
        const summaries = ids.map(id => StatisticsReport.Data.matrix.records[id]);
        const measurements = summaries.map(record => {
            const timing = record.timing || {};
            const timedOut = timing.timed_out || record.metadata?.timed_out || record.outcome === "timeout";
            const elapsed = timing.elapsed_seconds;
            const completed = ["pass", "fail"].includes(record.outcome) && !timedOut;
            const expected = completed && Number.isFinite(elapsed) && Number.isFinite(timing.expected_seconds) && elapsed > timing.expected_seconds;
            const relative = completed && Number.isFinite(elapsed) && Number.isFinite(timing.relative_threshold_seconds) && elapsed > timing.relative_threshold_seconds;
            const starts = [expected ? timing.expected_seconds : null, relative ? timing.relative_threshold_seconds : null].filter(value => value !== null);
            const start = Math.min(...starts);
            const deadline = timing.current_timeout_seconds;
            const progress = expected || relative ? Number.isFinite(deadline) && deadline > start ? Math.max(0, Math.min(1, (elapsed - start) / (deadline - start))) : 1 : 0;
            return { timing, timedOut, expected, relative, flagged: Boolean(timedOut || expected || relative), progress };
        });
        const seconds = value => Number.isFinite(value) ? `${value.toFixed(1)}s` : "unknown";
        if (measurements.length === 1) {
            const item = measurements[0];
            const timing = item.timing;
            cell.title += `\nElapsed: ${seconds(timing.elapsed_seconds)}\nStatic expected time: ${seconds(timing.expected_seconds)}\nPeer median: ${seconds(timing.peer_median_seconds)} (${timing.peer_models || 0} completed model configurations)\nPeer slow threshold: ${seconds(timing.relative_threshold_seconds)} (2 × median; descriptive comparison)\nCurrent timeout: ${seconds(timing.current_timeout_seconds)}\nSaved run timeout: ${seconds(timing.saved_timeout_seconds)}`;
            if (timing.expectation_reason)
                cell.title += `\nExpectation: ${timing.expectation_reason}`;

            cell.title += `\nTiming: ${item.timedOut ? "actually timed out" : [item.expected ? "over expected time" : null, item.relative ? "slow compared with other models" : null].filter(Boolean).join("; ") || (Number.isFinite(timing.elapsed_seconds) ? "no timing threshold exceeded" : "duration unavailable")}`;
        }
        else if (measurements.length) {
            cell.title += `\nTiming across ${measurements.length} unique observations: ${measurements.filter(item => item.timedOut).length} actual timeouts; ${measurements.filter(item => item.expected).length} over expectation; ${measurements.filter(item => item.relative).length} slow compared with peers. Counts can overlap. Triangle shows the worst timing.`;
        }

        const flagged = measurements.filter(item => item.flagged);
        if (!flagged.length)
            return;

        const timedOut = flagged.some(item => item.timedOut);
        const progress = Math.max(...flagged.map(item => item.progress));
        cell.style.position = "relative";
        const marker = StatisticsReport.Element("span", cell);
        marker.dataset.timingMarker = timedOut ? "timeout" : "slow";
        if (timedOut)
            marker.dataset.timeoutMarker = "true";

        marker.setAttribute("aria-hidden", "true");
        marker.style.position = "absolute";
        marker.style.top = "0";
        marker.style.right = "0";
        marker.style.width = "0";
        marker.style.height = "0";
        marker.style.borderTop = `6px solid ${timedOut ? "#ff0000" : `hsl(${120 - 82 * progress}, 90%, 40%)`}`;
        marker.style.borderLeft = "6px solid transparent";
        marker.style.pointerEvents = "none";
        cell.title += timedOut ? "\nRed corner: includes an actual timeout, regardless of current settings." : "\nGreen-to-amber corner: a completed run exceeded its static expectation or peer threshold.";
    },
    //#endregion
    Cell: (row, cells, heading, individual = false, total = false) => {
        const cell = StatisticsReport.Cell(row, "");
        const ids = [...new Set(cells.flatMap(item => item.ids))];
        const counts = ResultsMatrix.Counts(cells);
        const scored = counts.pass + counts.fail + counts.timeout;
        let state = scored ? "scored" : counts.observations ? "other" : "missing";
        if (individual)
            state = ids.length > 1 ? "multiple" : ids.length ? counts.observations ? StatisticsReport.Data.matrix.records[ids[0]].outcome : "missing" : "missing";

        const text = scored ? `${Math.round(counts.pass / scored * 100)}%` : "—";
        cell.style.backgroundColor = scored ? ResultsMatrix.RateColor(counts.pass / scored) : ResultsMatrix.Palette[state] || ResultsMatrix.Palette.other;
        cell.style.whiteSpace = "nowrap";
        cell.style.textAlign = "center";
        cell.style.padding = "0";
        cell.style.height = "24px";
        cell.style.width = "24px";
        cell.style.minWidth = "24px";
        cell.style.maxWidth = "24px";
        cell.style.fontSize = "10px";
        cell.style.boxSizing = "border-box";
        cell.dataset.outcome = state;
        cell.title = `${heading}\n${ResultsMatrix.CountsText(counts)}\nTotals count unique independently executed observations.`;
        ResultsMatrix.TimingMarker(cell, ids);

        if (!ids.length) {
            cell.textContent = text;
            return;
        }

        const button = StatisticsReport.Element("button", cell, text);
        button.style.background = "transparent";
        button.style.border = "0";
        button.style.color = "inherit";
        button.style.font = "inherit";
        button.style.cursor = "pointer";
        button.style.whiteSpace = "nowrap";
        button.style.padding = "0";
        button.setAttribute("aria-label", cell.title);
        button.addEventListener("click", () => ids.length === 1 ? StatisticsReport.Inspect(ids[0]) : ResultsMatrix.Inspect(ids, heading));
    },
    Render: () => {
        const scope = ResultsMatrix.Scope.value;
        const search = ResultsMatrix.Search.value.trim().toLowerCase();
        const rows = StatisticsReport.Data.matrix.rows.filter(row => (scope === "all" || row.current === (scope === "current")) && `${row.name} ${row.test_id} ${row.variant_id}`.toLowerCase().includes(search));
        for (const [status, label] of ResultsMatrix.Statuses) {
            const state = ResultsMatrix.Sections[status];
            const details = StatisticsReport.Element("details", StatisticsReport.Content);
            details.id = `judgement-${status}`;
            details.open = state.open;
            details.addEventListener("toggle", () => state.open = details.open);
            const selected = rows.filter(row => (row.judgement?.status || "needs_review") === status);
            StatisticsReport.Element("summary", details, `${label} (${new Set(selected.map(row => row.definition_id)).size} test variants)`);
            const groupingPanel = StatisticsReport.Element("details", details);
            groupingPanel.open = state.groupingOpen;
            groupingPanel.addEventListener("toggle", () => state.groupingOpen = groupingPanel.open);
            StatisticsReport.Element("summary", groupingPanel, "Grouping");
            state.groupings.Initialize(groupingPanel);
            ResultsMatrix.RenderTable(details, selected, status, state);
        }

        const key = StatisticsReport.Element("small", StatisticsReport.Content, "Red 0% → yellow 50% → green 100% · — No scored result · Triangle: green→amber slow; red timed out · Hover for details; click scores for evidence.");
        key.id = "matrix-key";
        key.style.display = "block";
        key.style.marginTop = "12px";
        const method = StatisticsReport.Element("details", StatisticsReport.Content);
        StatisticsReport.Element("summary", method, "How totals work").style.fontSize = "11px";
        StatisticsReport.Element("small", method, "Each table has separate totals. Unique passes are divided by passes + failures + timeouts. Missing and infrastructure outcomes are excluded. Historical definitions can be excluded using Evidence scope.");
    },
    RenderTable: (parent, rows, status, state) => {
        const matrix = StatisticsReport.Data.matrix;
        const groupings = state.groupings;
        const cellsFor = group => group.flatMap(row => matrix.models.map(model => row.cells[model.id] || ResultsMatrix.Empty));
        const allCounts = ResultsMatrix.Counts(cellsFor(rows));
        const summary = StatisticsReport.Element("p", parent, `${matrix.models.length} model configuration(s) · ${rows.length} variant/repetition rows · ${allCounts.observations} unique observations shown. ${allCounts.pass} PASS, ${allCounts.fail} FAIL, ${allCounts.timeout} timeout.`);
        summary.id = status === "needs_review" ? "matrix-summary" : `matrix-summary-${status}`;
        const wrap = StatisticsReport.Element("div", parent);
        const table = StatisticsReport.Element("table", wrap);
        table.id = status === "needs_review" ? "results-matrix" : `results-matrix-${status}`;
        table.style.borderCollapse = "separate";
        table.style.borderSpacing = "1px";
        table.style.fontSize = "11px";
        const header = StatisticsReport.Element("tr", StatisticsReport.Element("thead", table));
        const headers = ["Test / variant / repetition", ...matrix.models.map(model => `${model.nickname}${model.simulated ? " · SIM" : ""}`), "Total"];
        for (const [index, text] of headers.entries()) {
            const th = StatisticsReport.Element("th", header, text);
            th.scope = "col";
            th.style.position = "sticky";
            th.style.top = "0";
            th.style.zIndex = "2";
            th.style.backgroundColor = "#e2e8f0";
            th.style.padding = "2px";
            th.style.whiteSpace = "nowrap";
            if (index > 0) {
                const label = StatisticsReport.Element("span", th, text);
                th.firstChild.remove();
                label.style.writingMode = "vertical-rl";
                label.style.transform = "rotate(180deg)";
                label.style.maxHeight = "230px";
                label.style.overflow = "hidden";
                label.style.textOverflow = "ellipsis";
                th.title = index > matrix.models.length ? "Total across models" : `${matrix.models[index - 1].label} · ${matrix.models[index - 1].execution_class}${matrix.models[index - 1].simulated ? " · SIMULATED" : ""} · ${matrix.models[index - 1].id}`;
                th.style.width = "24px";
                th.style.padding = "0";
            }
        }

        const body = StatisticsReport.Element("tbody", table);
        const labelCell = (row, text, depth = 0) => {
            const th = StatisticsReport.Element("th", row, text);
            th.scope = "row";
            th.style.position = "sticky";
            th.style.left = "0";
            th.style.zIndex = "1";
            th.style.backgroundColor = "#f8fafc";
            th.style.textAlign = "left";
            th.style.minWidth = "220px";
            th.style.maxWidth = "360px";
            th.style.whiteSpace = "nowrap";
            th.style.overflow = "hidden";
            th.style.textOverflow = "ellipsis";
            th.style.padding = `0 4px 0 ${4 + depth * 12}px`;
            th.style.height = "24px";
            th.style.lineHeight = "24px";
            th.title = text;
            return th;
        };
        const presentationOrder = { "Normal JSON": 0, "Indexed arrays": 1, "Full paths": 2, "Unspecified": 3 };
        const leafOrder = (left, right) => {
            for (const axis of ["ability_category", "task_type", "prompt_comparison_set", "test_version"]) {
                const difference = ResultsMatrix.Compare(left.grouping[axis].label, right.grouping[axis].label);
                if (difference)
                    return difference;
            }

            return (presentationOrder[left.grouping.input_presentation.label] ?? 4) - (presentationOrder[right.grouping.input_presentation.label] ?? 4) ||
                ResultsMatrix.Compare(left.name, right.name) || left.repetition - right.repetition || ResultsMatrix.Compare(left.variant_id, right.variant_id) || ResultsMatrix.Compare(left.id, right.id);
        };
        const addCases = (group, depth) => {
            if (ResultsMatrix.Rows.value !== "cases")
                return;

            for (const item of [...group].sort(leafOrder)) {
                const row = StatisticsReport.Element("tr", body);
                row.dataset.kind = "case";
                row.dataset.rowId = item.id;
                const label = labelCell(row, `${item.grouping.input_presentation.label} · ${item.variant_name} / repetition ${item.repetition + 1}${item.current ? "" : ` / HISTORICAL revision ${item.revision}`}`, depth);
                label.style.cursor = "pointer";
                label.tabIndex = 0;
                label.setAttribute("role", "button");
                label.setAttribute("aria-label", `Judge ${item.test_id} / ${item.variant_id}`);
                label.title += "\nClick to judge this test variant.";
                label.addEventListener("click", () => TestJudgements.Dialog([item]));
                label.addEventListener("keydown", event => {
                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        TestJudgements.Dialog([item]);
                    }
                });
                for (const model of matrix.models) {
                    ResultsMatrix.Cell(row, [item.cells[model.id] || ResultsMatrix.Empty], `${model.label} / ${item.test_id} / ${item.variant_id} / ${item.repetition + 1}`, true);
                }

                ResultsMatrix.Cell(row, cellsFor([item]), `${item.variant_id} / all models`, false, true);
            }
        };
        const addGroups = (groupRows, depth = 0, path = []) => {
            const axis = groupings.Order[depth];
            if (!axis) {
                addCases(groupRows, depth);
                return;
            }

            const groups = Map.groupBy(groupRows, row => row.grouping[axis].key);
            const ordered = [...groups.entries()].sort(([, left], [, right]) => {
                const leftLabel = left[0].grouping[axis].label;
                const rightLabel = right[0].grouping[axis].label;
                return axis === "input_presentation" ? (presentationOrder[leftLabel] ?? 4) - (presentationOrder[rightLabel] ?? 4) : ResultsMatrix.Compare(leftLabel, rightLabel);
            });
            for (const [key, group] of ordered) {
                const label = group[0].grouping[axis].label;
                const groupPath = [...path, [axis, key]];
                const groupKey = JSON.stringify(groupPath);
                const collapsed = state.collapsed.has(groupKey);
                const heading = StatisticsReport.Element("tr", body);
                heading.dataset.kind = "group-heading";
                heading.dataset.axis = axis;
                heading.dataset.groupKey = groupKey;
                heading.dataset.level = `${depth}`;
                const headingCell = labelCell(heading, "", depth);
                headingCell.colSpan = matrix.models.length + 2;
                headingCell.style.backgroundColor = depth === 0 ? "#cbd5e1" : "#e2e8f0";
                headingCell.style.position = "static";
                const toggle = StatisticsReport.Element("button", headingCell, `${collapsed ? "▸" : "▾"} ${label}`);
                toggle.style.border = "0";
                toggle.style.background = "transparent";
                toggle.style.font = "inherit";
                toggle.style.fontWeight = "bold";
                toggle.style.cursor = "pointer";
                toggle.setAttribute("aria-label", `${collapsed ? "Expand" : "Collapse"} ${groupings.Axes[axis]}: ${label}`);
                toggle.setAttribute("aria-expanded", `${!collapsed}`);
                toggle.addEventListener("click", () => {
                    if (collapsed)
                        state.collapsed.delete(groupKey);
                    else
                        state.collapsed.add(groupKey);

                    StatisticsReport.Render();
                });
                if (axis === "test_version") {
                    const judge = StatisticsReport.Element("button", headingCell, "Judge…");
                    judge.style.marginLeft = "8px";
                    judge.style.font = "inherit";
                    judge.setAttribute("aria-label", `Judge group ${label}`);
                    judge.addEventListener("click", () => TestJudgements.Dialog(group));
                }

                if (!collapsed)
                    addGroups(group, depth + 1, groupPath);

                const subtotal = StatisticsReport.Element("tr", body);
                subtotal.dataset.kind = "group-total";
                subtotal.dataset.axis = axis;
                subtotal.dataset.groupKey = groupKey;
                subtotal.dataset.level = `${depth}`;
                const subtotalLabel = labelCell(subtotal, `${label} — total`, depth);
                subtotalLabel.style.backgroundColor = depth === 0 ? "#cbd5e1" : "#e2e8f0";
                for (const model of matrix.models) {
                    ResultsMatrix.Cell(subtotal, group.map(row => row.cells[model.id] || ResultsMatrix.Empty), `${model.label} / ${label}`);
                }

                ResultsMatrix.Cell(subtotal, cellsFor(group), `${label} / all models`, false, true);
                for (const cell of subtotal.children) {
                    cell.style.borderTop = depth === 0 ? "2px solid #64748b" : "1px solid #94a3b8";
                    cell.style.fontWeight = "bold";
                }
            }
        };
        addGroups(rows);

        const footer = StatisticsReport.Element("tr", StatisticsReport.Element("tfoot", table));
        footer.id = status === "needs_review" ? "matrix-totals" : `matrix-totals-${status}`;
        labelCell(footer, "TOTAL — filtered rows, unique observations");
        for (const model of matrix.models) {
            ResultsMatrix.Cell(footer, rows.map(row => row.cells[model.id] || ResultsMatrix.Empty), `${model.label} / total`);
        }

        ResultsMatrix.Cell(footer, cellsFor(rows), "Grand total", false, true);
        if (!rows.length)
            StatisticsReport.Element("p", parent, "No test rows match the selected scope/search.");
    }
};
//#endregion
