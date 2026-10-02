"use strict";

//#region Manual test review
const TestJudgements = {
    Dialog: rows => {
        const definitions = [...new Map(rows.map(row => [row.definition_id, row])).values()];
        const dialog = StatisticsReport.Element("dialog", document.body);
        dialog.setAttribute("aria-label", "Judge tests");
        dialog.style.border = "1px solid #94a3b8";
        dialog.style.borderRadius = "12px";
        dialog.style.padding = "24px";
        dialog.style.maxWidth = "min(560px, 85vw)";
        dialog.style.boxShadow = "0 12px 48px #0003";
        StatisticsReport.Element("h2", dialog, `Judge ${definitions.length} test variant${definitions.length === 1 ? "" : "s"}`);
        if (!StatisticsReport.Data.judgement_api) {
            StatisticsReport.Element("p", dialog, "Open Open_Results_Table.bat to save judgements in the repository and enforce run blocking. This file is a read-only snapshot.");
            StatisticsReport.Element("button", dialog, "Close").addEventListener("click", () => dialog.close());
            dialog.addEventListener("close", () => dialog.remove());
            dialog.showModal();
            return;
        }

        const targets = StatisticsReport.Element("details", dialog);
        StatisticsReport.Element("summary", targets, "Selected definitions");
        for (const row of definitions) {
            StatisticsReport.Element("p", targets, `${row.name} / ${row.variant_name}`).style.fontSize = "12px";
        }

        const form = StatisticsReport.Element("form", dialog);
        const field = (caption, tag) => {
            const label = StatisticsReport.Element("label", form, caption);
            label.style.display = "block";
            label.style.margin = "10px 0";
            const control = StatisticsReport.Element(tag, label);
            control.setAttribute("aria-label", caption);
            control.style.display = "block";
            control.style.padding = "6px";
            return control;
        };
        const status = field("Judgement", "select");
        const blocked = definitions.some(row => row.judgement?.blocked);
        for (const [value, label] of ResultsMatrix.Statuses) {
            const option = StatisticsReport.Element("option", status, label);
            option.value = value;
            option.disabled = blocked && value !== "rejected";
        }

        status.value = blocked ? "rejected" : definitions[0].judgement?.status || "needs_review";
        const reason = field("Reason", "select");
        for (const text of ["Reviewed and accepted", "Needs investigation", "Outside scope", "Ambiguous instructions", "Incorrect expected result", "Uncontrolled comparison", "Redundant test", "Missing requirements or limits", "Other"]) {
            StatisticsReport.Element("option", reason, text).value = text;
        }

        reason.value = definitions[0].judgement?.reason || "Needs investigation";
        const reviewer = field("Reviewer", "input");
        reviewer.value = definitions[0].judgement?.reviewer || "Isaac";
        reviewer.required = true;
        reviewer.maxLength = 80;
        const note = field("Note", "textarea");
        note.value = definitions.length === 1 ? definitions[0].judgement?.note || "" : "";
        note.maxLength = 4000;
        note.rows = 3;
        note.style.width = "100%";
        note.style.boxSizing = "border-box";
        const warning = StatisticsReport.Element("p", form);
        warning.style.fontSize = "12px";
        const updateWarning = () => {
            warning.textContent = status.value === "rejected" ? "Rejection permanently blocks these exact definitions from running again. An edited definition starts in Needs review." : "Only the judgement changes. Saved scores and responses are preserved.";
        };
        status.addEventListener("change", () => {
            if (status.value === "accepted")
                reason.value = "Reviewed and accepted";
            else if (status.value === "needs_review")
                reason.value = "Needs investigation";
            else if (reason.value === "Reviewed and accepted" || reason.value === "Needs investigation")
                reason.value = "Other";

            updateWarning();
        });
        updateWarning();
        const error = StatisticsReport.Element("p", form);
        error.setAttribute("role", "alert");
        error.style.color = "#b91c1c";
        const cancel = StatisticsReport.Element("button", form, "Cancel");
        cancel.type = "button";
        cancel.addEventListener("click", () => dialog.close());
        const submit = StatisticsReport.Element("button", form, "Apply judgement");
        submit.type = "submit";
        submit.style.marginLeft = "8px";
        form.addEventListener("submit", async event => {
            event.preventDefault();
            submit.disabled = true;
            error.textContent = "";
            try {
                const api = StatisticsReport.Data.judgement_api;
                const response = await fetch(api.url, {
                    method: "POST", headers: { "Content-Type": "application/json", "X-Judgement-Token": api.token },
                    body: JSON.stringify({ ids: definitions.map(row => row.definition_id), status: status.value, reason: reason.value, reviewer: reviewer.value.trim(), note: note.value })
                });
                const result = await response.json();
                if (!response.ok)
                    throw new Error(result.error || "Could not save judgement");

                for (const row of StatisticsReport.Data.matrix.rows) {
                    if (result.entries[row.definition_id])
                        row.judgement = result.entries[row.definition_id];
                }

                dialog.close();
                StatisticsReport.Render();
            }
            catch (failure) {
                error.textContent = failure.message;
                submit.disabled = false;
            }
        });
        dialog.addEventListener("close", () => dialog.remove());
        dialog.showModal();
        status.focus();
    }
};
//#endregion
