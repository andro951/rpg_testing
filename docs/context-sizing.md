# Native context sizing (2026-11-15)

This is an allocation-policy correction, not a new self-review methodology.
The original prompt is retained once, with every candidate answer, review and
replacement instruction. Three replacement attempts remain allowed. The review
question, scoring, time limits, sampling, and raw response retention are unchanged.
No expected state or reference answer is used in inference or allocation planning.

## Planning

For the current direct-text suite, preflight counts the assembled step prompt and
system instructions once. The source JSON is already embedded in the prompt and
is not added a second time. A shared 4,096-unit continuation/history reserve is
added. Self-review adds only its literal control messages and conservative framing,
not another original prompt or eight 8,192-token answer allowances. The portable
estimate uses UTF-8 bytes, **not measured tokenizer output**. Older non-direct
workflow estimates retain their original baseline calculation.

The current 240-case suite plans **16,384 tokens for both review off and on**.
This headroom is an allocation, not a maximum answer length. The native model's
maximum still bounds the allocation. Model-facing requests retain `max_tokens=-1`
and context shifting stays disabled. Each complete request is formatted with the
runtime's actual chat template and tokenized before generation. Unexpected long
answers are never cropped or repaired to force them into the allocation.

Offline vocabulary-only measurements on the desktop's Qwen3-VL-8B-Instruct
Q4_K_M tokenizer found a maximum of 3,518 tokens across all 4,320 initial prompts.
A synthetic sizing check retaining four **reference-sized** candidates and every
review/replacement turn peaked at 3,836 tokens. This diagnostic is not model
inference, is not an output guarantee, and does not enter benchmark prompts.
Other model tokenizers can differ. Runtime token checks remain authoritative.

## Overflow and identity

Contexts marked `fixed-case-local-v1` do not expand and restart a workflow after
an overflow. A request that cannot fit, or a continuation that exhausts the
allocation, produces a terminal `context_capacity` outcome for that case. Raw
partial history is preserved; measurement is invalid and intent accuracy is not
reported as a wrong answer. Later cases continue after verified cache cleanup.
A cleanup failure stops the unsafe continuation and leaves later work pending.

New context policy/source provenance produces a separate experiment identity.
Do not reinterpret, relabel, overwrite, or count the previous 262,144-context
load failures as successful inference. Frozen older Unity runs retain their
original source and settings; revised runs require distinct receipts/evidence.

## Cause of the old 262,144 allocation

The pre-existing November 12 review estimator used `base * 2 + 8 * 8192`, then
an outer `estimate * 2 + 8192` rounded to the next power of two. The padding alone
forced at least 262,144 on a model with that native maximum. The new suite's
actual byte estimate was 15,216; the old review transform produced 95,968 and the
outer transform 200,128, rounded to 262,144. Even the archived 21-case suite with
review enabled produced the same allocation. Test counts were not summed.
