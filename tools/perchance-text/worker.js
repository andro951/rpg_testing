"use strict";

//#region Owned text worker
globalThis.RpgPerchanceText = {
    Version: "rpg-perchance-worker-v2",
    Active: null,
    Plugin: () => {
        const root = globalThis.root;
        return root?.aiTextPlugin || root?.$moduleSpace?.["ai-text-plugin"] || globalThis.aiTextPlugin;
    },
    Environment: () => ({
        version: globalThis.RpgPerchanceText.Version,
        ready: typeof globalThis.RpgPerchanceText.Plugin() === "function",
        frameUrl: location.href,
        userAgent: navigator.userAgent,
        remoteModel: null,
        appliedSampling: null,
        seedReproducibility: "unverified",
        cacheControl: null
    }),
    Snapshot: id => {
        const active = globalThis.RpgPerchanceText.Active;
        if (!active || active.id !== id)
            return { id, state: "absent" };

        return { id, state: active.state, text: active.text, chunks: active.chunks,
            rawResult: active.rawResult, stopReason: active.stopReason, error: active.error,
            forwardedSampling: active.forwardedSampling,
            elapsedMs: performance.now() - active.started, firstVisibleMs: active.firstVisibleMs };
    },
    Start: job => {
        const worker = globalThis.RpgPerchanceText;
        if (worker.Active?.state === "running")
            throw new Error("A text job is already running");

        if (typeof job.id !== "string" || typeof job.instruction !== "string" || !job.instruction.trim())
            throw new Error("A job ID and instruction are required");

        if (job.seed !== undefined && (!Number.isInteger(job.seed) || job.seed < 0 || job.seed > 0xFFFFFFFF))
            throw new Error("Seed must be an unsigned 32-bit integer");

        const plugin = worker.Plugin();
        if (typeof plugin !== "function")
            throw new Error("Perchance text plugin is unavailable");

        const active = { id: job.id, state: "running", text: "", chunks: [], rawResult: null,
            stopReason: null, error: null, started: performance.now(), firstVisibleMs: null, request: null,
            forwardedSampling: job.seed === undefined ? null : { seed: job.seed } };
        worker.Active = active;
        const options = { instruction: job.instruction, startWith: "", hideStartWith: true,
            stopSequences: [], onChunk: data => {
                if (worker.Active !== active || active.state !== "running")
                    return;

                const chunk = typeof data === "string" ? data : data?.textChunk ?? data?.chunk ?? data?.delta ?? data?.text ?? "";
                active.chunks.push({ text: String(chunk), isFromStartWith: !!data?.isFromStartWith,
                    elapsedMs: performance.now() - active.started });
                if (!data?.isFromStartWith) {
                    active.text += String(chunk);
                    if (chunk && active.firstVisibleMs === null)
                        active.firstVisibleMs = performance.now() - active.started;
                }
            } };
        if (job.seed !== undefined)
            options.seed = job.seed;

        const request = plugin(options);
        active.request = request;
        Promise.resolve(request).then(data => {
            if (worker.Active !== active || active.state !== "running")
                return;

            const raw = typeof data === "string" ? { generatedText: data } : data;
            //Retain serializable provider evidence without trimming its output.
            active.rawResult = JSON.parse(JSON.stringify(raw, (key, value) => typeof value === "function" ? undefined : value));
            const finalText = typeof data === "string" ? data : data?.generatedText ?? data?.text ?? data?.response ?? data?.output;
            if (typeof finalText === "string")
                active.text = finalText;

            active.stopReason = data?.stopReason ?? null;
            active.state = active.stopReason === "error" ? "error" : "completed";
            if (active.state === "error")
                active.error = "Perchance returned stopReason=error";
        }).catch(error => {
            if (worker.Active !== active || active.state !== "running")
                return;

            active.error = String(error?.stack || error);
            active.state = "error";
        });
        return worker.Snapshot(job.id);
    },
    Cancel: id => {
        const worker = globalThis.RpgPerchanceText;
        const active = worker.Active;
        if (!active || active.id !== id)
            return false;

        active.state = "cancelled";
        if (typeof active.request?.stop === "function")
            active.request.stop();

        return true;
    }
};
//#endregion
