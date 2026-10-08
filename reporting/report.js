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
        const filters = StatisticsReport.Element("div", document.body);
        filters.style.display = "flex";
        filters.style.flexWrap = "wrap";
        filters.style.gap = "16px";
        ResultsMatrix.Initialize(filters);
        StatisticsReport.Content = StatisticsReport.Element("main", document.body);
        StatisticsReport.Details = StatisticsReport.Element("section", document.body);
        StatisticsReport.Details.id = "drilldown";
        StatisticsReport.Render();
    },
    ModelLabel: key => `${StatisticsReport.Data.models[key].label} [${key.slice(-12)}]`,
    //#region Readable evidence
    EvidenceText: (parent, value) => {
        let text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
        if (typeof value === "string" && /^[\s]*[\[{]/.test(value)) {
            try {
                text = JSON.stringify(JSON.parse(value), null, 2);
            }
            catch (error) {
                //Partial output and ordinary prose retain their exact saved text.
                text = value;
            }
        }

        const pre = StatisticsReport.Element("pre", parent, text ?? "null");
        pre.style.whiteSpace = "pre-wrap";
        pre.style.overflowWrap = "anywhere";
        pre.style.fontSize = "13px";
        pre.style.lineHeight = "1.5";
        pre.style.padding = "12px";
        pre.style.backgroundColor = "#f8fafc";
        pre.style.border = "1px solid #e2e8f0";
        return pre;
    },
    EvidenceValue: (parent, value, depth = 0) => {
        if (value === null || typeof value !== "object") {
            StatisticsReport.EvidenceText(parent, value);
            return;
        }

        const entries = Object.entries(value);
        if (!entries.length) {
            StatisticsReport.EvidenceText(parent, value);
            return;
        }

        for (const [key, item] of entries) {
            if (item !== null && typeof item === "object") {
                const details = StatisticsReport.Element("details", parent);
                details.open = depth < 1;
                StatisticsReport.Element("summary", details, `${key}${Array.isArray(item) ? ` (${item.length} items)` : ""}`);
                StatisticsReport.EvidenceValue(details, item, depth + 1);
            }
            else {
                StatisticsReport.Element("h4", parent, key);
                StatisticsReport.EvidenceText(parent, item);
            }
        }
    },
    EvidenceSection: (parent, title, value, open = true) => {
        const details = StatisticsReport.Element("details", parent);
        details.open = open;
        details.style.margin = "16px 0";
        StatisticsReport.Element("summary", details, title).style.fontWeight = "600";
        StatisticsReport.EvidenceValue(details, value);
        return details;
    },
    ShowEvidence: (id, record, complete) => {
        const parent = StatisticsReport.Details;
        parent.replaceChildren();
        StatisticsReport.Element("h2", parent, `Evidence ${id}`);
        const summary = StatisticsReport.Data.matrix.records[id];
        StatisticsReport.Element("p", parent, `${summary.outcome.toUpperCase()} · ${summary.metadata.model_id} · ${summary.metadata.test_id} / ${summary.metadata.variant_id}`);
        StatisticsReport.EvaluationFeedback(parent, summary);
        if (summary.source_uri) {
            const link = StatisticsReport.Element("a", parent, "Open complete original result JSON");
            link.href = summary.source_uri;
            link.target = "_blank";
            link.rel = "noopener";
        }

        if (!complete) {
            StatisticsReport.Element("p", parent, "Limited saved preview. Open this report through Open_Results_Table.bat to load complete prompts and responses.");
            StatisticsReport.EvidenceSection(parent, "Model output preview (up to 4,000 characters)", summary.output_preview);
            StatisticsReport.EvidenceSection(parent, "Expected answer preview (up to 4,000 characters)", summary.oracle_preview);
            StatisticsReport.EvidenceSection(parent, "Result and scoring", summary.metadata);
            return;
        }

        StatisticsReport.EvidenceSection(parent, "Result and scoring", { status: record.status, timed_out: record.timed_out ?? false, error: record.error ?? null, score: record.score ?? null });
        StatisticsReport.EvidenceSection(parent, "Model outputs", record.outputs ?? {});
        const expected = {};
        for (const key of ["expected_answers", "expected_patch", "result"]) {
            if (Object.hasOwn(record.variant_definition || {}, key))
                expected[key] = record.variant_definition[key];
        }

        if (Object.hasOwn(record.test_definition || {}, "expected_state"))
            expected.expected_state = record.test_definition.expected_state;

        StatisticsReport.EvidenceSection(parent, "Expected result", expected);
        const calls = StatisticsReport.Element("details", parent);
        calls.open = true;
        StatisticsReport.Element("summary", calls, `Requests and responses (${record.calls?.length || 0})`).style.fontWeight = "600";
        for (const [index, call] of (record.calls || []).entries()) {
            const section = StatisticsReport.Element("details", calls);
            section.open = index === 0;
            StatisticsReport.Element("summary", section, `Call ${index + 1}${call.step ? ` · ${call.step}` : ""}`);
            for (const [number, message] of (call.request_messages || call.messages || []).entries()) {
                StatisticsReport.Element("h4", section, `Message ${number + 1} · ${message.role || "unknown role"}`);
                StatisticsReport.EvidenceText(section, message.content);
            }

            StatisticsReport.Element("h4", section, "Model response");
            StatisticsReport.EvidenceText(section, call.text ?? "");
            if (call.reasoning_text)
                StatisticsReport.EvidenceSection(section, "Saved reasoning", call.reasoning_text, false);

            const metadata = Object.fromEntries(Object.entries(call).filter(([key]) => !["messages", "text", "reasoning_text", "raw_chunks"].includes(key)));
            StatisticsReport.EvidenceSection(section, "Call settings and timing", metadata, false);
        }

        StatisticsReport.EvidenceSection(parent, "Test definition", { test_definition: record.test_definition, variant_definition: record.variant_definition }, false);
        const raw = StatisticsReport.Element("details", parent);
        StatisticsReport.Element("summary", raw, "Complete raw record (JSON)");
        StatisticsReport.EvidenceText(raw, record);
    },
    EvaluationFeedback: (parent, summary) => {
        const evaluation = summary.evaluation;
        if (!evaluation) {
            StatisticsReport.Element(`p`, parent, `Detailed evaluator feedback is unavailable in this older report. Regenerate the results table to include it.`);
            return;
        }

        const section = StatisticsReport.Element(`section`, parent);
        section.dataset.evaluatorFeedback = `true`;
        StatisticsReport.Element(`h3`, section, `Evaluator ${evaluation.objective_outcome}`);
        StatisticsReport.Element(`p`, section, evaluation.reason);
        if (evaluation.score_comparison === `disagreement`)
            StatisticsReport.Element(`p`, section, `The detailed evaluator disagrees with the saved score. The table retains the original recorded score; review this evidence.`);

        const checks = StatisticsReport.Element(`details`, section);
        StatisticsReport.Element(`summary`, checks, `Detailed checks (${evaluation.checks.length})`);
        for (const check of evaluation.checks) {
            const detail = StatisticsReport.Element(`details`, checks);
            const step = check.step ? ` · ${check.step}` : ``;
            const status = {passed: `PASS`, failed: `FAIL`, not_evaluated: `NOT EVALUATED`, not_applicable: `NOT APPLICABLE`}[check.status] || check.status;
            StatisticsReport.Element(`summary`, detail, `${status} · ${check.code}${step} — ${check.explanation}`);
            const values = Object.fromEntries(Object.entries(check).filter(([key]) => ![`status`, `code`, `step`, `explanation`].includes(key)));
            StatisticsReport.EvidenceValue(detail, values);
        }

        StatisticsReport.Element(`small`, section, `Evaluator diagnostics are separate from manual test judgements. Cell colors and totals retain saved scores.${evaluation.evaluator_version ? ` Evaluator: ${evaluation.evaluator_version}.` : ``}`);
    },
    Inspect: async id => {
        const request = (StatisticsReport.EvidenceRequest || 0) + 1;
        StatisticsReport.EvidenceRequest = request;
        const summary = StatisticsReport.Data.matrix.records[id];
        const original = StatisticsReport.Data.evidence[id];
        StatisticsReport.ShowEvidence(id, original, Boolean(original));
        StatisticsReport.Details.scrollIntoView({ behavior: "smooth" });
        if (original || !summary.source_uri || !StatisticsReport.Data.judgement_api)
            return;

        const loading = StatisticsReport.Element("p", StatisticsReport.Details, "Loading complete saved evidence…");
        loading.setAttribute("role", "status");
        try {
            const response = await fetch(summary.source_uri);
            if (!response.ok)
                throw new Error(`Evidence request failed (${response.status})`);

            const record = await response.json();
            if (StatisticsReport.EvidenceRequest === request)
                StatisticsReport.ShowEvidence(id, record, true);
        }
        catch (error) {
            if (StatisticsReport.EvidenceRequest === request)
                loading.textContent = `Could not load complete evidence: ${error.message}. The limited preview remains available.`;
        }
    },
    //#endregion
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
        StatisticsReport.EvidenceRequest = (StatisticsReport.EvidenceRequest || 0) + 1;
        StatisticsReport.Content.replaceChildren();
        StatisticsReport.Details.replaceChildren();
        ResultsMatrix.Render();
    }
};

StatisticsReport.Initialize();
