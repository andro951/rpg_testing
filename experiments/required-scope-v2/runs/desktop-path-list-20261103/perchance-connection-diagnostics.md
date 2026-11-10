# Perchance connection diagnostics

Later recheck: Isaac requested another attempt after both earlier browsers had stopped. The existing adapter connected successfully and completed both 114-observation cohorts. Audited Perchance results are saved in the dot and path-list run directories; the earlier connection cause remains unknown.

The dot-JSON run launched its research-owned controlled browser at local CDP port 9223, but Playwright `connect_over_cdp` timed out after the WebSocket connected. The path-list run correctly refused to attach to that different profile on port 9223.

The supported `perchance_cdp_port` option was used to launch the path-list provider on an unused port, 23721, with its own controlled profile. Its WebSocket also connected but `connect_over_cdp` timed out after 10 seconds. A later connection-only diagnostic against the same research-owned browser timed out after 30 seconds. Both `/json/version` endpoints report Chrome/153.0.8010.12 and CDP protocol 1.3; responding to this endpoint does not establish that Playwright can obtain a browser context.

The project's temporary headless dependency probe succeeded earlier, but the real controlled adapter uses a visible browser. This difference is an observation, not a proven cause. The existing launch helper suppresses browser stdout/stderr, and the controlled profiles did not expose a Chrome debug log, so the underlying cause remains unknown. No provider generation was completed and no Perchance results were recorded for either current recipe. The browser ownership guard and normal verification behavior were preserved; no unrelated browser was interrupted.

Evidence: `desktop-dot-20261103/desktop-status.json`, `desktop-path-list-20261103/direct-run-status.json`, `desktop-path-list-20261103/perchance-recovery-launch.json` and `desktop-path-list-20261103/perchance-recovery-status.json`.
