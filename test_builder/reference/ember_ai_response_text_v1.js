(function(root) {
    "use strict";

    function parseStateTextOperations(raw) {
        const text = String(raw ?? "").trim();
        if (text === "none")
            return {};
    
        if (!text)
            throw new Error("State response is empty; return none or update records.");
    
        const lines = text.split(/\r?\n/);
        const operations = {};
        const written = new Set();
        for (let index = 0; index < lines.length; index++) {
            if (!lines[index].trim())
                continue;
    
            const header = /^(set|append|change|remove): (\/.*)$/.exec(lines[index]);
            if (!header)
                throw new Error(`State line ${index + 1}: expected set, append, change, or remove with an exact /path.`);
    
            const [,operation,pointer] = header;
            const parts = pointer.slice(1).split("/");
            if (parts.some(part=>!part || /~(?![01])/.test(part)))
                throw new Error(`State line ${index + 1}: invalid path ${pointer}.`);
    
            const path = parts.map(part=>part.replace(/~1/g,"/").replace(/~0/g,"~"));
            if (path.some(part=>["__proto__","prototype","constructor"].includes(part)))
                throw new Error(`State line ${index + 1}: unsafe path ${pointer}.`);
    
            const writeKey = `${operation}:${pointer}`;
            if (operation !== "append" && written.has(writeKey))
                throw new Error(`State response repeats ${writeKey}.`);
    
            written.add(writeKey);
            if (operation === "remove") {
                (operations.d ||= []).push({path});
                continue;
            }
    
            index++;
            const valueLine=/^(null|list|object):[ \t]*$/.test(lines[index] || "")
                ? lines[index].trimEnd() : lines[index] || "";
            const typed = /^(text|number|boolean|null|list|object):(?: (.*))?$/.exec(valueLine);
            if (!typed)
                throw new Error(`State line ${index + 1}: expected one typed value after ${operation}.`);
    
            const [,type,content] = typed;
            let value;
            if (type === "text")
                value = content ?? "";
            else if (type === "number") {
                if (!/^[+-]?(?:0|[1-9]\d*)(?:\.\d+)?$/.test(content || "") || !Number.isFinite(Number(content)))
                    throw new Error(`State line ${index + 1}: number must be a finite decimal.`);
    
                value = Number(content);
            }
            else if (type === "boolean") {
                if (content !== "true" && content !== "false")
                    throw new Error(`State line ${index + 1}: boolean must be true or false.`);
    
                value = content === "true";
            }
            else {
                if (content !== undefined)
                    throw new Error(`State line ${index + 1}: ${type}: takes no value.`);
    
                value = type === "null" ? null : type === "list" ? [] : {};
            }
    
            if (operation === "change" && type !== "number")
                throw new Error(`State line ${index + 1}: change requires number:.`);
    
            const key = {set:"s",append:"a",change:"r"}[operation];
            (operations[key] ||= []).push({path,value});
        }
    
        return operations;
    }
    
    function parseObjectiveCompletionResult(raw = "") {
        const invalid = (reason) => ({ status: "invalid_response", step_id: "", reason });
        const fields = {};
        for (const line of String(raw || "").trim().split(/\r?\n/)) {
            if (!line.trim()) continue;
            const match = /^(status|note): (.+)$/.exec(line.trim());
            if (!match)
                return invalid(`Expected a status or note line; received: ${line}`);
    
            if (Object.hasOwn(fields, match[1]))
                return invalid(`Duplicate objective decision field: ${match[1]}`);
    
            fields[match[1]] = match[2].trim();
        }
    
        if (!["incomplete", "progress", "complete"].includes(fields.status))
            return invalid("Objective decision status must be incomplete, progress, or complete.");
    
        if (fields.status === "progress" && !fields.note)
            return invalid("An objective progress decision requires a factual note.");
    
        return {
            status: fields.status === "complete"
                ? "objective_complete"
                : fields.status === "progress" ? "objective_progress" : "no_change",
            step_id: "",
            reason: fields.status === "incomplete" ? "" : fields.note || "",
        };
    }

    const contract = Object.freeze({operations:parseStateTextOperations,objectiveDecision:parseObjectiveCompletionResult});
    root.EmberAiResponseText = contract;
    if (typeof module === "object" && module.exports) module.exports = contract;
})(typeof self === "object" ? self : globalThis);
