# Perchance capability policy

Standing user requirement recorded on October 1, 2026. This policy governs the Perchance Text Generator adapter, its scheduler, results, exports, UI, and study analysis. The adapter implements grouping and explicit unavailable capabilities. One harmless live Windows text request through normal browser/CDP succeeded on October 8, 2026; full benchmark execution and unavailable controls remain unverified. The connectivity evidence is separate from scored study results.

October 8 setup rule: before the other preflight checks, determine whether Perchance is eligible and pending, then verify its dependency and local browser launch. Offer installation through a Yes/No popup if setup is missing or broken. Yes installs and rechecks. No is recorded for one upcoming matching run and skips Perchance without writing a benchmark observation or making pending work complete. Ask again on the next run if setup is still needed. Keep consent and dependency setup outside provider identity; scope exclusions and completed observations must not cause unnecessary installation.

## One observation for one effective condition

If Perchance cannot actually apply an experimental control, run one representative baseline for the distinct effective prompt/workflow/condition. Do not execute nominally different temperature, caching, seed, or other settings when they would send the same effective experiment to the service. Do not repeat that baseline just because the provider is stochastic. Additional independent trials require explicit user direction.

Treat unsupported and unverified controls as unavailable for controlled comparisons. Accepting an option object, forwarding a field, or receiving different answers does not establish that a control works. Distinguish requested, forwarded, applied, and behaviorally verified settings. An unknown provider default must remain unknown; in particular, do not label an ignored request for temperature zero as an actual temperature-zero experiment.

Persist the collapse decision before execution so resume uses the same representative observation. Choose the representative deterministically before seeing any response. Never choose whichever response scores best. A wrong answer or timeout remains that observation's terminal result; it is not grounds to reroll another collapsed case. Existing infrastructure-attempt policy must preserve all failed attempts and must not selectively retry semantic failures. Explicit restart is separate, recorded user-directed work.

## Situations requiring capability treatment

| Situation | Required treatment |
| --- | --- |
| Cache on/off/default, clear/reset, warm-up, prefix/slot reuse, min_cached_tokens, cache hit verification | If control or verification is unavailable, run one default-service baseline for each distinct workload. Cache claims and cache-specific measurements are not applicable. A cache-only success criterion cannot pass from an ordinary response. Keep workload calls that are needed to exercise the actual workflow. |
| temperature, top_p, top_k, min_p, repeat_penalty | Collapse variants differing only in unavailable knobs. Record the requested values and service defaults separately. Apply the same rule to future frequency/presence penalties or other sampling options if added. |
| seed, repetition-derived seeds, same-seed/different-seed checks, ordinary repetitions of the same effective condition | If seed control is unavailable/unverified, collapse nominal seed/repetition runs to one observation for each otherwise distinct supported condition. Do not send hidden seed probes or run repeated default calls pretending to establish determinism. Reproducibility is not applicable/unverified. |
| Native JSON/schema/grammar constraints, enum/boolean/string output modes | Do not claim constrained decoding when unavailable. An ordinary-text baseline may retain the exact requested output instructions and be parsed/scored afterward, with the decoding constraint explicitly unavailable. If a feature-only test cannot be meaningfully performed, record it as not applicable. Changing output instructions or schemas may change the effective task and must not be blindly deduplicated. |
| Context allocation, native context limits, token/output budgets or context expansion | Local allocation requests cannot stand in for remote settings. Collapse differences that have no applied effect. Retain different actual source/prompt lengths, service truncation, failures, and client-imposed deadlines. Future caps follow this rule; current active specs prohibit output/context caps. |
| GPU layers, CPU offload, KV placement, quantization, GGUF artifacts, local VRAM tier | These are not applied remote-inference controls. Do not run Perchance again across local-model placement or hardware sweeps, or fabricate artifacts/GPU-fit evidence. Its assigned 8 GB tier is a scheduling restriction and must exclude larger tiers, including the local-model 11/12 GB one-tier-up exceptions. |
| Provider model/version choice, remote sessions, role-message handling | A model/version/session selector counts as a distinct condition only when its effect is supported/observed. Retain exact serialized instructions and any supported message-role or conversation differences. A renamed model entry or reset window alone is not a new independent sample. Provider identity changes must be recorded and must not be pooled silently. |
| startWith, hideStartWith, stopSequences, stop/cancel behavior, additional plugin options | Verify each option separately; the existing worker forwards the first three, but forwarding alone is not proof of applied behavior. Preserve distinct applied prefixes/stops and actual returned text. Unsupported option sweeps collapse. Retain timeout/cancellation outcomes and partial responses. |
| Unknown or newly added control | Add it to the capability ledger and treat it as unverified until demonstrated. Never assume support because another backend supports the same field. |
| Missing token counts, cache counters, first-token timestamps, prompt-processing/generation timing, remote memory/layer metrics | Record null/unavailable/not applicable. End-to-end timing can still be measured and labeled as service/browser/network latency. Missing measurements are not zero and do not warrant duplicate runs to fill a matrix. |

## What stays distinct

