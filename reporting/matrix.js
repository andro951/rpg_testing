"use strict";

//#region All-results matrix
const ResultsMatrix = {
    Empty: { ids: [], primary_ids: [], reference_ids: [] },
    Palette: { pass: "hsl(120, 75%, 80%)", fail: "hsl(0, 75%, 80%)", timeout: "hsl(0, 75%, 80%)", reference: "#dbeafe", multiple: "#ede9fe", missing: "#f1f5f9", other: "#fef3c7" },
    RateColor: rate => `hsl(${Math.max(0, Math.min(1, rate)) * 120}, 75%, 80%)`,
    Initialize: parent => {
        ResultsMatrix.Scope = StatisticsReport.Select(parent, "Evidence scope", [["all", "All saved results"], ["current", "Current definitions"], ["historical", "Historical definitions"]]);
        ResultsMatrix.Rows = StatisticsReport.Select(parent, "Rows", [["cases", "Every variant / repetition"], ["tests", "Tests with totals"]]);
        const label = StatisticsReport.Element("label", parent, "Find test ");
        ResultsMatrix.Search = StatisticsReport.Element("input", label);
        ResultsMatrix.Search.type = "search";
        ResultsMatrix.Search.setAttribute("aria-label", "Find test");
        ResultsMatrix.Search.addEventListener("input", StatisticsReport.Render);
        ResultsMatrix.Controls = [ResultsMatrix.Scope.parentElement, ResultsMatrix.Rows.parentElement, label];
    },
    Counts: cells => {
        const records = StatisticsReport.Data.matrix.records;
        const ids = new Set(cells.flatMap(cell => cell.primary_ids));
        const counts = { pass: 0, fail: 0, timeout: 0, error: 0, aborted: 0, skipped: 0, invalid: 0, unscored: 0,
            observations: ids.size, references: cells.reduce((n, c) => n + c.reference_ids.length, 0), not_run: cells.filter(c => !c.ids.length).length };
        for (const id of ids) {
            const state = records[id].outcome;
            counts[state in counts ? state : "unscored"]++;
        }

        return counts;
    },
    CountsText: counts => {
        const scored = counts.pass + counts.fail + counts.timeout;
        const extras = [["timeout", "timeout"], ["error", "error"], ["aborted", "aborted"], ["skipped", "skipped"], ["invalid", "invalid"], ["unscored", "unscored"], ["not_run", "not recorded"], ["references", "references"]];
        const text = `${counts.pass} PASS / ${counts.fail} FAIL${scored ? ` · ${(counts.pass / scored * 100).toFixed(1)}%` : " · unscored"}`;
        return text + extras.filter(([key]) => counts[key]).map(([key, label]) => `\n${counts[key]} ${label}`).join("");
    },
    Inspect: (ids, heading) => {
        const parent = StatisticsReport.Details;
        parent.replaceChildren();
        StatisticsReport.Element("h2", parent, heading);
        StatisticsReport.Element("p", parent, `${ids.length} unique saved result(s). Open a result for its score and original evidence. References do not create additional trials.`);
        for (const id of ids) {
            const summary = StatisticsReport.Data.matrix.records[id];
            const record = summary.metadata;
            StatisticsReport.EvidenceButton(parent, id, `${summary.outcome.toUpperCase()} · ${record.test_id} / ${record.variant_id} / repetition ${(record.repetition || 0) + 1} · ${id.slice(0, 8)}`);
        }

        parent.scrollIntoView({ behavior: "smooth" });
    },
    Cell: (row, cells, heading, individual = false, total = false) => {
        const cell = StatisticsReport.Cell(row, "");
        const ids = [...new Set(cells.flatMap(c => c.ids))];
        const counts = ResultsMatrix.Counts(cells);
        let state = counts.fail || counts.timeout ? "fail" : counts.error || counts.aborted || counts.invalid || counts.skipped || counts.unscored || (counts.observations && counts.not_run) ? "other" : counts.pass ? "pass" : counts.references ? "reference" : "missing";
        let text = ResultsMatrix.CountsText(counts);
        if (individual) {
            state = ids.length > 1 ? "multiple" : ids.length ? StatisticsReport.Data.matrix.records[ids[0]].outcome : "missing";
            const reference = ids.length && !counts.observations;
            text = ids.length > 1 ? `MULTIPLE (${ids.length})` : ids.length ? state.toUpperCase() : "NOT RECORDED";
            if (reference) {
                text = `↪ ${text}`;
                state = "reference";
            }
        }

        const fullText = text;
        if (!total) {
            const markers = { pass: "P", fail: "F", timeout: "T", error: "E", aborted: "A", skipped: "S", invalid: "!", unscored: "?", missing: "·" };
            const scored = counts.pass + counts.fail + counts.timeout;
            text = individual ? ids.length > 1 ? `${ids.length}` : ids.length ? `${counts.observations ? "" : "↪"}${markers[StatisticsReport.Data.matrix.records[ids[0]].outcome] || "?"}` : "·" : scored ? `${Math.round(counts.pass / scored * 100)}%` : counts.references ? "↪" : ids.length ? "!" : "·";
        }
        else {
            text = `${counts.pass} PASS / ${counts.fail} FAIL${counts.timeout ? ` / ${counts.timeout} timeout` : ""}${counts.not_run ? ` / ${counts.not_run} not recorded` : ""}${counts.references ? ` / ${counts.references} ↪` : ""}${counts.error + counts.aborted + counts.skipped + counts.invalid + counts.unscored ? " / other statuses" : ""}`;
        }

        const scored = counts.pass + counts.fail + counts.timeout;
        cell.style.backgroundColor = !individual && scored ? ResultsMatrix.RateColor(counts.pass / scored) : ResultsMatrix.Palette[state] || ResultsMatrix.Palette.other;
        cell.style.whiteSpace = "nowrap";
        cell.style.textAlign = "center";
        cell.style.padding = "0";
        cell.style.height = "24px";
        cell.style.width = total ? "auto" : "24px";
        cell.style.minWidth = total ? "150px" : "24px";
        cell.style.maxWidth = total ? "none" : "24px";
        cell.style.fontSize = total ? "11px" : "10px";
        cell.style.boxSizing = "border-box";
        cell.dataset.outcome = state;
        cell.title = `${heading}\n${ResultsMatrix.CountsText(counts)}\nTotals use unique primary observations; references are excluded.`;
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
        button.setAttribute("aria-label", `${heading}: ${fullText}`);
        button.addEventListener("click", () => ids.length === 1 ? StatisticsReport.Inspect(ids[0]) : ResultsMatrix.Inspect(ids, heading));
    },
    Render: () => {
        const matrix = StatisticsReport.Data.matrix;
        const scope = ResultsMatrix.Scope.value;
        const search = ResultsMatrix.Search.value.trim().toLowerCase();
        const rows = matrix.rows.filter(row => (scope === "all" || row.current === (scope === "current")) && `${row.name} ${row.test_id} ${row.variant_id}`.toLowerCase().includes(search));
        const parent = StatisticsReport.Content;
        StatisticsReport.Element("h2", parent, "Objective results — tests × models");
        StatisticsReport.Element("p", parent, "24 px squares: green P = pass, red F = fail / T = timeout, amber E/S/A/!/ ? = error/skipped/aborted/invalid/unscored, gray · = not recorded, blue ↪ = reference to one Perchance observation. Subtotal and total cells use a pass-rate gradient: 0% red, 50% yellow, 100% green. Missing and other statuses keep their separate colors. Hover for full counts; click for evidence.");
        StatisticsReport.Element("p", parent, matrix.note);
        if (!matrix.models.length) {
            StatisticsReport.Element("p", parent, "No saved model results. Expected test rows are retained; model columns appear when evidence is saved.");
            return;
        }

        const cellsFor = group => group.flatMap(row => matrix.models.map(model => row.cells[model.id] || ResultsMatrix.Empty));
        const allCounts = ResultsMatrix.Counts(cellsFor(rows));
        const summary = StatisticsReport.Element("p", parent, `${matrix.models.length} model configuration(s) · ${rows.length} variant/repetition rows · ${allCounts.observations} unique observations shown · ${allCounts.references} reference cells. ${allCounts.pass} PASS, ${allCounts.fail} FAIL, ${allCounts.timeout} timeout.`);
        summary.id = "matrix-summary";
        const wrap = StatisticsReport.Element("div", parent);
        const table = StatisticsReport.Element("table", wrap);
        table.id = "results-matrix";
        table.style.borderCollapse = "separate";
        table.style.borderSpacing = "1px";
        table.style.fontSize = "11px";
        const header = StatisticsReport.Element("tr", StatisticsReport.Element("thead", table));
        const headers = ["Test / variant / repetition", ...matrix.models.map(m => `${m.nickname}${m.simulated ? " · SIM" : ""}`), "Total across models"];
        for (const [index, text] of headers.entries()) {
            const th = StatisticsReport.Element("th", header, text);
            th.scope = "col";
            th.style.position = "sticky";
            th.style.top = "0";
            th.style.zIndex = "2";
            th.style.backgroundColor = "#e2e8f0";
            th.style.padding = "2px";
            th.style.whiteSpace = "nowrap";
            if (index > 0 && index <= matrix.models.length) {
                const label = StatisticsReport.Element("span", th, text);
                th.firstChild.remove();
                label.style.writingMode = "vertical-rl";
                label.style.transform = "rotate(180deg)";
                label.style.maxHeight = "230px";
                label.style.overflow = "hidden";
                label.style.textOverflow = "ellipsis";
                th.title = `${matrix.models[index - 1].label} · ${matrix.models[index - 1].execution_class}${matrix.models[index - 1].simulated ? " · SIMULATED" : ""} · ${matrix.models[index - 1].id}`;
                th.style.width = "24px";
                th.style.padding = "0";
            }
        }

        const body = StatisticsReport.Element("tbody", table);
        const groups = Map.groupBy(rows, r => `${r.current}|${r.test_id}|${r.comparison_id}`);
        const labelCell = (row, text) => {
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
            th.style.padding = "0 4px";
            th.style.height = "24px";
            th.style.lineHeight = "24px";
            th.title = text;
        };
        for (const group of groups.values()) {
            const label = `${group[0].name}${group[0].name === group[0].test_id ? "" : ` [${group[0].test_id}]`}${group[0].current ? "" : " · HISTORICAL"}`;
            const subtotal = StatisticsReport.Element("tr", body);
            subtotal.dataset.kind = "test-total";
            labelCell(subtotal, `${label} — total`);
            for (const model of matrix.models) {
                ResultsMatrix.Cell(subtotal, group.map(r => r.cells[model.id] || ResultsMatrix.Empty), `${model.label} / ${label}`);
            }

            ResultsMatrix.Cell(subtotal, cellsFor(group), `${label} / all models`, false, true);
            if (ResultsMatrix.Rows.value === "cases") {
                for (const item of group) {
                    const row = StatisticsReport.Element("tr", body);
                    row.dataset.kind = "case";
                    labelCell(row, `${item.variant_name} / repetition ${item.repetition + 1}${item.current ? "" : ` / revision ${item.revision}`}`);
                    for (const model of matrix.models) {
                        ResultsMatrix.Cell(row, [item.cells[model.id] || ResultsMatrix.Empty], `${model.label} / ${item.test_id} / ${item.variant_id} / ${item.repetition + 1}`, true);
                    }

                    ResultsMatrix.Cell(row, cellsFor([item]), `${item.variant_id} / all models`, false, true);
                }
            }
        }

        const footer = StatisticsReport.Element("tr", StatisticsReport.Element("tfoot", table));
        footer.id = "matrix-totals";
        labelCell(footer, "TOTAL — visible rows, unique observations");
        for (const model of matrix.models) {
            ResultsMatrix.Cell(footer, rows.map(r => r.cells[model.id] || ResultsMatrix.Empty), `${model.label} / total`);
        }

        ResultsMatrix.Cell(footer, cellsFor(rows), "Grand total", false, true);
        const totals = StatisticsReport.Table(["Model totals", "Pass", "Fail", "Timeout", "Other statuses", "Not recorded", "References"]);
        for (const model of matrix.models) {
            const counts = ResultsMatrix.Counts(rows.map(r => r.cells[model.id] || ResultsMatrix.Empty));
            const row = StatisticsReport.Element("tr", totals);
            for (const value of [model.nickname, counts.pass, counts.fail, counts.timeout, counts.error + counts.aborted + counts.skipped + counts.invalid + counts.unscored, counts.not_run, counts.references]) {
                const cell = StatisticsReport.Cell(row, `${value}`);
                if (value === model.nickname)
                    cell.title = `${model.label} · ${model.execution_class}${model.simulated ? " · SIMULATED" : ""} · ${model.id}`;
            }
        }
        if (!rows.length)
            StatisticsReport.Element("p", parent, "No test rows match the selected scope/search.");
    }
};
//#endregion
