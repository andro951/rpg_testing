# Source map and interactions

| Area | Files | Interactions |
|---|---|---|
| Startup | Start Workbench.vbs, Start Demo.vbs, Start Workbench.command, bootstrap.pyw, launch_workbench.py | Dependency setup -> supervisor -> locked child -> server or batch controller |
| Control | workbench/server.py, controller.py, locking.py, restarts.py | Authenticated routes -> exclusive edits/background operations -> snapshots/progress -> source restart |
| UI | workbench/web/index.html, app.js, style.css | Pairing/session storage -> fetch API -> state poll -> DOM text rendering and dialogs |
| Discovery | hub.py, downloads.py, model_manager.py, inventory.py, native_dialog.py | Explicit model root -> scan/catalog -> metadata selection -> verified transfer -> assign/rescan |
| Native runtime | runtimes.py, native.py, backends.py | Official bundle -> safe extraction -> runtime capabilities -> owned loopback process -> SSE transport |
| Domain | domain.py, planning.py, preflight.py, execution_policy.py | Validated definitions/catalog -> case identity -> pending work -> preparation/live readiness -> policy |
| Execution | scheduler.py, workflows.py, presentation.py, seedcheck.py, telemetry.py | Primary/recovery load -> diagnostic -> bounded workflow -> final score -> result/log flush |
| Evidence | scoring.py, analysis.py, gitops.py | Patch apply/exact state -> checksummed authoritative file -> descriptive summary -> optional narrow publication |
| Simulation | demo_native.py, backends.DemoBackend | Synthetic responses, placement and seed diagnostics; never real model measurements |
| Cluster | unity.py, launch_workbench.py | Generated reviewed Slurm job -> batch controller -> signal forwarding |
| Historical | rpgbench/*.py, run_worker.py, experiment.json, fixtures/, worker*.example.json | Fixed original research pipelines, append-only attempts, mock/native/LM Studio adapters |
| Quality | tests/*.py, tests/helpers/native_stub.py, scripts/audit_case_preservation.py, .github/workflows/tests.yml | Unit fixtures, local HTTP/SSE/process tests, browser workflows, pinned identity regression |
| Requirements | README.md, docs/*.md, AGENTS.md, results/README.md | Active operations, historical reports and separate research roadmap |

Canonical storage: root models.json (ignored catalog), test_specs/*.json (tracked experiment definitions), results/<model>/<case>.json (tracked real evidence), .local/workbench/{settings.json,artifacts.json,logs,preflight_reports,control.key}, .local/demo (isolated simulation), .local/runtime and runtime-cache. External model files/partials reside only under the selected model_root.

Main integration edges to preserve: selected/full case identity equality; source-only prompt vs oracle scorer; request cancellation vs process shutdown; load placement vs execution class; recorded actual context vs planning recipe; terminal wrong answer vs retryable infrastructure; source restart vs targeted Run intent; current catalog vs historical evidence.

Inventory has one record per tracked file with byte size, line count and SHA-256. See evidence/inventory.json. The 1,620 tracked JSON files are primarily the 1,552 result records, 59 enabled definitions, optional examples and historical/config fixtures. No application files were discovered outside the tracked scope that were needed to understand the cloned program. No nested AGENTS.md files were present.
