# State presentation comparison

Every JSON-state benchmark is run in three model-facing representations while keeping the authoritative state, event, workflow, sampling, timeout, and expected result the same.

## 1. raw_json

The authoritative state is shown as ordinary pretty-printed JSON. Arrays remain JSON arrays.

## 2. indexed_arrays

The state remains JSON-shaped, but every array is rendered as an object keyed by the array item's real zero-based index. The authoritative state used for scoring still contains real arrays.

## 3. full_paths

Every scalar leaf is shown as a complete dot path followed by its value.

Example:

```text
queue_name: North Region Service Desk

tickets.0.ticket_id: SR-22345
tickets.0.status: open

tickets.1.ticket_id: SR-30264
tickets.1.status: waiting_customer

review_samples: []
```

Rules:
- Arrays use numeric path segments.
- Empty arrays are preserved as `[]`.
- Empty objects are preserved as `{}`.
- Strings are shown without surrounding quotes.
- Newlines, tabs, backslashes, and dots inside path segments are escaped.
- Blank lines separate neighboring logical groups.
- The representation is model-facing only. Scoring and JSON Patch application always use the same authoritative JSON state.

Dialogue-only tests contain no state in the model prompt, so state presentation does not apply to them and they are not triplicated.
