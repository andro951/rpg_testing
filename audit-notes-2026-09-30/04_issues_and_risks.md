# Operational, research and security risks

## R01 — P2: local test duration exceeds built-in test action budget

Controller.selftest at controller.py:208 has a fixed 180-second subprocess timeout. The correctly configured 330-test suite was still running beyond five minutes on this desktop. Several controller/edge tests execute all 387 cases repeatedly. tests/browser_smoke.py:73 similarly waits only 15 seconds for an entire run and failed locally with state RUNNING. Treat these as measured local timing limitations, not evidence all CI platforms fail.

Repair: isolate a bounded set of plumbing cases in most tests, retaining one deliberate full-matrix regression. Use an explicit appropriate selftest deadline and asynchronous progress. Use a workload-appropriate browser deadline; avoid making unit tests depend on research matrix growth.

## R02 — P2: metadata identity and native build caching have verification limits

identify_artifact uses name/size/mtime and copied source metadata, not current-byte SHA-256. scan_models parses the first shard only. backend_version caches output until setup/runtime changes. Replacing a binary in place while the app runs can leave target/provenance cached although load metadata contains a fresh runtime version. Same-size/mtime weight replacement can reuse old identity.

Repair: distinguish observed metadata from verified hashes explicitly. Offer deliberate content verification and compare runtime identity at every load against the planned target; replan/version if it changes. Test in-place runtime replacement and preserved-mtime weight mutation. Do not claim cryptographic provenance from metadata alone.

## R03 — P2: editor validation is not a complete execution contract

validate_test can accept source={} without initial_state when there is no schema, result.step absent for an expected-state task, and objective checks missing value. Prompt/evaluate then fail later. Some backend contract fields are checked only for top-level steps. Repair with precise source/result/check validation, conditional/nested capability tests and actionable editor errors. Keep narrative/no-oracle definitions valid by an explicit rule.

## R04 — P2: batch restart chain is not bounded like graphical runs

launch_workbench.main restarts every exit 75 indefinitely. --batch returns 75 on source changes but does not use UpdateCoordinator's automatic_restart_count/resume TTL. Repeated upstream changes can consume an allocation with repeated pulls/restarts. Repair a common supervisor-level maximum and test batch and graphical paths. No Unity job was run to demonstrate the external symptom.

## R05 — P2: large result/history work scales poorly

code_fingerprint rereads 11 files for each case ID. pending_plan builds history for missing IDs and linearly compares old records per new case. Results repeat full test/state/load properties and raw chunks, so reading/checksumming/exporting all 1,552 files and returning snapshot data can be expensive. Current local suite/browser latency is consistent with this workload, but no profiler attribution was performed. Repair by run-scoped immutable fingerprints and indexed history, retaining corruption checks and exact identity semantics; then measure before adding persistent caches.

## R06 — P2: authoritative scans and download cancellation need careful recovery

An existing empty directory can represent an unmounted external volume, yet scan reconciliation deletes catalog metadata. Cancelled download metadata is written before transfer; a subsequent scan can remove that assignment when only partials exist, weakening discoverable resume. Repair mount-aware scan warnings where supported and explicit resumable download job metadata separate from installed catalog entries. Test unavailable path versus empty mount versus partial transfer. Existing intended manual deletion cleanup should remain functional.

## R07 — P2: optional publishing assumes one writer and sufficient memory

Publisher.prepare trusts an existing .git file without confirming branch/root. It mirrors local results and removes stale mirrored files, commits narrowly and pushes; it does not fetch/reconcile remote branch advancement on each flush. Conflicting remote pushes remain local warnings. Export builds all JSON summaries and ZIP bytes in memory. Keep single-writer branches; verify checkout identity; stream large exports or bound memory. Never broaden staging or reset divergent history.

## R08 — P2: control-plane blocking and sequencing edges

ThreadingHTTPServer has no explicit idle client timeout or connection cap; authenticated bodies can block reads and concurrent native-picker requests can open multiple host dialogs. Several server actions check operation.locked without acquiring it. Result reads correctly acquire the operation lock. Repair only demonstrated contention paths with explicit server/action ownership and bounded I/O. Bind/auth/Origin protections are strong; this review did not perform penetration or real tailnet tests.

## R09 — P2: research confidence and documentation drift

README says 110 simulated cases while current matrix has 387. WORKBENCH_GUIDE says preflight runs harness tests and describes old 600/300-second workflows; current code separates unit tests and uses test.timeout_seconds (60). docs/DESIGN and PLANNED_CHANGES retain a three/default-fixture framing; TEST_REPORT identifies a September 21 checkpoint and old counts, not the cloned commit. Keep reports historically labelled and add current validation evidence. Broad statistical conclusions are unsupported by small repeated synthetic task families and deterministic fixture adapters.

## R10 — P3: UI settings/workflow friction

Choosing a folder/runtime sets setupDirty=false even if unrelated fields hold unsaved changes; polling can overwrite those drafts. UI offers no explicit clear-token action since an empty token field is omitted. Whole-source JSON editing can rename IDs without deleting old definitions. Broad result views render every matching record without pagination. Repair draft preservation, token clearing, explicit create/rename distinction and bounded result views with browser tests.

Security/privacy boundary: no private data or credentials were introduced. Controls use textContent, local schema references, immutable remote revisions, narrow Git staging and constrained extraction. Hashes protect integrity, not authenticity against a person who can rewrite both data/checksum. Result contents are public synthetic research evidence by project policy; export/publication still needs appropriate user data discipline. This audit did not scan or read the unrelated JS Dev credential files.
