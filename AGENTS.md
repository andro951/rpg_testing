# Development rules

- Treat root `models.json` as machine-local and Git-ignored. When present, keep it a models-only JSON array. Use required_vram_gb, not min_vram_gb. Memory budgets are estimates until measured under a recorded load configuration.
- Do not put fixtures' expected states or example patches into model prompts.
- A wrong model answer is a completed benchmark result, not an infrastructure retry. Never retry selectively to inflate accuracy.
- Preserve immutable raw responses, exact experiment settings, model hashes and error records. Equivalent patches are graded by final state, not textual patch equality.
- Run `python -m unittest discover -s tests -v` after each code change. Add unit/smoke tests for new behavior, including failures. Repeat the mock run to check resume.
- No real private records, credentials, model weights or explicit content in this public repository. Never stage arbitrary user directories or force-push results.
- Do not call mocked tests real inference. Do not report unmeasured timing, memory or cache hits as zero.
- Keep controlled caching, verification/repair and narrative generation marked planned until implemented AND tested.
