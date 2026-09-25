# Benchmark results

This directory is intentionally version-controlled.

Real benchmark case JSON files are authoritative research evidence: completed answers, failures, timings, prompts, raw responses, model/runtime provenance, and checksums belong in Git with the experiment source that produced them.

The Workbench previously stored these files under `.local/workbench/results/`. A real Workbench launch migrates those legacy JSON files here without overwriting a conflicting result. Logs, credentials, runtime caches, model weights, and machine-local settings remain excluded from Git.
