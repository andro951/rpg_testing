# Workbench overhaul — in progress

Implementation authorized by Isaac on 2026-09-20. The planning-only hold is lifted.

Published checkpoints include scheduling, flat result files, discovery and the generic workflow/scoring interpreter. New controller/backends and their tests are being integrated locally before publication.

Local full-suite check after combining the existing repository with new code: **121 tests passed**, including 50 original tests and 71 workbench tests. Includes real localhost HTTP/SSE with a stub, simulated complete runs/resume/deletion, and missing-completed-model preflight.

Actual model inference, Windows hardware and Unity access have not been exercised here. CI now runs on Windows and Linux. Further checkpoints will add browser controls and final validation. Do not treat this in-progress checkpoint as a finished UI release.
