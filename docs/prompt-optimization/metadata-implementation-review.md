# Prompt-sharing metadata implementation review

October 8, 2026. The user authorized adding the metadata identified by the sharing review. This change adds the catalog and read-only compatibility APIs; it does not implement the optimizer, edit benchmark definitions, change judgment statuses or start live model runs.

## Requirements checked

- All 61 source definitions / 179 variants are registered, with all 159 active objective variants eligible for component experiments. Sixteen dialogue variants and four inactive example variants have explicit exclusions.
- Existing report metadata is reused for task families and presentation labels. The builder refuses stale reviewed grouping digests rather than treating a changed test as reviewed automatically.
- General output-format guidance, established-facts guidance, index location/answer formatting, analysis instructions and task-specific instructions have explicit editable locations and ordered expansion scopes.
- Insertion locations preserve original final instructions and embedded input. Replacement spans are confined to the reviewed system prefix or analysis instructions. Clinical presentation notes remain fixed. Slot lookup requires membership in the reviewed catalog; callers cannot redirect an edit into input data by supplying different offsets.
- Each slot records original text, Unicode character offsets and the containing message digest. Definition digests and the native workflow fingerprint bind the whole compatibility review. Unknown or changed definitions fail closed. Timeout changes do not invalidate identity or compatibility.
- Scope memberships are explicit and nested. Output formatter scopes remain separate; task-specific guidance also respects task and output contract. One-index and two-index formatting are separate. Analysis instructions only apply to existing analysis-first workflows.
- All scopes declare full configured repetition counts, eligible model expansion and current rejected-test blocking. The future executor must apply actual model/provider eligibility and current judgments; compatibility is not execution permission.
- Array-move formatter scope sizes are 1, 3, 18, 54, 123. Move-specific task scope sizes are 1, 3. Inventory-specific scope sizes are 1, 6. Wider claims of best performance are limited to the scope actually tested.
- The catalog is a sidecar. Existing execution specifications, immutable evidence and native workflow identity are unchanged.

## Validation

Fourteen focused tests pass, including complete coverage, every instruction span, scope boundaries, source/oracle changes, embedded-data preservation, clinical presentation instructions, two-step dependencies, excluded tests, invalid scope members and caller-supplied span tampering. The read-only CLI validation completed twice. The Workbench browser smoke passed with simulated service transport, including configured repetitions and resume.

Full repository validation:

- Initial suite: **521 tests passed** in 552.645 seconds (`.local/prompt-sharing-full.log`).
- Final suite, including the additional input-span guard test: **522 tests run; 520 passed and two errored** in 552.059 seconds (`.local/prompt-sharing-final.log`). Both errors were Windows `ConnectionAbortedError: [WinError 10053]` in existing HTTP server tests, `test_json_content_type_required` and `test_null_and_foreign_origins_are_rejected_without_a_key`. All fourteen metadata tests passed.
- Server-only rerun: **32 tests run; 31 passed and one errored** in 81.587 seconds (`.local/prompt-sharing-server-rerun.log`). The foreign-origin test again received a Windows socket abort instead of an HTTP response. This reproduces the intermittent server-test problem independently of the new metadata tests. The server source was not changed by this metadata task. Do not describe the final full-suite run as clean.
- All 1,428 existing evidence files retain their size and modification timestamp, and the native workflow fingerprint remains unchanged.

## Limits

Compatible components remain hypotheses to test empirically. Metadata cannot prove that newly written instructions retain their meaning or improve performance. Candidate creation must keep immutable requirements, run unchanged evaluators and retain complete comparison evidence. A future optimization runner must validate the complete catalog before using target scopes, apply current judgments/provider capabilities, record candidate versions and detect duplicate rendered requests caused by overrides. No UI, optimizer session, candidate application or stopping condition is introduced here.
