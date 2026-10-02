# RPG Testing repository review

Reviewed September 30, 2026, at commit b5bc3fdbd56dcec43a51f1b6f611ceb00e77fe3d on main.
Local checkout: D:\Program Files\JS Dev\rpg_testing.
Repository: https://github.com/andro951/rpg_testing

The repository is a state-update research harness intended to inform Ember Adventures. Its active application is the native llama.cpp web workbench; the old rpgbench CLI is retained for historical reproduction. The research roadmap deliberately starts with general structured-state reasoning, then retrieval, longitudinal no-op/commitment timing, memory and eventual RPG use.

Scope: all 1,715 tracked files, including active and historical code, launchers, tests/CI, examples, fixture definitions, documentation and tracked evidence. There are 59 enabled definitions, 387 configured cases per model, and 1,552 checksummed real-result records. Automated inventory is in evidence/inventory.json. Result contents were validated structurally and checksummed; this review did not independently reproduce their real model answers.

Six confirmed defects are documented. Highest priority findings: strict chat-template detection is broken; seed diagnostics lack a total watchdog; timeout-only compatibility can suppress unfinished recovery. Details and repair tests are in 03_bugs.md. Browser checks also expose timing/race weaknesses. Existing result preservation passed against the pinned baseline: 174 old cases per model retained, 213 additive cases, no old cases invalidated.

Application source, test definitions and stored benchmark results were not edited. Added this audit directory and an ignored .local/audit-venv with pinned jsonschema and Playwright for validation. No commits, pushes, model/runtime downloads, real inference, private remote binding or Unity jobs were performed.

Read 01 for behavior, 02 for navigation, 03/04 for findings, 07 for repair order and 08 for acceptance criteria. 09 records actual checks; 10 explains coverage and limits.
