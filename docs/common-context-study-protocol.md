# Optional frozen common-context studies

This feature does not choose a context limit or select a study. No active
`study_protocol.json` is supplied. Normal automatic allocation remains the default.
Establish the usable common limit through authorized capacity qualification before
selecting a protocol or starting benchmark inference.

## Selection and schema

An explicitly supplied, regular `study_protocol.json` at the checkout root selects
one study-wide native allocation. Unknown fields, duplicate JSON keys, invalid
limits, missing qualification references and symlinks are rejected. The schema is:

- `schema_version`: integer `1`.
- `study_id`: a stable ID using the existing repository ID syntax.
- `context`: exactly `policy: "common-native-context-v1"`, integer `tokens`, and
  `capacity_policy: "fixed-case-local-v1"`.
- `qualification_evidence`: a nonempty list of unique `reference` strings and
  their lowercase, 64-character `sha256` values. These are frozen provenance
  references, not automatic proof of sufficient GPU capacity. The loader does
  not follow URLs or open arbitrary referenced files.

The token value must be between 512 and 2,147,483,647 and must not exceed any
participating native model's real metadata maximum. These syntactic bounds do
not certify a usable GPU allocation. Do not modify the protocol in a running
checkout. Use a distinct frozen run/checkout when changing it.

## Native execution and identity

Preflight uses the exact selected value in the target identity and every native
model plan. It does not apply the automatic floor, round the value, enlarge it
for longer prompts, clamp it per model, or overwrite native maximum metadata.
Byte estimates remain diagnostic only. Actual runtime properties must positively
verify precisely the requested context before a study model is accepted as loaded.
Missing, zero, malformed or different runtime context evidence blocks the load.

The canonical protocol and its digest are included in native experiment targets
and coverage snapshots. Different limits or qualification provenance cannot reuse
native observations under the old identity. With no protocol file, existing
automatic target shape and allocation behavior are preserved. Implementation
fingerprints still record source changes; this feature adds no compatibility alias.

Unity bundles include the exact protocol file, its source hash and the same frozen
coverage scope. Workers verify these before starting their Controller. A changed
or omitted protocol cannot silently become an automatic-allocation job.

## What does not change

Initial prompts, scoring, cumulative self-review history, three permitted
replacement attempts, sampling and watchdogs are unchanged. Expected answers are
not consulted to choose the allocation. Native output remains uncapped
(`max_tokens=-1`), context shifting remains disabled and requests are tokenized
with the actual model/template. An input or continuation that cannot fit receives
the existing terminal, measurement-invalid, case-local context-capacity outcome.
There is no cropping, hidden history reduction, larger-context retry or semantic
failure claim. Later cases proceed only after cache cleanup succeeds.

Before admitting authentic game states or large databases, check their actual
requests using every relevant tokenizer against the qualified common limit.
An infeasible request must remain visible; the protocol does not authorize
silently trimming, replacing or simplifying a state to fit.

## Perchance

A native common context is **not** a supported Perchance control. Its requested
value and study provenance are recorded separately in plan/alias/target evidence.
Applied tokens and the provider's context limit remain `null`, allocation control
is marked unsupported and verification unknown. The protocol is never added to
model prompts, provider configuration or effective workflow identity. Changing
only this unsupported request does not create another independent remote trial;
ordinary repetitions and genuinely changed prompts/states/review workflows remain
independent. Existing immutable remote observations are not rewritten to claim a
new applied context. Run plans retain the requested provenance when observations
are reused.

Snapshots explicitly record `evidence_verification: references-only-unverified`. Evidence references and asserted hashes are frozen provenance, not independently verified qualification artifacts.
