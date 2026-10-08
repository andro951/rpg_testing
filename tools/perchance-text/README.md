# RPG Perchance text worker

Text-only adaptation of the local EmberAdventures tools/perchance-ai-text-harness browser-page-runner.mjs and perchance-browser-worker-bottom.html. The original harness is retained unchanged. This copy removes image generation, playtesting, file queues and retries; preserves untrimmed responses; exposes independent job snapshots/cancellation; and uses its own RpgPerchanceText namespace.

The Workbench launches a normal visible browser independently, attaches Playwright through loopback CDP, locates the hosted Perchance output iframe, and injects worker.js in memory. `workbench/perchance_connection.py` supplies this lifecycle to both standalone Perchance runs and the final Perchance phase of Run all. It inherits the unchanged request serializer from `perchance.py`; it does not use Playwright's `launch_persistent_context` in the Workbench path. No saved Perchance page is edited. The existing bootstrap page can still import its own image plugin; this adapter never invokes it. For a separate hosted text-only page, use this left pane:

```text
aiTextPlugin = {import:ai-text-plugin}

$meta
  header = minimal
  title = RPG Text Worker
```

The bottom pane only needs a JavaScript-created readiness label; the adapter injects worker.js when it connects. A dedicated page is optional and must be saved by its owner before configuring its URL.

The dedicated profile is `.local/workbench/perchance-controlled-profile`, with CDP bound to `127.0.0.1` on port **9223** by default. EmberAdventures' profile and port 9222 are separate. Worker setup exposes the local connection port. Close the RPG-controlled browser before changing its browser executable or port. An occupied port without this profile's ownership marker is rejected. Verification and batch completion disconnect Playwright while leaving the normal browser, cookies and hosted page open for the next request/run. Production windows are visible on the host; the old headless preference is retained only for settings compatibility and is no longer offered/applied to this transport.

Browser startup is outside benchmark timing. Worker text chunks, raw serializable plugin results, unknown stop/model settings, and first-visible-text timing are evidence; they are not native token timing or verified sampler/cache controls. Timeout/cancel closes the active page before another case. Every workflow shares one 300-second client deadline. There are no hidden text requests or retries. Dependency preflight probes normal browser/CDP locally using `about:blank`; connection verification checks plugin availability and explicitly does not claim generation works.

On October 8, 2026, one user-authorized harmless live request using this normal browser/CDP transport returned text in **4.410 seconds**. Complete request, untrimmed response, chunks and provider result are in `diagnostics/2026-10-08-cdp-response.json`. This is connectivity evidence, not a scored benchmark observation or a latency guarantee. The prior launch-persistent-context check stalled with no output; comparison artifacts establish the working transport, not the exact underlying service restriction. The inference adapter/worker and observation IDs remain unchanged; connection metadata is recorded separately in the response environment.
