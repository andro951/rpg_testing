# RPG Perchance text worker

Text-only adaptation of the local EmberAdventures tools/perchance-ai-text-harness browser-page-runner.mjs and perchance-browser-worker-bottom.html. The original harness is retained unchanged. This copy removes image generation, playtesting, file queues and retries; preserves untrimmed responses; exposes independent job snapshots/cancellation; and uses its own RpgPerchanceText namespace.

The Workbench opens an owned browser window with a private persistent profile at the existing worker URL, locates its plugin frame, and injects worker.js in memory. No saved Perchance page is edited. The existing bootstrap page can still import its own image plugin; this adapter never invokes it. For a separate hosted text-only page, use this left pane:

```text
aiTextPlugin = {import:ai-text-plugin}

$meta
  header = minimal
  title = RPG Text Worker
```

The bottom pane only needs a JavaScript-created readiness label; the adapter injects worker.js when it connects. A dedicated page is optional and must be saved by its owner before configuring its URL.

Browser startup is outside benchmark timing. Worker text chunks, raw serializable plugin results, unknown stop/model settings, and first-visible-text timing are evidence; they are not native token timing or verified sampler/cache controls. Timeout/cancel closes the owned page before another call. Every workflow shares one client deadline. No browser/profile/CDP connection is shared with EmberAdventures.