Preserve actual differences in source state/new information, prompt wording, representation (raw JSON/indexed objects/full paths), source length, supported applied controls, output instructions, conversation history, step ordering, branching, verification/repair/narration logic, scoring/oracle requirements, and provider identity. Record client deadlines as execution metadata, not separate conditions. Instructions referring to a control can alter the prompt even when the corresponding API knob is unavailable; those are prompt experiments, not verified knob experiments.

One baseline means one workflow execution, not necessarily one model call. A meaningful multi-step workflow can require several calls, branches, or loop iterations. Unsupported-control deduplication must not remove those steps or turn a repair/narration workflow into a different task.

If identical inference evidence can legitimately serve more than one scoring view, keep each requested oracle and derived score clearly attributed to the same immutable observation. Different scoring requirements must not be lost, and reused evidence must never count as multiple independent trials.

## Evidence and reporting contract

The implementation must persist:

- A versioned capability snapshot with supported-and-verified, unsupported, and unverified states; evidence/source/date for the classifications; known provider/browser/worker/adapter identity and unknown fields explicitly marked.
- The requested test/variant IDs, repetitions, settings, constraints, and workflow, without editing original specs.
- The exact effective serialized instruction(s), verified applied options, supported execution conditions, client deadline, and the versioned equivalence-key policy.
- One representative observation ID per equivalence group, with all original requested cases mapped to it and the precise unavailable dimensions causing collapse. A plan can be deduplicated before it runs; a collapsed case is fulfilled only once its referenced observation is terminal.
- Separate applicability for task accuracy and feature-specific claims. A text baseline can have valid task accuracy while cache-control or constrained-decoding claims remain not applicable.
- Immutable original response/partial stream, finish/error/timeout details, scoring, available timings, and prior infrastructure attempts. Avoid response trimming or cleanup in raw evidence.
- Requested case count, independent executed observation count, collapsed aliases, unsupported feature-only cases, pending work, timeouts, and errors as separate counts.

Collapsed aliases are not missing results, model failures, successful controlled-feature trials, or extra observations. They must be visible in result tables and exports with a link to their representative. Charts must not clone that representative's score or latency into every unsupported setting cell. Accuracy denominators, uncertainty calculations, matched comparisons, and coverage counts must use actual independent applicable observations. Unsupported-setting effects cannot be estimated. A single observation cannot supply a variance estimate. Preserve remote versus local execution provenance and differences in applied controls when comparing providers.

## Current source findings

The active suite has 58 enabled test definitions, 175 enabled variants and 357 requested cases per local model. Ninety-one variants have three repetitions. If Perchance's seed control is unavailable, reducing repetitions to one leaves at most 175 observations before any further identical-effective-experiment grouping. This is a planning bound, not a completed Perchance run or a claim that every variant is compatible.

Every active variant currently uses cache=default and text output. Explicit cache-on/off variants exist in examples/cached_questions.json. Other examples include constrained boolean/string output. The current validator recognizes temperature, top_p, top_k, min_p, seed, and repeat_penalty; the workflow supplies default sampling values and derives a new seed per repetition.

The existing EmberAdventures worker sends instruction, startWith, hideStartWith, stopSequences, and streaming callbacks. It does not forward the tester's sampling knobs, seeds, cache controls, or constrained-output schemas. It reads token-count/context metadata, but that is not a remote context-allocation control. Under this policy, capabilities missing from that adapter are unavailable until the copied adapter implements and verifies them. This does not assert that the underlying service can never support them.

## Required implementation tests

- Unsupported temperature/cache/seed/repetition sweeps produce one actual baseline; the collapse mapping records all requested cases.
- Supported applied controls, different prompts/states/representations, distinct output instructions/scoring requirements, and workflow structures remain correctly distinguished; deadline changes do not split observations.
- Multi-step workflows keep their required calls even when unsupported dimensions collapse whole-case variants.
- Resume does not repeat terminal representative observations or turn collapsed aliases into fresh work. Wrong answers and timeouts do not trigger rerolls.
- Unknown controls/defaults are recorded as unverified/unknown. Merely accepted or forwarded fields do not become verified capabilities.
- Cache-only/schema-only qualification cannot be reported as passed from an unconstrained default baseline; raw task accuracy remains separately applicable where meaningful.
- Reports and exports distinguish requested coverage from independent observations and never count aliases multiple times. Missing measurements stay unavailable.
- Old local-model case IDs, raw results, scoring behavior and valid supported repetitions remain unchanged; the Perchance 8 GB rule rejects larger tiers.

These acceptance requirements are covered in the integration preparation and review document. The user subsequently authorized implementation and testing. Real benchmark evidence must remain separate from simulated transport tests.


Timeout is an execution watchdog, not an experimental control or identity dimension. Changing it changes only the allowed duration of pending executions, never the observation ID or terminal completion state. Local test definitions use 120 seconds. Perchance uses a fixed 300-second whole-workflow deadline in every entry point; each requested local deadline remains recorded in alias metadata. Overview Run all remaining tests includes Perchance last on an actual 8 GB worker, after native GPU and recovery passes. Larger workers, simulated demo runs and targeted local/all-local selections exclude this automatic phase. Preflight counts and validates both phases; completed local cases do not block pending Perchance work. Cancellation or stop-after-model prevents starting the final phase. Provider baseline deduplication and terminal resume rules still apply.
