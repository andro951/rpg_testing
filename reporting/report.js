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
        if (location.hash.startsWith(`#results=`)) {
            StatisticsReport.Content = StatisticsReport.Element(`main`, document.body);
            StatisticsReport.Content.style.overflowWrap = `anywhere`;
            window.addEventListener(`hashchange`, StatisticsReport.InitializeEvidence);
            StatisticsReport.InitializeEvidence();
            return;
        }

        StatisticsReport.Element("h1", document.body, "RPG testing statistics");
        StatisticsReport.Element("p", document.body, `Offline snapshot · ${StatisticsReport.Data.version} · ${Object.keys(StatisticsReport.Data.matrix.records).length} saved objective results`);
        const filters = StatisticsReport.Element("div", document.body);
        filters.style.display = "flex";
        filters.style.flexWrap = "wrap";
        filters.style.gap = "16px";
        ResultsMatrix.Initialize(filters);
        StatisticsReport.Content = StatisticsReport.Element("main", document.body);
        StatisticsReport.Render();
    },
    ModelLabel: key => `${StatisticsReport.Data.models[key].label} [${key.slice(-12)}]`,
    //#region Readable evidence
    EvidenceText: (parent, value, formatJson = true) => {
        let text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
        if (formatJson && typeof value === "string" && /^[\s]*[\[{]/.test(value)) {
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
    EvidenceBlock: (parent, title) => {
        const section = StatisticsReport.Element(`section`, parent);
        section.dataset.evidenceBlock = title;
        StatisticsReport.Element(`h2`, section, title);
        return section;
    },
    PromptText: (parent, value) => {
        const exact = typeof value === `string` ? value : JSON.stringify(value, null, 2);
        const readable = exact.split(`\n`).map(line => {
            if (!/^\s*[\[{]/.test(line))
                return line;

            try {
                return JSON.stringify(JSON.parse(line), null, 2);
            }
            catch (error) {
                //Only complete JSON lines are expanded; instructions and partial JSON stay intact.
                return line;
            }
        }).join(`\n`);
        const text = StatisticsReport.EvidenceText(parent, readable, false);
        if (readable !== exact) {
            const toggle = StatisticsReport.Element(`button`, parent, `Show exact sent text`);
            let showingExact = false;
            toggle.addEventListener(`click`, () => {
                showingExact = !showingExact;
                text.textContent = showingExact ? exact : readable;
                toggle.textContent = showingExact ? `Show readable JSON` : `Show exact sent text`;
            });
        }

        return text;
    },
    ExpectedText: (parent, variant = {}, reference = null) => {
        if (reference?.kind === `reference`) {
            StatisticsReport.Element(`p`, parent, reference.label);
            StatisticsReport.EvidenceText(parent, reference.text, false);
            return;
        }

        const values = Object.entries(reference?.answers || variant.expected_answers || {});
        if (!values.length)
            StatisticsReport.Element(`p`, parent, reference?.reason || `No verified expected response text is available in this snapshot.`);

        for (const [label, value] of values) {
            if (values.length > 1)
                StatisticsReport.Element(`h3`, parent, label);

            StatisticsReport.EvidenceText(parent, typeof value === `string` ? value : JSON.stringify(value), false);
        }
    },
    ShowEvidence: (id, record, complete) => {
        const parent = StatisticsReport.Content;
        parent.replaceChildren();
        const summary = StatisticsReport.Data.matrix.records[id];
        document.title = `${summary.outcome.toUpperCase()} · ${summary.metadata.test_id} · RPG test result`;
        const header = StatisticsReport.Element(`header`, parent);
        Object.assign(header.style, {display: `flex`, alignItems: `center`, gap: `20px`, flexWrap: `wrap`});
        StatisticsReport.Element(`h1`, header, summary.outcome.toUpperCase());
        StatisticsReport.OptimizationAction(header, id, summary);
        const prompt = StatisticsReport.EvidenceBlock(parent, `Full prompt sent to the AI`);
        const output = StatisticsReport.EvidenceBlock(parent, `Full text result`);
        const expected = StatisticsReport.EvidenceBlock(parent, `Expected result`);
        const failure = StatisticsReport.EvidenceBlock(parent, `Failure reason`);
        if (complete) {
            const calls = record.calls || [];
            if (!calls.length)
                StatisticsReport.Element(`p`, prompt, `No AI request was captured in this saved record.`);

            for (const [index, call] of calls.entries()) {
                const label = `Call ${index + 1}${call.step ? ` · ${call.step}` : ``}${call.iteration ? ` · iteration ${call.iteration}` : ``}`;
                StatisticsReport.Element(`h3`, prompt, label);
                const messages = call.request_messages || call.messages || [];
                if (!messages.length)
                    StatisticsReport.Element(`p`, prompt, `No request messages were captured for this call.`);

                for (const [number, message] of messages.entries()) {
                    StatisticsReport.Element(`h4`, prompt, `Message ${number + 1} · ${message.role || `unknown role`}`);
                    StatisticsReport.PromptText(prompt, message.content);
                }

                StatisticsReport.Element(`h3`, output, label);
                if (call.incomplete || record.timed_out && index === calls.length - 1)
                    StatisticsReport.Element(`p`, output, `Partial response saved when the run stopped.`);

                StatisticsReport.EvidenceText(output, call.text ?? ``);
            }

            if (!calls.length)
                StatisticsReport.EvidenceText(output, record.outputs ?? {});

            StatisticsReport.ExpectedText(expected, record.variant_definition || {}, summary.evaluation?.expected_response);
        }
        else {
            StatisticsReport.Element(`p`, prompt, `Complete prompt unavailable in this snapshot. Open the table through Open_Results_Table.bat to load the saved record.`);
            StatisticsReport.Element(`p`, output, `Limited output preview (up to 4,000 characters).`);
            StatisticsReport.EvidenceText(output, summary.output_preview);
            StatisticsReport.Element(`p`, expected, `Limited expected-result preview (up to 4,000 characters).`);
            try {
                StatisticsReport.ExpectedText(expected, JSON.parse(summary.oracle_preview), summary.evaluation?.expected_response);
            }
            catch (error) {
                //A truncated preview cannot be unpacked; never invent its missing answer.
                StatisticsReport.EvidenceText(expected, summary.oracle_preview, false);
            }
        }

        const evaluation = summary.evaluation;
        const states = evaluation?.validation_states;
        if (states && (complete ? Object.hasOwn(record.test_definition || {}, `expected_state`) : states.expected !== null)) {
            const validation = StatisticsReport.EvidenceBlock(parent, `Resulting JSON states for validation`);
            StatisticsReport.Element(`h3`, validation, `Expected resulting JSON state`);
            StatisticsReport.EvidenceText(validation, states.expected);
            StatisticsReport.Element(`h3`, validation, `Actual resulting JSON state`);
            if (states.actual_available)
                StatisticsReport.EvidenceText(validation, states.actual);
            else
                StatisticsReport.Element(`p`, validation, `Unavailable: no valid resulting state was captured; the submitted patch failed validation.`);
        }

        const failed = summary.outcome !== `pass` || evaluation?.objective_outcome === `FAIL`;
        StatisticsReport.Element(`p`, failure, failed ? evaluation?.reason || record?.error || record?.reason || `No detailed failure reason was captured.` : `None — this result passed.`);
        if (evaluation?.score_comparison === `disagreement`)
            StatisticsReport.Element(`p`, failure, `The detailed evaluator disagrees with the saved score shown at the top.`);

        const other = StatisticsReport.EvidenceBlock(parent, `Additional information`);
        StatisticsReport.Element(`p`, other, `${summary.metadata.model_id} · ${summary.metadata.test_id} / ${summary.metadata.variant_id} · repetition ${(summary.metadata.repetition || 0) + 1} · ${id}`);
        StatisticsReport.EvaluationFeedback(other, summary);
        StatisticsReport.EvidenceSection(other, `Timing`, summary.timing || {}, false);
        StatisticsReport.EvidenceSection(other, `Result and scoring`, summary.metadata, false);
        if (summary.source_uri) {
            const link = StatisticsReport.Element(`a`, other, `Open complete original result JSON`);
            link.href = summary.source_uri;
            link.target = `_blank`;
            link.rel = `noopener`;
        }

        if (!complete)
            return;

        StatisticsReport.EvidenceSection(other, `Captured outputs`, record.outputs || {}, false);
        for (const [index, call] of (record.calls || []).entries()) {
            if (call.reasoning_text)
                StatisticsReport.EvidenceSection(other, `Call ${index + 1} saved reasoning`, call.reasoning_text, false);

            const settings = Object.fromEntries(Object.entries(call).filter(([key]) => ![`messages`, `request_messages`, `text`, `reasoning_text`, `raw_chunks`].includes(key)));
            StatisticsReport.EvidenceSection(other, `Call ${index + 1} settings and timing`, settings, false);
        }

        StatisticsReport.EvidenceSection(other, `Test definition`, { test_definition: record.test_definition, variant_definition: record.variant_definition }, false);
        const raw = StatisticsReport.Element(`details`, other);
        StatisticsReport.Element(`summary`, raw, `Complete raw record (JSON)`);
        StatisticsReport.EvidenceText(raw, record);
    },
    //#region Optimization handoff
    OptimizationAction: (parent, id, summary) => {
        const api = StatisticsReport.Data.optimization_api;
        const button = StatisticsReport.Element(`button`, parent, `Checking optimization availability…`);
        button.type = `button`;
        button.disabled = true;
        Object.assign(button.style, {padding: `10px 16px`, fontSize: `15px`, cursor: `pointer`});
        const message = StatisticsReport.Element(`small`, parent);
        message.setAttribute(`role`, `status`);
        if (!api) {
            button.textContent = `Optimize this prompt (OPRO)`;
            message.textContent = `Open the table through Workbench’s Results page or Open_Results_Table.bat to select this test for optimization.`;
            return;
        }

        const query = new URLSearchParams({model_id: summary.metadata.model_id, case_id: id});
        fetch(`${api.target_url}?${query}`).then(async response => {
            const selection = await response.json();
            if (!response.ok)
                throw new Error(selection.error || `Unable to select this result (${response.status}).`);

            button.textContent = `Optimize this prompt (OPRO)`;
            button.disabled = false;
            button.title = `Open ${selection.target.name} · ${selection.target.presentation} in Prompt Optimization. No inference starts automatically.`;
            message.textContent = api.local_worker ? `Opens Workbench on this computer. For a remote worker, open the table from that Workbench’s Results page.` : `Select settings before starting; opening the tab does not run a model.`;
            button.addEventListener(`click`, async () => {
                button.disabled = true;
                button.textContent = `Opening Prompt Optimization…`;
                message.textContent = ``;
                const navigate = url => location.assign(url);
                if (api.open_url) {
                    fetch(api.open_url, {method: `POST`, headers: {"Content-Type": `application/json`, "X-Judgement-Token": api.token}, body: JSON.stringify({model_id: summary.metadata.model_id, case_id: id})})
                        .then(async result => {
                            const data = await result.json();
                            if (!result.ok)
                                throw new Error(data.error || `Workbench could not open.`);

                            navigate(data.url);
                        }).catch(error => {
                            button.disabled = false;
                            button.textContent = `Optimize this prompt (OPRO)`;
                            message.textContent = error.message;
                        });
                }
                else {
                    const url = new URL(api.base_url, location.href);
                    url.hash = new URLSearchParams({page: `optimization`, test_id: selection.target.test_id, variant_id: selection.target.variant_id,
                        definition_id: selection.target.definition_id, origin_model_id: selection.origin_model_id, source_result_id: id}).toString();
                    navigate(url.href);
                }
            });
        }).catch(error => {
            button.textContent = `OPRO unavailable for this result`;
            button.title = error.message;
            message.textContent = error.message;
        });
    },
    //#endregion
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
    EvidenceUrl: ids => {
        const url = new URL(location.href);
        //Older running viewers reload this script but do not have the new endpoint.
        if (StatisticsReport.Data.result_tab_url === `/result/`)
            url.pathname = `/result/`;

        url.hash = `results=${ids.join(`,`)}`;
        return url.href;
    },
    Inspect: id => StatisticsReport.OpenEvidence([id]),
    OpenEvidence: ids => {
        //Open during the click so loading evidence cannot trigger popup blocking.
        window.open(StatisticsReport.EvidenceUrl(ids), `_blank`, `noopener`);
    },
    InitializeEvidence: async () => {
        const parent = StatisticsReport.Content;
        const request = (StatisticsReport.EvidenceRequest || 0) + 1;
        StatisticsReport.EvidenceRequest = request;
        parent.replaceChildren();
        const ids = [...new Set(location.hash.slice(`#results=`.length).split(`,`))];
        if (!ids.length || ids.some(id => !Object.hasOwn(StatisticsReport.Data.matrix.records, id))) {
            StatisticsReport.Element(`h1`, parent, `Result unavailable`);
            StatisticsReport.Element(`p`, parent, `This saved result is not in the current report.`);
            return;
        }

        if (ids.length > 1) {
            document.title = `Selected test results`;
            StatisticsReport.Element(`h1`, parent, `Selected test results`);
            StatisticsReport.Element(`p`, parent, `${ids.length} unique saved results. Select one to see its complete prompt, response, expected result and failure reason.`);
            const list = StatisticsReport.Element(`ul`, parent);
            for (const id of ids) {
                const summary = StatisticsReport.Data.matrix.records[id];
                const metadata = summary.metadata;
                const link = StatisticsReport.Element(`a`, StatisticsReport.Element(`li`, list), `${summary.outcome.toUpperCase()} · ${metadata.model_id} · ${metadata.test_id} / ${metadata.variant_id} · repetition ${(metadata.repetition || 0) + 1}`);
                link.href = StatisticsReport.EvidenceUrl([id]);
            }

            return;
        }

        const id = ids[0];
        const summary = StatisticsReport.Data.matrix.records[id];
        const original = StatisticsReport.Data.evidence[id];
        if (!StatisticsReport.Data.judgement_api || !summary.source_uri) {
            StatisticsReport.ShowEvidence(id, original, Boolean(original));
            return;
        }

        const loading = StatisticsReport.Element(`p`, parent, `Loading complete saved evidence…`);
        loading.setAttribute(`role`, `status`);
        try {
            const response = await fetch(summary.source_uri);
            if (!response.ok)
                throw new Error(`Evidence request failed (${response.status})`);

            const record = await response.json();
            if (request === StatisticsReport.EvidenceRequest)
                StatisticsReport.ShowEvidence(id, record, true);
        }
        catch (error) {
            if (request !== StatisticsReport.EvidenceRequest)
                return;

            StatisticsReport.ShowEvidence(id, original, Boolean(original));
            const message = StatisticsReport.Element(`p`, parent.lastElementChild, `Could not load complete evidence: ${error.message}.${original ? ` The embedded saved record is displayed.` : ` The limited preview remains available.`}`);
            message.setAttribute(`role`, `status`);
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
        ResultsMatrix.Render();
    }
};

StatisticsReport.Initialize();
