# Benchmark results

This directory is intentionally version-controlled.

Real benchmark case JSON files are authoritative research evidence: completed answers, failures, timings, prompts, raw responses, model/runtime provenance, and checksums belong in Git with the experiment source that produced them.

The Workbench previously stored these files under `.local/workbench/results/`. A real Workbench launch migrates those legacy JSON files here without overwriting a conflicting result. Logs, credentials, runtime caches, model weights, and machine-local settings remain excluded from Git.

The prior study results were archived on October 15, 2026, at `archives/suite-before-activation-2026-10-15/results/`. This active folder now contains only observations from new runs; archived files are preserved unchanged and are not scanned here.
