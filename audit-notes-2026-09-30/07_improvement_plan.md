# Ordered improvement plan

1. Freeze a copy of current evidence and preserve the baseline report. Repairs in fingerprint-bearing files intentionally change new case IDs; decide/version comparison compatibility before running new benchmarks. Never rewrite previous raw answers to make them match corrected code.
2. Fix B01/B04 together with exact template-role/body tests and a simulated apply-template rejection test. This is prerequisite to measuring strict-template models fairly.
3. Fix B02 with a bounded seed diagnostic and cleanup/advance test against continuous SSE; verify diagnostic cancellation, case timeout and load timeout stay distinct.
4. Fix B03 through a shared historical/exact completion classifier. Add tests across watchdog edits and fallback deletion/completion. Rerun case preservation; retain old result files.
5. Fix B06 with an explicit no-rebase fast-forward pull and inherited-config regressions. Stabilize B05 and R01: wait for operation/report completion, use fixed plumbing subsets, retain one full-suite check and calibrate selftest/browser deadlines on Windows.
6. Strengthen editor source/result/check contracts (R03) and unify graphical/batch restart bounds (R04). Preserve optional narratives and targeted selection.
7. Validate runtime at load against planned identity and add optional model content verification (R02); distinguish retained publisher hashes from bytes verified on this host.
8. Profile preflight/planner/export at current and larger evidence sizes before addressing R05/R07. Use indexed history and run-scoped fingerprints first.
9. Repair resumable transfer/scan intent and mount recovery (R06), then control-plane sequencing/timeouts (R08), then draft/token/pagination UX (R10).
10. Update current guide/counts and add an exact-commit validation report (R09). Keep the research roadmap separate from implemented behaviors.
11. Perform authorized environment smokes: one small known GGUF on the actual GPU/runtime, full-GPU qualification, cache counters, timeout cancellation and resume; then Tailscale and Unity separately. These checks require the intended hardware/storage setup and must not be replaced by demo results.

For each repair, run the required unittest suite, relevant native/browser regressions and mock/demo resume, and recheck source fingerprint/result compatibility. No source repairs were made in this review.
