# Design debt and replacement directions

1. Identity fingerprints are recomputed through disk I/O inside every case ID and mix unrelated global implementation into all cases. Cache an immutable run fingerprint; keep explicit experimental versioning and baseline preservation tests.
2. History compatibility is bolted onto the planner separately from terminal/recovery semantics. Centralize completion classification so exact and historical identities cannot disagree (B03).
3. Most controller tests use the growing research matrix. Separate a tiny fixed plumbing dataset from dedicated full-matrix semantic/preservation regressions; record deadlines against actual workload.
4. Controller and 260 densely packed JavaScript lines mix settings, operation sequencing, discovery, rendering and repair behavior. Split along existing modules/contracts after correctness repairs, without stylistic rewrites that invalidate benchmark identity gratuitously.
5. Case evidence repeats very large state/properties blocks. Keep self-contained exports but consider content-addressed immutable shared artifacts with explicit versioned references and checksum validation. Do not erase old self-contained evidence.
6. Metadata discovery, installed catalog, download intent and historical completion ownership are partly conflated. Separate installed inventory from resumable transfer intent and historical model descriptors.
7. Active and legacy benchmark stacks duplicate scoring/storage/transport contracts. Mark the legacy boundary clearly; migrate deliberately with reproduction checks rather than casually sharing new behavior.
8. Documentation claims drift independently of executable contracts. Generate small count/deadline summaries from validated definitions and attach current test evidence to exact commits.
