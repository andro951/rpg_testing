# Development rules

- Treat root `models.json` as machine-local and Git-ignored. When present, keep it a models-only JSON array. Use required_vram_gb, not min_vram_gb. Memory budgets are estimates until measured under a recorded load configuration.
- Do not put fixtures' expected states or example patches into model prompts.
- A wrong model answer is a completed benchmark result, not an infrastructure retry. Never retry selectively to inflate accuracy.
- Preserve immutable raw responses, exact experiment settings, model hashes and error records. Equivalent patches are graded by final state, not textual patch equality.
- Run `python -m unittest discover -s tests -v` after each code change. Add unit/smoke tests for new behavior, including failures. Repeat the mock run to check resume.
- No real private records, credentials or model weights in this public repository. Synthetic benchmark prompts and outputs under `results/` are intentional research evidence and are version-controlled, including mature fictional benchmark content. Never stage arbitrary user directories or force-push results.
- Do not call mocked tests real inference. Do not report unmeasured timing, memory or cache hits as zero.
- Keep controlled caching, verification/repair and narrative generation marked planned until implemented AND tested.

## Perchance and provider capability standing rule

- Follow `docs/perchance-capability-policy.md` when planning, implementing, testing, or analyzing the Perchance Text Generator adapter. This is an explicit user requirement, not an optional optimization.
- When a provider cannot apply or verify an experimental control, run ONE representative baseline per distinct effective prompt/workflow/condition instead of running each unsupported setting value or seed/repetition. Record requested controls, actual applied controls, unsupported/unverified capabilities, and every collapsed case's reference to that single observation. Never fabricate support, silently ignore settings, clone scores as independent results, or count collapsed cases as additional samples. Preserve genuinely different prompts, states, representations, supported controls, workflow steps, scoring requirements, and deadlines. Feature-only measurements that cannot be performed are not applicable, never invented baseline successes. Fresh trials beyond that single baseline require explicit user direction.
- Apply this to cache modes and verification, all sampling knobs, seed/reproducibility repetitions, constrained output, context/token controls, execution placement and provider configuration, and any future knob. Unknown capability is unverified until demonstrated. Provider defaults are unknown unless observed, not the requested values. Unavailable measurements remain null/not applicable, never zero.
- Perchance is fixed to the 8 GB scheduling tier with an explicit exclusion of larger tiers; do not inherit the local-model one-tier-up exception. Its inference is a remote service, not measured local 8 GB GPU inference. Preserve existing local-model case identities and raw evidence when adding it. The adapter and capability-aware scheduling are implemented with unit and simulated browser coverage. Real service inference and Linux/Unity deployment remain unverified; do not treat mocks as live study observations.
