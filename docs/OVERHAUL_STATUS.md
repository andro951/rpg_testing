# Browser workbench overhaul — software handoff

The browser UI, controller, discovery, preflight/manual repairs, generic workflows, file-based resume, evidence export, private remote-control support and launchers are implemented and pushed to main.

Code commit `13554b40d1337dc02d92696233b019c2a4886c5c` passed all GitHub Actions jobs in run `35556535167`: 179 unit/smoke tests on Windows, 179 on Linux, and the real Chromium browser workflow. This documentation checkpoint adds no runtime changes.

Start with **Start Demo.vbs**, then **Start Workbench.vbs**. See the root README and WORKBENCH_GUIDE.md. The old worker.local.json/experiment.json instructions apply only to the retained CLI prototype.

Actual GPU inference, the user's LM Studio installation, the Tailscale route and Unity allocation remain untested here. Peak VRAM is unavailable and full GPU residency is unverified. See TEST_REPORT.md for evidence and PLANNED_CHANGES.md for coverage and limits.
