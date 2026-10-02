"use strict";

//#region Grouping presets and ordered levels
const MatrixGroupings = {
    Create: status => {
const groupings = {
    Axes: {
        ability_category: "Ability category", task_type: "Task type",
        prompt_comparison_set: "Prompt comparison set", test_version: "Test version",
        input_presentation: "Input presentation"
    },
    StorageKey: `rpg-testing.matrix-groupings.v1.${status}`,
    Defaults: () => {
        const base = ["ability_category", "task_type", "prompt_comparison_set", "test_version"];
        return [
            { name: "Individual tests", axes: base },
            ...["Presentation overall", "Presentation by ability", "Presentation by task", "Presentation by scenario"].map((name, index) => {
                const axes = [...base];
                axes.splice(index, 0, "input_presentation");
                return { name, axes };
            })
        ];
    },
    Signature: axes => JSON.stringify(axes),
    ValidAxes: axes => Array.isArray(axes) && axes.length <= 5 && new Set(axes).size === axes.length && axes.every(axis => Object.hasOwn(groupings.Axes, axis)),
    ValidState: state => state?.version === 1 && groupings.ValidAxes(state.axes) && Array.isArray(state.presets) &&
        state.presets.every(preset => typeof preset.name === "string" && preset.name.trim().length > 0 && preset.name.length <= 80 && groupings.ValidAxes(preset.axes)) &&
        new Set(state.presets.map(preset => preset.name.trim().toLowerCase())).size === state.presets.length &&
        new Set(state.presets.map(preset => groupings.Signature(preset.axes))).size === state.presets.length,
    Match: () => groupings.Presets.findIndex(preset => groupings.Signature(preset.axes) === groupings.Signature(groupings.Order)),
    Persist: () => {
        try {
            localStorage.setItem(groupings.StorageKey, JSON.stringify({ version: 1, presets: groupings.Presets, axes: groupings.Order }));
            groupings.Message.textContent = "Presets and the selected grouping are saved in this browser.";
        }
        catch (error) {
            groupings.Message.textContent = `Browser storage is unavailable; changes last for this session only. ${error.message}`;
        }
    },
    Initialize: parent => {
        let message = "Presets and the selected grouping are saved in this browser.";
        let firstVisit = false;
        if (!groupings.Initialized) {
            groupings.Presets = groupings.Defaults();
            groupings.Order = [...groupings.Presets[0].axes];
            try {
                const saved = localStorage.getItem(groupings.StorageKey);
                firstVisit = saved === null;
                if (saved !== null) {
                    const state = JSON.parse(saved);
                    if (!groupings.ValidState(state))
                        throw new Error("Invalid saved preset data");

                    groupings.Presets = state.presets;
                    groupings.Order = state.axes;
                }
            }
            catch (error) {
                message = `Saved presets could not be loaded: ${error.message}. Defaults are available for this session.`;
            }

            groupings.Initialized = true;
        }

        const panel = StatisticsReport.Element("fieldset", parent);
        panel.id = `matrix-groupings-${status}`;
        panel.style.flexBasis = "100%";
        panel.style.border = "1px solid #cbd5e1";
        panel.style.borderRadius = "8px";
        panel.style.padding = "12px";
        StatisticsReport.Element("legend", panel, "Group results");
        const label = StatisticsReport.Element("label", panel, "Preset ");
        groupings.Select = StatisticsReport.Element("select", label);
        groupings.Select.setAttribute("aria-label", "Grouping preset");
        groupings.Select.addEventListener("change", () => {
            const preset = groupings.Presets[Number(groupings.Select.value)];
            if (preset)
                groupings.Change([...preset.axes]);
        });
        groupings.SaveNew = StatisticsReport.Element("button", panel, "Save as new…");
        groupings.SaveNew.style.marginLeft = "12px";
        groupings.SaveNew.addEventListener("click", groupings.SaveDialog);
        groupings.Delete = StatisticsReport.Element("button", panel, "Delete…");
        groupings.Delete.style.marginLeft = "8px";
        groupings.Delete.addEventListener("click", groupings.DeleteDialog);
        groupings.Levels = StatisticsReport.Element("ol", panel);
        groupings.Levels.setAttribute("aria-label", "Grouping priority, outermost first");
        groupings.Levels.style.margin = "10px 0";
        const addLabel = StatisticsReport.Element("label", panel, "Add level ");
        groupings.AddSelect = StatisticsReport.Element("select", addLabel);
        groupings.AddSelect.setAttribute("aria-label", "Add grouping level");
        groupings.Add = StatisticsReport.Element("button", panel, "Add");
        groupings.Add.addEventListener("click", () => {
            if (groupings.AddSelect.value)
                groupings.Change([...groupings.Order, groupings.AddSelect.value]);
        });
        StatisticsReport.Element("p", panel, "Outermost first. Unselected levels are sorted automatically; presentations stay adjacent within each test version. Totals appear at the bottom of every group.").style.margin = "8px 0";
        groupings.Message = StatisticsReport.Element("small", panel, message);
        groupings.Message.setAttribute("role", "status");
        groupings.Refresh();
        if (firstVisit)
            groupings.Persist();

        return panel;
    },
    Change: axes => {
        if (!groupings.ValidAxes(axes))
            throw new Error("Invalid grouping levels");

        groupings.Order = axes;
        groupings.Refresh();
        groupings.Persist();
        StatisticsReport.Render();
    },
    Refresh: () => {
        const match = groupings.Match();
        const select = groupings.Select;
        select.replaceChildren();
        const custom = StatisticsReport.Element("option", select, "Custom grouping");
        custom.value = "custom";
        custom.disabled = true;
        for (const [index, preset] of groupings.Presets.entries()) {
            StatisticsReport.Element("option", select, preset.name).value = `${index}`;
        }

        select.value = match < 0 ? "custom" : `${match}`;
        groupings.SaveNew.disabled = match >= 0;
        groupings.Delete.disabled = match < 0;
        groupings.Levels.replaceChildren();
        for (const [index, axis] of groupings.Order.entries()) {
            const name = groupings.Axes[axis];
            const item = StatisticsReport.Element("li", groupings.Levels, name + " ");
            item.style.padding = "2px 0";
            for (const [caption, delta] of [["↑", -1], ["↓", 1]]) {
                const button = StatisticsReport.Element("button", item, caption);
                button.setAttribute("aria-label", `Move ${name} ${delta < 0 ? "up" : "down"}`);
                button.disabled = index + delta < 0 || index + delta >= groupings.Order.length;
                button.addEventListener("click", () => {
                    const axes = [...groupings.Order];
                    [axes[index], axes[index + delta]] = [axes[index + delta], axes[index]];
                    groupings.Change(axes);
                });
            }

            const remove = StatisticsReport.Element("button", item, "Remove");
            remove.setAttribute("aria-label", `Remove ${name}`);
            remove.addEventListener("click", () => groupings.Change(groupings.Order.filter(level => level !== axis)));
        }

        groupings.AddSelect.replaceChildren();
        for (const [axis, label] of Object.entries(groupings.Axes)) {
            if (!groupings.Order.includes(axis))
                StatisticsReport.Element("option", groupings.AddSelect, label).value = axis;
        }

        groupings.Add.disabled = groupings.AddSelect.options.length === 0;
        groupings.AddSelect.disabled = groupings.Add.disabled;
    },
    Dialog: title => {
        const dialog = StatisticsReport.Element("dialog", document.body);
        dialog.setAttribute("aria-label", title);
        dialog.style.border = "1px solid #94a3b8";
        dialog.style.borderRadius = "12px";
        dialog.style.padding = "24px";
        dialog.style.boxShadow = "0 12px 48px #0003";
        dialog.style.maxWidth = "min(420px, 80vw)";
        StatisticsReport.Element("h2", dialog, title).style.marginTop = "0";
        const form = StatisticsReport.Element("form", dialog);
        const cancel = StatisticsReport.Element("button", form, "Cancel");
        cancel.type = "button";
        cancel.addEventListener("click", () => dialog.close());
        dialog.addEventListener("close", () => dialog.remove());
        return { dialog, form, cancel };
    },
    SaveDialog: () => {
        if (groupings.Match() >= 0)
            return;

        const { dialog, form, cancel } = groupings.Dialog("Save grouping preset");
        const label = StatisticsReport.Element("label", form, "Preset name ");
        form.prepend(label);
        const input = StatisticsReport.Element("input", label);
        input.setAttribute("aria-label", "Preset name");
        input.required = true;
        input.maxLength = 80;
        input.style.display = "block";
        input.style.padding = "8px";
        input.style.margin = "8px 0 16px";
        input.addEventListener("input", () => input.setCustomValidity(""));
        const create = StatisticsReport.Element("button", form, "Create preset");
        create.type = "submit";
        create.style.marginLeft = "8px";
        form.addEventListener("submit", event => {
            event.preventDefault();
            const name = input.value.trim();
            if (!name || groupings.Presets.some(preset => preset.name.toLowerCase() === name.toLowerCase())) {
                input.setCustomValidity(name ? "A preset already has that name." : "Enter a preset name.");
                input.reportValidity();
                return;
            }

            if (groupings.Match() >= 0)
                return;

            groupings.Presets.push({ name, axes: [...groupings.Order] });
            groupings.Refresh();
            groupings.Persist();
            dialog.close();
        });
        dialog.showModal();
        input.focus();
    },
    DeleteDialog: () => {
        const match = groupings.Match();
        if (match < 0)
            return;

        const preset = groupings.Presets[match];
        const { dialog, form } = groupings.Dialog("Delete grouping preset");
        form.prepend(StatisticsReport.Element("p", dialog, `Delete “${preset.name}”? The current grouping will remain available as a custom combination.`));
        const remove = StatisticsReport.Element("button", form, "Delete preset");
        remove.style.marginLeft = "8px";
        form.addEventListener("submit", event => {
            event.preventDefault();
            groupings.Presets.splice(match, 1);
            groupings.Refresh();
            groupings.Persist();
            dialog.close();
        });
        dialog.showModal();
    }
};
        return groupings;
    }
};
//#endregion