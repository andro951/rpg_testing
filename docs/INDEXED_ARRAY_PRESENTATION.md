# Indexed-array state presentation

Authoritative state remains ordinary JSON. The workbench does not replace arrays in storage.

For model-facing prompts, the default presentation is now `indexed_arrays`: every JSON array is rendered as a JSON object whose keys are the real zero-based array indexes. This makes the index visible to the model instead of requiring it to count array elements.

The model still returns ordinary RFC 6902 JSON Patch. The visible numeric key maps directly to the JSON Pointer array index in the authoritative JSON. Patches are validated and applied to the real JSON state.

Tests can set `state_presentation` to `raw_json` to show ordinary arrays. The paired 100-item array fixtures 004 through 009 use identical source situations with one raw-array variant and one indexed-object variant so the effect of presentation can be measured directly.

The core benchmark no longer relies on the custom semantic patch representation. Legacy semantic support remains in the harness only for older examples/backward compatibility while results are migrated.
