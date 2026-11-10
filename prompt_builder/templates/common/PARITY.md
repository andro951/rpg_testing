# Legacy parity and the intentional change

Before changing schema behavior, the replacement template assembly reproduced all **38 current base message lists** (13 cases × applicable input views) byte-for-byte in roles and content, including whitespace and the empty system message. Independent serializers and schema rendering were checked against both the original builder and the frozen draft snapshots.

An additional **24 captured researched-format message lists** were reconstructed exactly from their extracted format fragments and captured case inputs. This covers the format catalog examples, not every historical optimized/cohort prompt.

Evidence: `archives/prompt-builder-parity/parity-report.json` records SHA-256 hashes and scope; `legacy-messages.json` preserves the old messages. Source baseline: `a64cc029837a33d4b67a6a8e4b5d686497ef943c`.

After that check, schema descriptions were removed, shared restrictions revised, and the ID-keyed/full-path views made self-describing. That original migration had the new `file-templates-v1` / `schema-free-intent-v1` identity. It is **not** byte-equivalent to old prompts after these requested changes, and old model results are not relabeled as results of this version.

The old builder is deleted. Frozen tests, references, prompt snapshots and results remain. Historical synthetic regression tests run saved definitions rather than regenerating them with archived builder code.

The later validator-only ID mapping revision selects `array-identities-intent-v1`. Its current 38 messages remain byte-identical to the immediately preceding schema-free suite; ID metadata changes evaluation identity, never model messages. Historical parity evidence above remains unchanged.
