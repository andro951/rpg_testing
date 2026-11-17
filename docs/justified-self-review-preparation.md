# Justified self-review comparison: prepared, not activated

## Owner decision, November 16, 2026

Finish Perchance and ALL local desktop models of the current run unchanged.
Unity completion is not an activation prerequisite. Preserve/archive original
results, exact prompts and source, raw calls, controls, model identities, grading,
case IDs and sync receipts before activating the new protocol. Never rewrite or
rescore historical evidence. No running checkout should be changed mid-run.

The revised review justifies BOTH verdicts. YES explains why the answer is good;
NO explains what is right and wrong (explicitly saying nothing is right when
appropriate), and the next answer uses that feedback. Maximum three replacements
and the final review remain unchanged; no reference/evaluator feedback is given.

## Prepared implementation

Opt in with `retry_enabled: true` and `retry_protocol: justified-v2` in each
new comparison variant. Omission retains `yes-no-v1` behavior. The new field is
part of native case identity and Perchance effective workflow identity. All
review/replacement calls retain full conversation and raw explanation. The model
must start with a standalone Yes/No line followed by nonempty natural-language
justification. Missing/malformed verdict or missing justification is ambiguous,
not acceptance. The parser does not judge whether the justification is correct;
objective grading still independently grades the final answer.

Do not deploy this preparation to an active worker. Do not alias the workflow/provider fingerprint. An exact evaluator-only mapping
was reviewed against pinned study source 7a45024e31cac48ce0668225946208c477992e50:
only runner import/protocol routing changed among all evaluator sources.
Use this pinned study branch, NOT main, whose suite/context controls differ.
Current suite definitions and archived results are untouched by this branch.

## Comparison and rollout after verified desktop completion

1. Read fresh status proving Perchance and every configured desktop local model
   finished; resolve interrupted/pending entries rather than assuming completion.
2. Preserve the old run's immutable evidence plus manifest and provenance. Existing
   Unity old-protocol jobs can continue in their pinned checkout/output location.
3. Build a separate comparison definition selecting ONLY retry-enabled conditions
   (240 cases x three input views x six output formats = 4,320 per model), with
   justified-v2 and separate run/coverage identity. Do not rerun unchanged off cases.
4. Run across all requested models via supported controller/sync flow. Preserve
   provider eligibility, locks, resources and no-duplicate jobs. A busy Unity GPU
   queues new work without changing the still-running old-protocol job.
5. Compare matched case/input/output/model/control/repetition records from old and
   new runs; report missing pairs separately. Retain old no-retry reference results,
   but never clone them as new observations. Compare exact state correctness,
   formatting, review outcomes, revisions/calls/tokens/time, and model acceptance
   versus independent correctness. Do not merge yes/no and justified conditions.

This branch is offline preparation only, not evidence that any model ran the new
protocol. Full regression and activation gates must be resolved before deployment.

## Pinned candidate validation

Validated code commit: 741cc441, based on active study source
7a45024e31cac48ce0668225946208c477992e50. Do not use the earlier main-based
preparation branch for this comparison.

- `python -m unittest discover -s tests -v`: 1,204 tests, OK, one skip,
  906.131 seconds. These are offline/unit/simulated workflow checks, not inference.
- Focused review/comparison checks: 33 tests passed.
- Exact active suite inspection selects 4,320 retry-enabled variants from 1,440
  definitions, with all no-retry variants excluded.
- Independent read-only source review confirmed evaluator-only alias points to
  pinned grading fingerprint c71db6accfac0cfb6f5f40d3e42b541670f89d233b471da3ee5fddd4ed56e5ce;
  no old workflow/provider identity is aliased, and unknown source changes remain stale.
- No active desktop/Unity checkout, results, jobs or model settings were changed.
- No publication, deployment or new model inference performed. Activation still
  requires fresh completion evidence for Perchance and all desktop models, archival
  of original run evidence, separate comparison scope, and preserved worker controls.
