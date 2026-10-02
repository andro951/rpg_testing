"use strict";

const StatisticsReport = {
    Data: JSON.parse(document.getElementById("evidence-data").textContent),
    Colors: { correct: "#087f5b", timeout: "#b45309", missing: "#64748b", ambiguous: "#9333ea" },
    Element: (tag, parent, text = "") => {
        const element = document.createElement(tag);
        element.textContent = text;
        parent.append(element);
        return element;
    },
    Select: (parent, label, options) => {
        const holder = StatisticsReport.Element("label", parent, `${label} `);
        const select = StatisticsReport.Element("select", holder);
        select.setAttribute("aria-label", label);
        for (const [value, text] of options) {
            const option = StatisticsReport.Element("option", select, text);
            option.value = value;
        }

        select.addEventListener("change", StatisticsReport.Render);
        return select;
    },
    Initialize: () => {
        document.body.style.fontFamily = "system-ui, sans-serif";
        document.body.style.margin = "24px";
        document.body.style.color = "#17212f";
        StatisticsReport.Element("h1", document.body, "RPG testing statistics");
        StatisticsReport.Element("p", document.body, `Offline snapshot · ${StatisticsReport.Data.version} · ${Object.keys(StatisticsReport.Data.matrix.records).length} saved objective results`);
        const remote = StatisticsReport.Data.remote_statistics;
        if (remote?.observation_records) StatisticsReport.Element("p", document.body, `Remote service: ${remote.independent_observations} observations with calls, ${remote.observation_records} records, ${remote.mapped_requested_cases} mapped requested cases, ${remote.collapsed_cases} collapsed aliases. Aliases are not independent trials; errors and aborted attempts remain unqualified evidence.`);
        const filters = StatisticsReport.Element("div", document.body);
        filters.style.display = "flex";
        filters.style.flexWrap = "wrap";
        filters.style.gap = "16px";
        const cohorts = StatisticsReport.Data.cohorts;
        StatisticsReport.Cohort = StatisticsReport.Select(filters, "Protocol", cohorts.map((item, index) => [item.id, `${index + 1}: ${item.conditions.simulated ? "SIMULATED" : "Recorded"} · ${item.rows.length} records · ${item.id.slice(0, 8)}`]));
        StatisticsReport.Kind = StatisticsReport.Select(filters, "Task", [["locate", "Locate indexes"], ["patch", "Construct patches"]]);
        StatisticsReport.View = StatisticsReport.Select(filters, "View", [["matrix", "Objective results matrix"], ["comparison", "Representation comparison"], ["grid", "Individual cases"], ["failures", "Failure categories"], ["latency", "Latency"], ["history", "Historical evidence"]]);
        ResultsMatrix.Initialize(filters);
        StatisticsReport.Content = StatisticsReport.Element("main", document.body);
        StatisticsReport.Details = StatisticsReport.Element("section", document.body);
        StatisticsReport.Details.id = "drilldown";
        const notes = StatisticsReport.Element("details", document.body);
        StatisticsReport.Element("summary", notes, "Method, limitations and original summaries");
        for (const note of StatisticsReport.Data.notes) {
            StatisticsReport.Element("p", notes, note);
        }

        StatisticsReport.Element("pre", notes, JSON.stringify(StatisticsReport.Data.original_summary, null, 2)).style.whiteSpace = "pre-wrap";
        StatisticsReport.Element("p", notes, `Unreadable evidence files: ${StatisticsReport.Data.problems.length}`);
        StatisticsReport.Element("pre", notes, JSON.stringify(StatisticsReport.Data.problems, null, 2));
        StatisticsReport.Render();
    },
    ModelLabel: key => `${StatisticsReport.Data.models[key].label} [${key.slice(-12)}]`,
    Inspect: id => {
        StatisticsReport.Details.replaceChildren();
        StatisticsReport.Element("h2", StatisticsReport.Details, `Evidence ${id}`);
        const summary = StatisticsReport.Data.matrix.records[id];
        const original = StatisticsReport.Data.evidence[id];
        StatisticsReport.Element("p", StatisticsReport.Details, original ? "Original saved record: exact messages, outputs, oracle, scoring, timings, settings and checksum. The report does not rescore or rewrite it." : "Saved outcome and metadata summary. Output/oracle previews are limited to 4,000 characters; open the original JSON for complete evidence.");
        if (summary?.source_uri) {
            const link = StatisticsReport.Element("a", StatisticsReport.Details, "Open complete original result JSON");
            link.href = summary.source_uri;
            link.target = "_blank";
            link.rel = "noopener";
        }

        if (summary?.source_archive)
            StatisticsReport.Element("p", StatisticsReport.Details, `Complete evidence is in ${summary.source_archive}`);
        const pre = StatisticsReport.Element("pre", StatisticsReport.Details, JSON.stringify(original || summary, null, 2));
        pre.style.whiteSpace = "pre-wrap";
        pre.style.overflowWrap = "anywhere";
        pre.style.maxHeight = "650px";
        pre.style.overflow = "auto";
        StatisticsReport.Details.scrollIntoView({ behavior: "smooth" });
    },
    EvidenceButton: (parent, id, text) => {
        const button = StatisticsReport.Element("button", parent, text);
        button.addEventListener("click", () => StatisticsReport.Inspect(id));
        button.title = `Inspect original evidence ${id}`;
        return button;
    },
    Table: headers => {
        const wrap = StatisticsReport.Element("div", StatisticsReport.Content);
        wrap.style.overflowX = "auto";
        const table = StatisticsReport.Element("table", wrap);
        table.style.borderCollapse = "collapse";
        const row = StatisticsReport.Element("tr", StatisticsReport.Element("thead", table));
        for (const header of headers) {
            StatisticsReport.Element("th", row, header).style.padding = "8px";
        }

        return StatisticsReport.Element("tbody", table);
    },
    Cell: (row, text) => {
        const cell = StatisticsReport.Element("td", row, text);
        cell.style.padding = "8px";
        cell.style.borderBottom = "1px solid #cbd5e1";
        return cell;
    },
    Bar: (parent, value, text, color) => {
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("viewBox", "0 0 320 24");
        svg.setAttribute("width", "320");
        svg.setAttribute("height", "24");
        svg.setAttribute("role", "img");
        svg.setAttribute("aria-label", text);
        const rect = document.createElementNS(svg.namespaceURI, "rect");
        rect.setAttribute("width", `${Math.max(0, Math.min(1, value)) * 320}`);
        rect.setAttribute("height", "24");
        rect.setAttribute("fill", color);
        svg.append(rect);
        parent.append(svg);
    },
    LatencyPlot: items => {
        const measured = items.filter(item => item.seconds !== null);
        if (!measured.length)
            return;
        StatisticsReport.Element("p", StatisticsReport.Content, "Per-case completed-response latency: horizontal axis seconds, vertical axis strict correct (top) / unsuccessful (bottom). Each dot opens its original evidence. Timeouts are counted in the table and have no completed-response latency.");
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("viewBox", "0 0 800 140");
        svg.setAttribute("role", "img");
        svg.setAttribute("aria-label", "Accuracy versus completed-response latency; interactive per-case points");
        svg.style.width = "100%";
        svg.style.maxWidth = "1000px";
        const max = Math.max(1, ...measured.map(item => item.seconds));
        for (const item of measured) {
            const circle = document.createElementNS(svg.namespaceURI, "circle");
            circle.setAttribute("cx", `${30 + item.seconds / max * 740}`);
            circle.setAttribute("cy", item.outcome === "correct" ? "30" : "95");
            circle.setAttribute("r", "6");
            circle.setAttribute("fill", { raw: "#2563eb", indexed: "#087f5b", full_paths: "#9333ea" }[item.representation]);
            circle.setAttribute("tabindex", "0");
            circle.setAttribute("role", "button");
            const label = `${StatisticsReport.ModelLabel(item.model)}, ${item.operation}, ${item.representation}: ${item.seconds.toFixed(3)} seconds, ${item.outcome}`;
            circle.setAttribute("aria-label", label);
            const title = document.createElementNS(svg.namespaceURI, "title");
            title.textContent = label;
            circle.append(title);
            circle.addEventListener("click", () => StatisticsReport.Inspect(item.id));
            circle.addEventListener("keydown", event => {
                if (event.key === "Enter" || event.key === " ")
                    StatisticsReport.Inspect(item.id);
            });
            svg.append(circle);
        }

        for (const [x, text] of [[30, "0 s"], [700, `${max.toFixed(2)} s`]]) {
            const label = document.createElementNS(svg.namespaceURI, "text");
            label.setAttribute("x", `${x}`);
            label.setAttribute("y", "135");
            label.textContent = text;
            svg.append(label);
        }

        StatisticsReport.Content.append(svg);
        StatisticsReport.Element("p", StatisticsReport.Content, "Blue: raw JSON · green: indexed objects · purple: full paths. Overlapping points can be inspected individually using the table.");
    },
    Render: () => {
        const report = StatisticsReport.Data;
        const cohort = report.cohorts.find(item => item.id === StatisticsReport.Cohort.value);
        const kind = StatisticsReport.Kind.value;
        const view = StatisticsReport.View.value;
        StatisticsReport.Content.replaceChildren();
        StatisticsReport.Details.replaceChildren();
        StatisticsReport.Cohort.parentElement.hidden = view === "matrix";
        StatisticsReport.Kind.parentElement.hidden = view === "matrix";
        for (const control of ResultsMatrix.Controls) {
            control.hidden = view !== "matrix";
        }

        if (view === "matrix") {
            ResultsMatrix.Render();
            return;
        }
        if (view === "history") {
            StatisticsReport.Element("h2", StatisticsReport.Content, "Historical evidence — excluded from current rates");
            const table = StatisticsReport.Table(["Model", "Task", "Representation", "Outcome", "Original record"]);
            for (const item of report.historical.filter(item => item.kind === kind)) {
                const row = StatisticsReport.Element("tr", table);
                for (const text of [StatisticsReport.ModelLabel(item.model), item.operation, item.representation, item.outcome]) {
                    StatisticsReport.Cell(row, text);
                }

                StatisticsReport.EvidenceButton(StatisticsReport.Cell(row, ""), item.id, "Inspect");
            }

            return;
        }

        if (!cohort) {
            StatisticsReport.Element("p", StatisticsReport.Content, "No current compatible evidence. Historical records remain available in the Historical evidence view.");
            return;
        }

        const rows = cohort.rows.filter(item => item.kind === kind);
        const cells = cohort.cells.filter(item => item.kind === kind);
        const matched = cohort.matched[kind];
        const selected = rows.filter(item => matched.some(([operation, repetition]) => item.operation === operation && item.repetition === repetition));
        StatisticsReport.Element("p", StatisticsReport.Content, `${matched.length} matched operations/repetitions across all models and representations. Coverage: ${cells.filter(item => item.ids.length === 1).length}/${cells.length} expected cells. Missing: ${cells.filter(item => item.outcome === "missing").length}. Ambiguous: ${cells.filter(item => item.outcome === "ambiguous").length}.`);
        const conditions = StatisticsReport.Element("details", StatisticsReport.Content);
        StatisticsReport.Element("summary", conditions, "Selected protocol conditions");
        StatisticsReport.Element("pre", conditions, JSON.stringify(cohort.conditions, null, 2)).style.whiteSpace = "pre-wrap";
        if (view === "grid") {
            const table = StatisticsReport.Table(["Task / repetition", "Model", "Raw JSON", "Indexed objects", "Full paths"]);
            for (const operation of ["replace", "remove", "add", "move", "copy", "test"]) {
                for (const model of [...new Set(cells.map(item => item.model))]) {
                    for (const repetition of [...new Set(cells.map(item => item.repetition))]) {
                        const row = StatisticsReport.Element("tr", table);
                        StatisticsReport.Cell(row, `${operation} / ${repetition + 1}`);
                        StatisticsReport.Cell(row, StatisticsReport.ModelLabel(model));
                        for (const representation of ["raw", "indexed", "full_paths"]) {
                            const item = cells.find(item => item.operation === operation && item.model === model && item.repetition === repetition && item.representation === representation);
                            const cell = StatisticsReport.Cell(row, "");
                            cell.style.color = StatisticsReport.Colors[item.outcome] || "#b91c1c";
                            if (!item.ids.length)
                                cell.textContent = item.outcome;
                            for (const id of item.ids) {
                                StatisticsReport.EvidenceButton(cell, id, item.outcome);
                            }
                        }
                    }
                }
            }

            return;
        }

        if (view === "failures") {
            StatisticsReport.Element("p", StatisticsReport.Content, "All observed current evidence; categories retain timeout and infrastructure distinctions. Correct-index/format diagnostics are separate from original strict accuracy.");
            const table = StatisticsReport.Table(["Model", "Representation", "Category", "Count", "Evidence"]);
            const groups = Map.groupBy(rows, item => `${item.model}|${item.representation}|${item.outcome}`);
            for (const items of groups.values()) {
                const item = items[0];
                const row = StatisticsReport.Element("tr", table);
                for (const text of [StatisticsReport.ModelLabel(item.model), item.representation, item.outcome, items.length]) {
                    StatisticsReport.Cell(row, text);
                }

                const cell = StatisticsReport.Cell(row, "");
                for (const entry of items) {
                    StatisticsReport.EvidenceButton(cell, entry.id, `${entry.operation}/${entry.repetition + 1}`);
                }
            }

            return;
        }

        if (!matched.length)
            StatisticsReport.Element("p", StatisticsReport.Content, "No complete matched set. Comparison rates are unavailable; inspect coverage and individual evidence.");
        if (view === "latency") {
            StatisticsReport.Element("p", StatisticsReport.Content, "Latency describes all observed current cases. Its accuracy/counts use those observed cases, including timeouts; task coverage can differ, so these are not matched comparative rates. Prompt-processing/generation metrics, where recorded, appear in each original call's timings and usage.");
            StatisticsReport.LatencyPlot(rows);
        }

        const table = StatisticsReport.Table(view === "latency" ? ["Model", "Representation", "Accuracy vs median latency", "Completed responses", "Timeouts", "Per-case latency / timing evidence"] : ["Model", "Representation", "Strict correct / total", "Accuracy", "Index diagnostic correct / total", "Evidence"]);
        for (const model of [...new Set(rows.map(item => item.model))]) {
            for (const representation of ["raw", "indexed", "full_paths"]) {
                const items = (view === "latency" ? rows : selected).filter(item => item.model === model && item.representation === representation && !["error", "aborted", "skipped", "invalid_measurement", "unscored"].includes(item.outcome));
                const correct = items.filter(item => item.outcome === "correct").length;
                const row = StatisticsReport.Element("tr", table);
                StatisticsReport.Cell(row, StatisticsReport.ModelLabel(model));
                StatisticsReport.Cell(row, representation);
                if (view === "latency") {
                    const times = items.map(item => item.seconds).filter(value => value !== null).sort((a, b) => a - b);
                    const median = times.length ? (times[Math.floor((times.length - 1) / 2)] + times[Math.floor(times.length / 2)]) / 2 : null;
                    StatisticsReport.Cell(row, `${items.length ? (correct / items.length * 100).toFixed(1) + "%" : "unavailable"} / ${median === null ? "unavailable" : median.toFixed(3) + " s median"}`);
                    StatisticsReport.Cell(row, `${times.length}`);
                    StatisticsReport.Cell(row, `${items.filter(item => item.outcome === "timeout").length}`);
                    const cell = StatisticsReport.Cell(row, "");
                    const max = Math.max(1, ...times);
                    for (const item of items) {
                        StatisticsReport.EvidenceButton(cell, item.id, `${item.operation}: ${item.seconds === null ? item.outcome : item.seconds.toFixed(3) + " s"}`);
                        if (item.seconds !== null)
                            StatisticsReport.Bar(cell, item.seconds / max, `${item.operation}: ${item.seconds} seconds`, "#2563eb");
                    }
                }
                else {
                    StatisticsReport.Cell(row, `${correct}/${items.length}`);
                    const percent = items.length ? `${(correct / items.length * 100).toFixed(1)}%` : "unavailable";
                    const cell = StatisticsReport.Cell(row, percent);
                    if (items.length)
                        StatisticsReport.Bar(cell, correct / items.length, percent, "#087f5b");
                    StatisticsReport.Cell(row, kind === "locate" ? `${items.filter(item => ["correct", "correct_index_wrong_format"].includes(item.outcome)).length}/${items.length}` : "not applicable");
                    const evidence = StatisticsReport.Cell(row, "");
                    for (const item of items) {
                        StatisticsReport.EvidenceButton(evidence, item.id, item.operation);
                    }
                }
            }
        }
    }
};

StatisticsReport.Initialize();
