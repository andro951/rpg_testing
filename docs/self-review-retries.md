> Current suite update (2026-11-15): the 240-case paired suite now generates both disabled and enabled variants directly, yielding 8,640 workflow conditions per model. The original implementation/protocol below is retained; references to the 21-case default describe its earlier introduction.

# Model self-review retries

`retry_enabled` is a boolean on each workflow variant. Omitted or `false` retains
one answer per executed generate step. `true` enables model self-review on every
executed generate step (including conditional/loop steps). It is independent of
sampling, repetitions, output format and input presentation. No setting is applied
by programmatic correctness, and wrong final answers remain terminal results.

In Workbench, open **Tests → View / edit JSON**. Set `retry_enabled` on a variant,
or use **Add retry-enabled comparison variants** to prepare copies with `__retry`
IDs, identical original prompts/settings and `retry_enabled: true`. The original
variants remain disabled for retries. Restart an already-running Workbench process
before using the new Python workflow. The button only changes the editor; review
and **Validate and save test** explicitly. Existing definition review/rejection
and active-operation guards still apply. No root definitions, case catalog,
frozen run, prompt template or model list were changed by this implementation.
The current default scope remains 21 cases and 372 distinct prompts per model at
one repetition; the illustrative 72 configurations were not used as a catalog.

## Enabled workflow

1. Generate the initial answer under the existing case controls.
2. Send the full original conversation, the answer, and the exact user request:
   `Does this answer look correct? Yes or no.` Reviews are unconstrained text,
   even when answer generation uses an output schema.
3. Accept only a single case-insensitive `yes` or `no`, with surrounding whitespace
   and optionally one final `.` or `!`. Explanations, mixed answers, code fences,
   empty replies, and all other text are recorded as `ambiguous`.
4. On `yes`, stop. On an ambiguous review, stop immediately with the current
   answer **unendorsed** (`ambiguous_review`); do not assume yes, fabricate no,
   retry the reviewer, or spend a replacement. The answer is still graded normally.
5. On `no`, append the review and this feedback to the retained conversation:
   `You judged your previous answer wrong. Provide a new answer to the original request, following its requested output format.`
   Generate a replacement and review it too. Allow three replacements after the
   initial answer, reviewing the third replacement before stopping. At most eight
   calls occur per executed generate step. The last answer is graded even if its
   review says no (`retry_budget_exhausted`).

Every follow-up retains the original messages and prior answers/reviews. The
review helper receives messages and backend controls only: no expected state,
expected patch, identity map, programmatic verdict, or grading diagnostic is
passed into model feedback. Existing intent grading and the independent strict
format metric run after the workflow, on the final answer only.

## Evidence and execution limits

Enabled calls retain messages, original text/reasoning/chunks, backend timings,
usage, requested/applied controls when available, step/iteration, `call_kind`,
`answer_attempt` (zero is initial), schema, and measured `workflow_request_seconds`.
Review calls also retain `review_decision`. Step events record each decision,
outcome, retries used and fixed retry limit. `outputs` contains the final answer;
`calls` preserves the initial answer and every replacement and review. Missing
provider measurements remain unavailable. Perchance keeps its capability-aware
independent repetitions and effective-workflow deduplication; retries are real
workflow differences and cannot collapse into disabled observations.

Stop, transport errors and watchdog timeouts preserve completed calls and any
available partial response through the existing result-store partial/attempt
paths. Failed enabled requests get explicit incomplete/error evidence, including
requests which produced no text. There is no infrastructure reroll added here.
The existing whole-case deadline covers all requests (120 seconds local, 300 for
Perchance); it is not reset for each review/replacement. Automatic local context
planning gives enabled histories extra finite allowance, capped at native context;
this is an estimate, not a measured token count or a promise all histories fit.
Cache verification still evaluates actual per-call cached-token evidence.

## Identity and compatibility

`retry_enabled: true` participates in experiment identity, manual definition
review identity, and Perchance effective-workflow identity. It cannot reuse a
one-answer result, including with an unchanged variant ID. Explicit false and an
omitted setting normalize to the historical disabled identity.

The exact reviewed implementation, provider adapter and v3 evaluator source hashes
are whitelisted in `workbench/operational-source-compatibility.json`. This is an
additive workflow extension with unchanged disabled generation and unchanged
post-response grading. Raw source hashes remain visible, including the evaluator's
`implementation_fingerprint` and Perchance's saved `raw_adapter_hash`. Only these
exact hashes preserve prior pins; unknown future changes stay distinct/stale.
No saved evidence was rewritten or rescored, and retired evaluator versions remain
blocked. The retry helper is included in the implementation fingerprint.

## Verification

`tests/test_self_review.py` uses deterministic fake responses, never model-quality
or GPU evidence. It covers disabled/omitted behavior, immediate yes, no then yes,
all three replacements with final review, ambiguity, wrong answers endorsed by the
model, Stop, partial streams, transport/deadline errors, constrained answers with
unconstrained reviews, local and Perchance behavior, strict/intent independence,
finite context allocation, idempotent UI pairing without a browser, workflow
identity separation, immutable result saving and repeated resume.

The frozen `tests/fixtures/self_review_disabled_workflows.txt` runner from commit
`f78bdf51` verifies the disabled runner on all
372 current prompts: requests, responses, outputs, scores and all non-timing
result fields agree. Existing case definitions and saved evidence are untouched.
The test suite requires the repository environment, `.venv-workbench/Scripts/python`;
system Python on the development machine lacks `jsonschema`. On Windows, run
with `PYTHONUTF8=1`: an existing frozen-export test uses default `read_text()`
decoding for UTF-8 archives. Its failure under the CP1252 default reproduces with
the pre-change runner and passes with UTF-8 mode; no archive or old test was edited.

No live inference or broad sweep is part of this change. A tiny explicitly selected
live local check would still be useful to observe actual model compliance with the
yes/no question and context/latency growth. It would not establish benchmark
accuracy or provider capability support.

Verified on the implementation workstation: with `PYTHONUTF8=1`,
`.venv-workbench/Scripts/python -m unittest discover -s tests -v` completed
1,116 tests in 1454.590 seconds: OK, with one existing skip because the filesystem
has no distinct Windows 8.3 alias. The focused runner/identity/formatting/Perchance/
HTTP transport set completed 136 tests in 60.737 seconds: OK. `node --check
workbench/web/app.js` and `git diff --cached --check` passed. These are unit and
simulated workflow checks, not live inference.
