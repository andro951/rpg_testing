# Prompt-version failure retrospective — 16 October 2026

## Executive findings

This completed read-only inventory reconciles **all 930 original observations**, including all **138 original desktop Qwen3.5-9B Q4_K_M failures**, and every subsequently discovered saved live database-suite observation through final desktop, Perchance and Unity propagation. It contains **6,041 distinct saved observations**, **334 exact sent-message versions plus one no-request placeholder**, and 10 model/worker cohorts. Archive copies are references, not extra samples.

Original saved outcomes: **4,135 PASS, 1,897 completed model FAIL, 7 terminal timeout, 1 transport/runtime ERROR, 1 interrupted partial**. The historical counts aggregate different prompts and selected OPRO scopes; they are not one accuracy estimate. Every non-pass has its actual output, expected/source state, saved validator evidence and source references in the failure evidence JSONL.

Most failures concern the operation language: quotes inside value paths, the complete source path, JSON containers/escaping, and field roles. There are also semantic errors: Copy vs Move, omitted required changes, and mutations for unrelated information. The retired redundant-assignment NOOP is a separate design confound. Strict rejection of bare string selectors is consistent with the specified typed path grammar; this inspection establishes no scorer defect that turns those outputs into valid submitted operations.

The final prompt succeeds on desktop Q4_K_M and Q4_K_S at 186/186, but does not generalize uniformly: the 4B cohort falls from 183 to 99, while Unity Q4_K_M reaches 180. Prompt promotion must therefore be evaluated per exact model and worker. No new inference, optimization, patch application, regrading, parser change or evidence deletion was performed for this retrospective.

## Scope, provenance and counting

The original manifest is `selector-quote-revision/original-evidence-hashes.json` (SHA256 `9c17ff3243415ce6fc427b40871d4672e321b7ff357f517b0aef2bf07d584a95`). All 930 source-file hashes were found. The original run ended 15 October 2026 at 15:34:03 EDT / 19:34:03 UTC; its earliest saved observation is `2026-10-15T19:08:08.508547+00:00`. Later data never substitutes for that run. The original cohort is four native desktop models plus Perchance; Q4_K_S and Unity are later additions.

Inspected sources: task-workspace loose JSON, the retained task evidence archives, current repository results, optimization_results, and repository study archives. Read 26,744 JSON source documents; 16,216 record references reconcile to 6,041 distinct request/output identities before chronology filtering. 0 pre-baseline observations are excluded. The source-files JSONL records every parsed document and its byte hash. Two pre-baseline archived optimization sessions are excluded from the in-window candidate table; directory 33570f57299d40d080582ea21f9f0c28 contains no saved session or trial files. No denied session storage, credentials or model-weight contents were inspected.

Deduplication uses actual request/response IDs plus model, exact messages and output; when IDs are absent, timestamp/case/repetition/content form a weaker identity. Independent calls with identical prompts and answers remain independent observations. Three expected weak identities are the empty-text provider error, terminal native timeout and cancelled partial; see the inventory for exact IDs. Embedded session summaries, copied result files, archived trials and detailed evaluator views do not create extra samples. Distinct repeated attempts are preserved.

The prompt key is SHA256 of canonical JSON for the actual role/content message array (`request_messages` when saved, otherwise `messages`); multiple-call workflows hash the ordered message arrays. The prompt registry stores the complete messages. Perchance also records the effective serialized instruction hash and serializer version in the inventory; remote model identity and provider defaults remain unknown. A cancelled attempt with no calls is marked `actual_request_present=false` and does not establish that an empty prompt was sent.

Record integrity: sha256_verified=5617, no_stored_record_checksum=1, checksum_verified=423. No checksum mismatch was found. File-level hashes preserve original bytes, including line endings. The scripts import no evaluator and never apply a submitted patch. Classification parses JSON syntax and reads saved states/errors only; syntax classification does not repair or rescore an answer.

## Exact prompt versions first

Each row below is an actual message version, not a candidate label or a current builder reconstruction. The companion prompt-versions JSONL supplies its full SHA256, actual messages, exact model/test/format/repetition sets, outcomes and source observation IDs. Failure counts within a row are grouped by the primary observed mechanism; concurrent operation-contract errors are additional inventory tags. Prefixes below are unique in this corpus.

| Version / SHA prefix | Test · format | Calls; PASS/FAIL/technical | Failure mechanisms |
| --- | --- | --- | --- |
| V001 4fc424aaa981 | append_record · normal_json | 15; 15/0/0 | — |
| V002 c2fe05440c22 | append_record · id_keyed_arrays | 15; 15/0/0 | — |
| V003 ee928afe56d9 | append_record · full_paths | 15; 15/0/0 | — |
| V004 0bbd9f2804bc | append_record_empty · normal_json | 15; 15/0/0 | — |
| V005 6a260f88fa24 | append_record_empty · id_keyed_arrays | 15; 15/0/0 | — |
| V006 d47e4e81b195 | append_record_empty · full_paths | 15; 15/0/0 | — |
| V007 ca3a225e7e99 | append_value · normal_json | 15; 15/0/0 | — |
| V008 b0de7768e4ad | append_value · id_keyed_arrays | 15; 15/0/0 | — |
| V009 12d2a3ffb04d | append_value · full_paths | 15; 15/0/0 | — |
| V010 c468b6bbd4d0 | append_value_empty · normal_json | 15; 15/0/0 | — |
| V011 c017ef348eca | append_value_empty · id_keyed_arrays | 15; 12/3/0 | wrong_or_unsupported_operation_name:3 |
| V012 69c7fd053134 | append_value_empty · full_paths | 15; 15/0/0 | — |
| V013 87805c63925a | copy_record · normal_json | 15; 1/14/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6; outer_json_string_escaping_error:2 |
| V014 0f39c3789dde | copy_record · id_keyed_arrays | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V015 97d555f65a28 | copy_record · full_paths | 15; 3/12/0 | missing_or_non_json_collection_selector:6; source_id_used_without_collection_path:3; outer_json_string_escaping_error:3 |
| V016 5c32afe838a2 | copy_record_empty · normal_json | 15; 2/13/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6; outer_json_string_escaping_error:1 |
| V017 e7b90c1956c0 | copy_record_empty · id_keyed_arrays | 15; 1/14/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6; outer_json_string_escaping_error:2 |
| V018 e7fd6079ab81 | copy_record_empty · full_paths | 15; 0/15/0 | missing_or_non_json_collection_selector:6; source_id_used_without_collection_path:3; outer_json_string_escaping_error:6 |
| V019 053747a0165b | copy_value · normal_json | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V020 8d28d1a2af6f | copy_value · id_keyed_arrays | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V021 2d45477156da | copy_value · full_paths | 15; 3/12/0 | wrong_supported_operation_for_task:3; source_id_used_without_collection_path:3; missing_or_non_json_collection_selector:3; outer_json_string_escaping_error:3 |
| V022 56ae89526c12 | copy_value_empty · normal_json | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V023 d1656e6c157b | copy_value_empty · id_keyed_arrays | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V024 dfa547306eca | copy_value_empty · full_paths | 15; 3/12/0 | wrong_supported_operation_for_task:3; source_id_used_without_collection_path:3; missing_or_non_json_collection_selector:6 |
| V025 b60fb63ef6f4 | move_record · normal_json | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V026 b99bd1c63ccc | move_record · id_keyed_arrays | 15; 2/13/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6; outer_json_string_escaping_error:1 |
| V027 f746ac5d9e49 | move_record · full_paths | 15; 3/12/0 | missing_or_non_json_collection_selector:8; array_fields_without_operation_object:3; outer_json_string_escaping_error:1 |
| V028 896f5a5472aa | move_record_empty · normal_json | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V029 eb2d5cd9fb90 | move_record_empty · id_keyed_arrays | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V030 16b4df4df905 | move_record_empty · full_paths | 15; 3/12/0 | missing_or_non_json_collection_selector:6; array_fields_without_operation_object:3; outer_json_string_escaping_error:3 |
| V031 3a0762fda7ee | move_value · normal_json | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V032 fd143de47401 | move_value · id_keyed_arrays | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V033 713be68b55fd | move_value · full_paths | 15; 6/9/0 | source_id_used_without_collection_path:3; missing_or_non_json_collection_selector:3; outer_json_string_escaping_error:3 |
| V034 7d6718a5149c | move_value_empty · normal_json | 15; 1/14/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6; outer_json_string_escaping_error:2 |
| V035 d8b6aaaeae05 | move_value_empty · id_keyed_arrays | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V036 0514382bee42 | move_value_empty · full_paths | 15; 6/9/0 | source_id_used_without_collection_path:3; missing_or_non_json_collection_selector:3; outer_json_string_escaping_error:3 |
| V037 88e3c84243db | no_change · normal_json | 15; 5/10/0 | markdown_fences_or_code_wrapper:1; missing_or_non_json_collection_selector:9 |
| V038 c15cf577c9c8 | no_change · id_keyed_arrays | 15; 3/12/0 | missing_or_non_json_collection_selector:12 |
| V039 7eaa2a610fa9 | no_change · full_paths | 15; 6/9/0 | historical_redundant_assignment_noop_design:3; outer_json_string_escaping_error:3; missing_or_non_json_collection_selector:3 |
| V040 1bd017d92da9 | remove_record · normal_json | 15; 3/12/0 | missing_or_non_json_collection_selector:9; outer_json_string_escaping_error:3 |
| V041 48d9912a9fd2 | remove_record · id_keyed_arrays | 15; 0/15/0 | missing_or_non_json_collection_selector:9; outer_json_string_escaping_error:6 |
| V042 c76d214e2537 | remove_record · full_paths | 15; 6/9/0 | missing_or_non_json_collection_selector:9 |
| V043 ae6d83c4769b | remove_record_last · normal_json | 15; 3/12/0 | missing_or_non_json_collection_selector:9; outer_json_string_escaping_error:3 |
| V044 43efd28e48a5 | remove_record_last · id_keyed_arrays | 15; 3/12/0 | missing_or_non_json_collection_selector:9; outer_json_string_escaping_error:3 |
| V045 f66046191976 | remove_record_last · full_paths | 15; 6/9/0 | missing_or_non_json_collection_selector:7; outer_json_string_escaping_error:2 |
| V046 67aad4b347c2 | remove_value · normal_json | 15; 3/12/0 | missing_or_non_json_collection_selector:6; wrong_remove_selection_level_or_field_role:6 |
| V047 4b0baabfa50c | remove_value · id_keyed_arrays | 15; 3/12/0 | missing_or_non_json_collection_selector:9; outer_json_string_escaping_error:3 |
| V048 623658140a62 | remove_value · full_paths | 15; 9/6/0 | missing_or_non_json_collection_selector:6 |
| V049 f25c1c1b3840 | remove_value_last · normal_json | 15; 3/12/0 | missing_or_non_json_collection_selector:6; wrong_remove_selection_level_or_field_role:6 |
| V050 8f23cc83755e | remove_value_last · id_keyed_arrays | 15; 3/12/0 | missing_or_non_json_collection_selector:9; wrong_remove_selection_level_or_field_role:3 |
| V051 f2e5e612f9ae | remove_value_last · full_paths | 15; 9/6/0 | wrong_remove_selection_level_or_field_role:3; missing_or_non_json_collection_selector:3 |
| V052 d31b838e19ea | update_field · normal_json | 15; 15/0/0 | — |
| V053 326f0d21df0f | update_field · full_paths | 15; 15/0/0 | — |
| V054 807aa05d2e20 | update_nested_collection · normal_json | 15; 3/12/0 | missing_or_non_json_collection_selector:12 |
| V055 86b486ce17a5 | update_nested_collection · id_keyed_arrays | 15; 1/14/0 | missing_or_non_json_collection_selector:12; wrong_or_incomplete_object_field_path:1; outer_json_string_escaping_error:1 |
| V056 73f9c7b14377 | update_nested_collection · full_paths | 15; 6/9/0 | outer_json_string_escaping_error:3; missing_or_non_json_collection_selector:6 |
| V057 ef520530dd8a | update_record · normal_json | 15; 3/12/0 | missing_or_non_json_collection_selector:12 |
| V058 24e97fdc0810 | update_record · id_keyed_arrays | 15; 3/12/0 | missing_or_non_json_collection_selector:12 |
| V059 a173c81a43ad | update_record · full_paths | 15; 6/9/0 | outer_json_string_escaping_error:3; missing_or_non_json_collection_selector:6 |
| V060 7c4420933d95 | update_record_nested · normal_json | 15; 3/12/0 | selector_matches_no_or_multiple_elements:3; missing_or_non_json_collection_selector:9 |
| V061 8daf99539695 | update_record_nested · id_keyed_arrays | 15; 3/12/0 | missing_or_non_json_collection_selector:12 |
| V062 8b4919d035b7 | update_record_nested · full_paths | 15; 6/9/0 | outer_json_string_escaping_error:6; missing_or_non_json_collection_selector:3 |
| V063 5772a4fc3dcd | update_field · normal_json | 21; 21/0/0 | — |
| V064 4c06ea5ef4d4 | update_field · full_paths | 21; 18/3/0 | markdown_fences_or_code_wrapper:3 |
| V065 632281fa98c0 | update_nested_collection · normal_json | 21; 0/21/0 | missing_or_non_json_collection_selector:21 |
| V066 e71ffde4ae69 | update_nested_collection · id_keyed_arrays | 21; 0/21/0 | missing_or_non_json_collection_selector:21 |
| V067 c9b3c0308af7 | update_nested_collection · full_paths | 21; 3/18/0 | missing_or_non_json_collection_selector:15; markdown_fences_or_code_wrapper:3 |
| V068 1956faac250e | update_record · normal_json | 21; 3/18/0 | missing_or_non_json_collection_selector:15; markdown_fences_or_code_wrapper:3 |
| V069 9507640fe1f8 | update_record · id_keyed_arrays | 21; 6/15/0 | missing_or_non_json_collection_selector:15 |
| V070 ea5f5837f120 | update_record · full_paths | 21; 15/6/0 | missing_or_non_json_collection_selector:3; markdown_fences_or_code_wrapper:3 |
| V071 a8d1636c3312 | update_record_nested · normal_json | 21; 6/15/0 | missing_or_non_json_collection_selector:15 |
| V072 95e6b4144e50 | update_record_nested · id_keyed_arrays | 21; 6/15/0 | missing_or_non_json_collection_selector:15 |
| V073 15a3cfcf6887 | update_record_nested · full_paths | 21; 12/9/0 | missing_or_non_json_collection_selector:6; markdown_fences_or_code_wrapper:3 |
| V074 ec5c25377936 | update_record · normal_json | 3; 3/0/0 | — |
| V075 081a8f152b40 | update_field · normal_json | 3; 3/0/0 | — |
| V076 dd4e33d8ba62 | update_field · full_paths | 3; 3/0/0 | — |
| V077 8a58f084e1bd | update_nested_collection · normal_json | 3; 0/3/0 | missing_or_non_json_collection_selector:3 |
| V078 cabc35a21823 | update_nested_collection · id_keyed_arrays | 3; 0/3/0 | missing_or_non_json_collection_selector:3 |
| V079 9e67e61c995a | update_nested_collection · full_paths | 3; 0/3/0 | outer_json_string_escaping_error:3 |
| V080 db6e9df15cc3 | update_record · id_keyed_arrays | 3; 3/0/0 | — |
| V081 ef930dc56905 | update_record · full_paths | 3; 3/0/0 | — |
| V082 e871eb9ff59b | update_record_nested · normal_json | 3; 3/0/0 | — |
| V083 0a068c5faafa | update_record_nested · id_keyed_arrays | 3; 3/0/0 | — |
| V084 d327579d5315 | update_record_nested · full_paths | 3; 3/0/0 | — |
| V085 019e0f763641 | update_record · normal_json | 3; 3/0/0 | — |
| V086 ecedf64eabc7 | update_field · normal_json | 3; 3/0/0 | — |
| V087 3da0c8d38205 | update_field · full_paths | 3; 3/0/0 | — |
| V088 6adbcea47943 | update_nested_collection · normal_json | 3; 3/0/0 | — |
| V089 bf3d5aa9b3af | update_nested_collection · id_keyed_arrays | 3; 3/0/0 | — |
| V090 ba6766b1e691 | update_nested_collection · full_paths | 3; 3/0/0 | — |
| V091 e8e7ac4aab04 | update_record · id_keyed_arrays | 3; 3/0/0 | — |
| V092 caa99ad61195 | update_record · full_paths | 3; 3/0/0 | — |
| V093 b8d96bfb79f1 | update_record_nested · normal_json | 3; 3/0/0 | — |
| V094 2a4f86a9db0c | update_record_nested · id_keyed_arrays | 3; 3/0/0 | — |
| V095 d44c68d51572 | update_record_nested · full_paths | 3; 3/0/0 | — |
| V096 46dff412eb6c | append_record · normal_json | 15; 12/3/0 | markdown_fences_or_code_wrapper:3 |
| V097 c46fd82f9fd4 | append_record · id_keyed_arrays | 15; 12/3/0 | markdown_fences_or_code_wrapper:3 |
| V098 147677c093d4 | append_record · full_paths | 15; 12/3/0 | markdown_fences_or_code_wrapper:3 |
| V099 cddfd62c0d6d | append_record_empty · normal_json | 15; 12/3/0 | markdown_fences_or_code_wrapper:3 |
| V100 eeb9984382fa | append_record_empty · id_keyed_arrays | 15; 12/3/0 | markdown_fences_or_code_wrapper:3 |
| V101 2d6673ce21f5 | append_record_empty · full_paths | 15; 12/3/0 | markdown_fences_or_code_wrapper:3 |
| V102 a6d5ac547b2f | append_value · normal_json | 15; 12/3/0 | markdown_fences_or_code_wrapper:3 |
| V103 8301ce1eeaf2 | append_value · id_keyed_arrays | 15; 12/3/0 | markdown_fences_or_code_wrapper:3 |
| V104 ee1a65b712a6 | append_value · full_paths | 15; 12/3/0 | markdown_fences_or_code_wrapper:3 |
| V105 150d519db094 | append_value_empty · normal_json | 15; 15/0/0 | — |
| V106 7e18f6458578 | append_value_empty · id_keyed_arrays | 15; 15/0/0 | — |
| V107 b09779df39c6 | append_value_empty · full_paths | 15; 15/0/0 | — |
| V108 51b24b5ee1f3 | copy_record · normal_json | 15; 0/15/0 | missing_or_non_json_collection_selector:9; source_id_used_without_collection_path:3; markdown_fences_or_code_wrapper:3 |
| V109 50892dd5662d | copy_record · id_keyed_arrays | 15; 0/15/0 | missing_or_non_json_collection_selector:12; markdown_fences_or_code_wrapper:3 |
| V110 8677500e5b20 | copy_record · full_paths | 15; 3/12/0 | missing_or_non_json_collection_selector:12 |
| V111 b478966e19ac | copy_record_empty · normal_json | 15; 0/15/0 | missing_or_non_json_collection_selector:9; markdown_fences_or_code_wrapper:6 |
| V112 2042e7add644 | copy_record_empty · id_keyed_arrays | 15; 3/12/0 | missing_or_non_json_collection_selector:9; markdown_fences_or_code_wrapper:3 |
| V113 04984dc4a7f9 | copy_record_empty · full_paths | 15; 0/15/0 | missing_or_non_json_collection_selector:12; markdown_fences_or_code_wrapper:3 |
| V114 8c81d3e2408f | copy_value · normal_json | 15; 0/15/0 | missing_or_non_json_collection_selector:9; markdown_fences_or_code_wrapper:6 |
| V115 eae3cefdb42a | copy_value · id_keyed_arrays | 15; 3/12/0 | missing_or_non_json_collection_selector:9; source_id_used_without_collection_path:3 |
| V116 3b14f86273e9 | copy_value · full_paths | 15; 0/15/0 | missing_or_non_json_collection_selector:12; markdown_fences_or_code_wrapper:3 |
| V117 ec92483f470e | copy_value_empty · normal_json | 15; 0/15/0 | missing_or_non_json_collection_selector:9; markdown_fences_or_code_wrapper:6 |
| V118 ca6fa696f54a | copy_value_empty · id_keyed_arrays | 15; 3/12/0 | missing_or_non_json_collection_selector:9; source_id_used_without_collection_path:3 |
| V119 8addafdb17ee | copy_value_empty · full_paths | 15; 0/15/0 | missing_or_non_json_collection_selector:9; source_id_used_without_collection_path:3; markdown_fences_or_code_wrapper:3 |
| V120 e4303182cbce | move_record · normal_json | 15; 0/15/0 | source_id_used_without_collection_path:9; missing_or_non_json_collection_selector:6 |
| V121 1d238bbbdf9d | move_record · id_keyed_arrays | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V122 352be3c41e5a | move_record · full_paths | 15; 0/15/0 | source_id_used_without_collection_path:3; missing_or_non_json_collection_selector:9; markdown_fences_or_code_wrapper:3 |
| V123 aa419bf81fb9 | move_record_empty · normal_json | 15; 0/15/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6; markdown_fences_or_code_wrapper:3 |
| V124 3cfbfc9f6b35 | move_record_empty · id_keyed_arrays | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V125 9fcacffa9874 | move_record_empty · full_paths | 15; 0/15/0 | source_id_used_without_collection_path:3; missing_or_non_json_collection_selector:9; markdown_fences_or_code_wrapper:3 |
| V126 f43fb7b66de4 | move_value · normal_json | 15; 0/15/0 | source_id_used_without_collection_path:6; markdown_fences_or_code_wrapper:6; missing_or_non_json_collection_selector:3 |
| V127 139d2ad1db59 | move_value · id_keyed_arrays | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V128 090aa0e17f8c | move_value · full_paths | 15; 3/12/0 | missing_or_non_json_collection_selector:12 |
| V129 c1271a3846b2 | move_value_empty · normal_json | 15; 0/15/0 | source_id_used_without_collection_path:6; markdown_fences_or_code_wrapper:6; missing_or_non_json_collection_selector:3 |
| V130 c2ccf3615809 | move_value_empty · id_keyed_arrays | 15; 3/12/0 | source_id_used_without_collection_path:6; missing_or_non_json_collection_selector:6 |
| V131 c9b2326959f9 | move_value_empty · full_paths | 15; 0/15/0 | missing_or_non_json_collection_selector:12; markdown_fences_or_code_wrapper:3 |
| V132 04dc69999288 | no_change · normal_json | 15; 6/6/3 | missing_or_non_json_collection_selector:6; technical_benchmark_timeout:3 |
| V133 a617d1007beb | no_change · id_keyed_arrays | 15; 3/9/3 | missing_or_non_json_collection_selector:9; technical_benchmark_timeout:3 |
| V134 2447a57712f2 | no_change · full_paths | 15; 15/0/0 | — |
| V135 ea780be4a636 | remove_record · normal_json | 15; 3/12/0 | missing_or_non_json_collection_selector:12 |
| V136 faff7fdc3323 | remove_record · id_keyed_arrays | 15; 3/12/0 | missing_or_non_json_collection_selector:12 |
| V137 5aa869376915 | remove_record · full_paths | 15; 3/12/0 | missing_or_non_json_collection_selector:9; markdown_fences_or_code_wrapper:3 |
| V138 77b30ac60690 | remove_record_last · normal_json | 15; 0/15/0 | missing_or_non_json_collection_selector:12; markdown_fences_or_code_wrapper:3 |
| V139 4b3dd672410d | remove_record_last · id_keyed_arrays | 15; 3/12/0 | missing_or_non_json_collection_selector:12 |
| V140 918e73f80065 | remove_record_last · full_paths | 15; 6/9/0 | missing_or_non_json_collection_selector:6; markdown_fences_or_code_wrapper:3 |
| V141 12778f771507 | remove_value · normal_json | 15; 0/15/0 | missing_or_non_json_collection_selector:12; markdown_fences_or_code_wrapper:3 |
| V142 d06467ef6f9e | remove_value · id_keyed_arrays | 15; 0/15/0 | missing_or_non_json_collection_selector:12; markdown_fences_or_code_wrapper:3 |
| V143 400d44cc8ec9 | remove_value · full_paths | 15; 6/9/0 | missing_or_non_json_collection_selector:9 |
| V144 bf327539ee26 | remove_value_last · normal_json | 15; 3/12/0 | missing_or_non_json_collection_selector:12 |
| V145 168e0a813d31 | remove_value_last · id_keyed_arrays | 15; 3/12/0 | missing_or_non_json_collection_selector:12 |
| V146 7ce219e9350f | remove_value_last · full_paths | 15; 3/12/0 | wrong_remove_selection_level_or_field_role:3; markdown_fences_or_code_wrapper:3; missing_or_non_json_collection_selector:6 |
| V147 88cfa2cf27ca | append_record · normal_json | 27; 27/0/0 | — |
| V148 2d57ab1d29cc | append_record · id_keyed_arrays | 27; 27/0/0 | — |
| V149 d5ba5ed9fd82 | append_record · full_paths | 27; 27/0/0 | — |
| V150 4131a53c12db | append_record_empty · normal_json | 27; 27/0/0 | — |
| V151 1d636257c624 | append_record_empty · id_keyed_arrays | 27; 27/0/0 | — |
| V152 a55b6a92362f | append_record_empty · full_paths | 27; 27/0/0 | — |
| V153 ad84e745dc56 | append_value · normal_json | 27; 27/0/0 | — |
| V154 c0704004c185 | append_value · id_keyed_arrays | 27; 27/0/0 | — |
| V155 2a71cad2442f | append_value · full_paths | 27; 27/0/0 | — |
| V156 02bc5eabd9ca | append_value_empty · normal_json | 27; 27/0/0 | — |
| V157 917675042433 | append_value_empty · id_keyed_arrays | 27; 24/3/0 | wrong_or_unsupported_operation_name:3 |
| V158 ebf1f059ba49 | append_value_empty · full_paths | 27; 27/0/0 | — |
| V159 5bf42c0440dd | copy_record · normal_json | 27; 15/12/0 | missing_or_non_json_collection_selector:12 |
| V160 b074e9848fd1 | copy_record · id_keyed_arrays | 27; 21/6/0 | missing_or_non_json_collection_selector:6 |
| V161 b3065a1cf40b | copy_record · full_paths | 27; 24/3/0 | missing_or_non_json_collection_selector:3 |
| V162 ec523e6a982e | copy_record_empty · normal_json | 27; 18/9/0 | missing_or_non_json_collection_selector:9 |
| V163 d8d9a6d7af1d | copy_record_empty · id_keyed_arrays | 27; 18/9/0 | missing_or_non_json_collection_selector:9 |
| V164 59a7b8e678c4 | copy_record_empty · full_paths | 27; 24/3/0 | missing_or_non_json_collection_selector:3 |
| V165 a8d050726be6 | copy_value · normal_json | 27; 12/15/0 | missing_or_non_json_collection_selector:15 |
| V166 fc0039aa21a3 | copy_value · id_keyed_arrays | 27; 9/18/0 | missing_or_non_json_collection_selector:18 |
| V167 12eddad3e66a | copy_value · full_paths | 27; 18/9/0 | missing_or_non_json_collection_selector:9 |
| V168 743eb3a72d01 | copy_value_empty · normal_json | 27; 12/15/0 | missing_or_non_json_collection_selector:15 |
| V169 0bbe3207fc56 | copy_value_empty · id_keyed_arrays | 27; 9/18/0 | missing_or_non_json_collection_selector:18 |
| V170 4921b6be43f4 | copy_value_empty · full_paths | 27; 18/9/0 | outer_json_string_escaping_error:3; missing_or_non_json_collection_selector:6 |
| V171 33583b772d2b | move_record · normal_json | 30; 15/15/0 | missing_or_non_json_collection_selector:15 |
| V172 d4bf9bcbe6a8 | move_record · id_keyed_arrays | 30; 15/15/0 | missing_or_non_json_collection_selector:15 |
| V173 10b0b622f61f | move_record · full_paths | 30; 21/9/0 | missing_or_non_json_collection_selector:9 |
| V174 c2c934150ec9 | move_record_empty · normal_json | 30; 15/15/0 | missing_or_non_json_collection_selector:15 |
| V175 4254093041d4 | move_record_empty · id_keyed_arrays | 30; 12/18/0 | missing_or_non_json_collection_selector:18 |
| V176 c5d7ca3e894c | move_record_empty · full_paths | 30; 21/9/0 | missing_or_non_json_collection_selector:9 |
| V177 51f1e2528dae | move_value · normal_json | 30; 12/18/0 | missing_or_non_json_collection_selector:18 |
| V178 b8b93a8f716d | move_value · id_keyed_arrays | 30; 9/21/0 | missing_or_non_json_collection_selector:21 |
| V179 8a307667bda4 | move_value · full_paths | 30; 21/9/0 | outer_json_string_escaping_error:3; missing_or_non_json_collection_selector:6 |
| V180 d95a13057ad9 | move_value_empty · normal_json | 30; 12/18/0 | missing_or_non_json_collection_selector:18 |
| V181 6b3e831fc964 | move_value_empty · id_keyed_arrays | 30; 9/21/0 | missing_or_non_json_collection_selector:21 |
| V182 ddf56a1f4271 | move_value_empty · full_paths | 30; 27/3/0 | outer_json_string_escaping_error:3 |
| V183 19f636dbe0d7 | no_change · normal_json | 12; 6/6/0 | historical_redundant_assignment_noop_design:6 |
| V184 08990038735c | no_change · id_keyed_arrays | 12; 6/6/0 | historical_redundant_assignment_noop_design:6 |
| V185 f7f7562e845e | no_change · full_paths | 12; 6/6/0 | historical_redundant_assignment_noop_design:6 |
| V186 d6f74e2c77d9 | remove_record · normal_json | 27; 24/3/0 | missing_or_non_json_collection_selector:3 |
| V187 844a2f59f6b3 | remove_record · id_keyed_arrays | 27; 21/6/0 | missing_or_non_json_collection_selector:6 |
| V188 533354235450 | remove_record · full_paths | 27; 27/0/0 | — |
| V189 acd7e8a815d3 | remove_record_last · normal_json | 27; 24/3/0 | missing_or_non_json_collection_selector:3 |
| V190 4cd0eec0396a | remove_record_last · id_keyed_arrays | 27; 21/6/0 | missing_or_non_json_collection_selector:6 |
| V191 2c3eeca90b7e | remove_record_last · full_paths | 27; 27/0/0 | — |
| V192 2dde1ec33411 | remove_value · normal_json | 27; 17/10/0 | missing_or_non_json_collection_selector:9; wrong_remove_selection_level_or_field_role:1 |
| V193 06e8ce2a77db | remove_value · id_keyed_arrays | 27; 15/12/0 | missing_or_non_json_collection_selector:12 |
| V194 e09ffc0166e4 | remove_value · full_paths | 27; 27/0/0 | — |
| V195 c45b21ebeaec | remove_value_last · normal_json | 27; 15/12/0 | missing_or_non_json_collection_selector:9; wrong_remove_selection_level_or_field_role:3 |
| V196 48002803de85 | remove_value_last · id_keyed_arrays | 27; 17/10/0 | missing_or_non_json_collection_selector:10 |
| V197 db7d0b21f60e | remove_value_last · full_paths | 27; 27/0/0 | — |
| V198 7278fca2486e | update_field · normal_json | 27; 27/0/0 | — |
| V199 ef9f56a8381e | update_field · full_paths | 27; 27/0/0 | — |
| V200 e4a568f892be | update_nested_collection · normal_json | 27; 24/3/0 | missing_or_non_json_collection_selector:3 |
| V201 177260425115 | update_nested_collection · id_keyed_arrays | 27; 24/3/0 | missing_or_non_json_collection_selector:3 |
| V202 9e010ce6d210 | update_nested_collection · full_paths | 27; 27/0/0 | — |
| V203 7cb1ce59c151 | update_record · normal_json | 27; 27/0/0 | — |
| V204 a45d5ae581bf | update_record · id_keyed_arrays | 27; 24/3/0 | missing_or_non_json_collection_selector:3 |
| V205 1eda7f99c283 | update_record · full_paths | 27; 27/0/0 | — |
| V206 76893facaa70 | update_record_nested · normal_json | 27; 27/0/0 | — |
| V207 dd5e41ad778b | update_record_nested · id_keyed_arrays | 27; 24/3/0 | missing_or_non_json_collection_selector:3 |
| V208 19dfa05844d7 | update_record_nested · full_paths | 27; 27/0/0 | — |
| V209 792f00d9891f | no_change · normal_json | 27; 24/3/0 | javascript_dot_or_index_path_notation:3 |
| V210 29981703e63f | no_change · id_keyed_arrays | 27; 24/3/0 | javascript_dot_or_index_path_notation:3 |
| V211 7e1ffc312ff2 | no_change · full_paths | 27; 24/3/0 | unrequested_database_mutation_on_unrelated_information:3 |
| V212 f26f73dc4d72 | move_record · normal_json | 3; 3/0/0 | — |
| V213 1ddadc833ea5 | move_record · id_keyed_arrays | 3; 3/0/0 | — |
| V214 1e1af22e65f5 | move_record · full_paths | 3; 3/0/0 | — |
| V215 f8f1bbb8e2ee | move_record_empty · normal_json | 3; 3/0/0 | — |
| V216 b80948f245fe | move_record_empty · id_keyed_arrays | 3; 3/0/0 | — |
| V217 29ad3499efd6 | move_record_empty · full_paths | 3; 3/0/0 | — |
| V218 ddb84c41c104 | move_value · normal_json | 3; 3/0/0 | — |
| V219 1cfc620ba4fe | move_value · id_keyed_arrays | 3; 3/0/0 | — |
| V220 962e1de4ff30 | move_value · full_paths | 3; 3/0/0 | — |
| V221 60d4c4172286 | move_value_empty · normal_json | 3; 3/0/0 | — |
| V222 de2da7e1f1cc | move_value_empty · id_keyed_arrays | 3; 0/3/0 | missing_or_non_json_collection_selector:3 |
| V223 33170193433f | move_value_empty · full_paths | 3; 3/0/0 | — |
| V224 95399ff0532c | move_record · normal_json | 3; 3/0/0 | — |
| V225 f9be7db04ad4 | move_record · id_keyed_arrays | 3; 3/0/0 | — |
| V226 e0e2df99e933 | move_record · full_paths | 3; 3/0/0 | — |
| V227 196c5e2d6427 | move_record_empty · normal_json | 3; 3/0/0 | — |
| V228 77f565b0ec08 | move_record_empty · id_keyed_arrays | 3; 3/0/0 | — |
| V229 12138bb29e88 | move_record_empty · full_paths | 3; 3/0/0 | — |
| V230 6e109f7c83d4 | move_value · normal_json | 3; 0/3/0 | missing_or_non_json_collection_selector:3 |
| V231 3fcf3d4d7685 | move_value · id_keyed_arrays | 3; 3/0/0 | — |
| V232 711cd4beafa3 | move_value · full_paths | 3; 3/0/0 | — |
| V233 1759c4401f5e | move_value_empty · normal_json | 3; 3/0/0 | — |
| V234 ad260868a494 | move_value_empty · id_keyed_arrays | 3; 0/3/0 | missing_or_non_json_collection_selector:3 |
| V235 b9acf18160f4 | move_value_empty · full_paths | 3; 3/0/0 | — |
| V236 419b5de85c8f | move_record · normal_json | 3; 3/0/0 | — |
| V237 848658c3a6bd | move_record · id_keyed_arrays | 3; 3/0/0 | — |
| V238 e44bb2ba5090 | move_record · full_paths | 3; 3/0/0 | — |
| V239 a89e6e62a5e6 | move_record_empty · normal_json | 3; 3/0/0 | — |
| V240 18feeb808a6d | move_record_empty · id_keyed_arrays | 3; 3/0/0 | — |
| V241 8f9f264323d3 | move_record_empty · full_paths | 3; 3/0/0 | — |
| V242 fba16d8d9a6a | move_value · normal_json | 3; 3/0/0 | — |
| V243 806afb0372d3 | move_value · id_keyed_arrays | 3; 3/0/0 | — |
| V244 d8d36e7455ea | move_value · full_paths | 3; 3/0/0 | — |
| V245 b12ee8e0db53 | move_value_empty · normal_json | 3; 3/0/0 | — |
| V246 00f04acece32 | move_value_empty · id_keyed_arrays | 3; 3/0/0 | — |
| V247 66dea1b25312 | move_value_empty · full_paths | 3; 3/0/0 | — |
| V248 2dc93a0f1346 | append_record · normal_json | 33; 32/0/1 | technical_benchmark_timeout:1 |
| V249 c8ab126c810a | append_record · id_keyed_arrays | 33; 33/0/0 | — |
| V250 b18ce33ac3da | append_record · full_paths | 34; 33/0/1 | technical_browser_navigation:1 |
| V251 8986e7261e8c | append_record_empty · normal_json | 33; 33/0/0 | — |
| V252 95e6495e7e10 | append_record_empty · id_keyed_arrays | 33; 30/3/0 | wrong_or_unsupported_operation_name:3 |
| V253 b37480caaf24 | append_record_empty · full_paths | 33; 33/0/0 | — |
| V254 f00f9b7d0dad | append_value · normal_json | 33; 33/0/0 | — |
| V255 c2c12a789c05 | append_value · id_keyed_arrays | 33; 33/0/0 | — |
| V256 1e3500dd8ea0 | append_value · full_paths | 33; 33/0/0 | — |
| V257 5b38e3d016f0 | append_value_empty · normal_json | 33; 33/0/0 | — |
| V258 0b040eea2330 | append_value_empty · id_keyed_arrays | 33; 30/3/0 | empty_patch_misses_required_change:3 |
| V259 9cd45eb171d2 | append_value_empty · full_paths | 33; 33/0/0 | — |
| V260 654993684f30 | copy_record · normal_json | 6; 6/0/0 | — |
| V261 8be52f7da5b1 | copy_record · id_keyed_arrays | 6; 6/0/0 | — |
| V262 addcb3979611 | copy_record · full_paths | 6; 6/0/0 | — |
| V263 311e5dc7d539 | copy_record_empty · normal_json | 6; 6/0/0 | — |
| V264 b9446d0f832a | copy_record_empty · id_keyed_arrays | 6; 6/0/0 | — |
| V265 9343b82809a2 | copy_record_empty · full_paths | 6; 6/0/0 | — |
| V266 eef9f85eaf4b | copy_value · normal_json | 6; 6/0/0 | — |
| V267 20a6d8b936ce | copy_value · id_keyed_arrays | 6; 0/6/0 | missing_or_non_json_collection_selector:6 |
| V268 e344c5d6b26e | copy_value · full_paths | 6; 6/0/0 | — |
| V269 0298fd72e491 | copy_value_empty · normal_json | 6; 6/0/0 | — |
| V270 5e322650a8a6 | copy_value_empty · id_keyed_arrays | 6; 0/6/0 | missing_or_non_json_collection_selector:6 |
| V271 a4346e2f4756 | copy_value_empty · full_paths | 6; 6/0/0 | — |
| V272 98d6d7594a41 | move_record · normal_json | 33; 27/6/0 | array_fields_without_operation_object:3; missing_or_non_json_collection_selector:3 |
| V273 978bb6aab3d4 | move_record · id_keyed_arrays | 33; 27/6/0 | array_fields_without_operation_object:3; missing_or_non_json_collection_selector:3 |
| V274 54c86cd5242b | move_record · full_paths | 33; 30/3/0 | array_fields_without_operation_object:3 |
| V275 3d7f8bee1c2f | move_record_empty · normal_json | 33; 24/9/0 | array_fields_without_operation_object:6; missing_or_non_json_collection_selector:3 |
| V276 4e8ac7451648 | move_record_empty · id_keyed_arrays | 33; 21/12/0 | array_fields_without_operation_object:6; missing_or_non_json_collection_selector:6 |
| V277 6c5456608aa3 | move_record_empty · full_paths | 33; 30/3/0 | array_fields_without_operation_object:3 |
| V278 34252e66594e | move_value · normal_json | 33; 30/3/0 | missing_or_non_json_collection_selector:3 |
| V279 ab957b7d0efc | move_value · id_keyed_arrays | 33; 24/9/0 | missing_or_non_json_collection_selector:9 |
| V280 e7204a1a9ef2 | move_value · full_paths | 33; 33/0/0 | — |
| V281 3a303efc52aa | move_value_empty · normal_json | 33; 30/3/0 | missing_or_non_json_collection_selector:3 |
| V282 6255c2848598 | move_value_empty · id_keyed_arrays | 33; 22/11/0 | array_fields_without_operation_object:2; missing_or_non_json_collection_selector:9 |
| V283 f4153fbea42b | move_value_empty · full_paths | 33; 33/0/0 | — |
| V284 c0ae164fec70 | no_change · normal_json | 33; 30/3/0 | javascript_dot_or_index_path_notation:3 |
| V285 ff9b1d739bc3 | no_change · id_keyed_arrays | 33; 30/3/0 | missing_or_non_json_collection_selector:3 |
| V286 681ed0835407 | no_change · full_paths | 33; 30/3/0 | unrequested_database_mutation_on_unrelated_information:3 |
| V287 a2fb360c7810 | remove_record · normal_json | 6; 6/0/0 | — |
| V288 ffcd56e7921f | remove_record · id_keyed_arrays | 6; 6/0/0 | — |
| V289 ad06c2fa0fab | remove_record · full_paths | 6; 6/0/0 | — |
| V290 f9c1f10bfc0d | remove_record_last · normal_json | 6; 6/0/0 | — |
| V291 d2494fc22564 | remove_record_last · id_keyed_arrays | 6; 6/0/0 | — |
| V292 af89108d500d | remove_record_last · full_paths | 6; 6/0/0 | — |
| V293 0e3cd55c16f2 | remove_value · normal_json | 6; 6/0/0 | — |
| V294 e38fdd0e744c | remove_value · id_keyed_arrays | 6; 0/6/0 | missing_or_non_json_collection_selector:6 |
| V295 42225cae768e | remove_value · full_paths | 6; 6/0/0 | — |
| V296 663ab81e67a8 | remove_value_last · normal_json | 6; 3/3/0 | missing_or_non_json_collection_selector:3 |
| V297 ca5c0c888ecf | remove_value_last · id_keyed_arrays | 6; 6/0/0 | — |
| V298 e513b5b3ad02 | remove_value_last · full_paths | 6; 6/0/0 | — |
| V299 fc82bfaa285e | update_field · normal_json | 33; 33/0/0 | — |
| V300 ac56e638022f | update_field · full_paths | 33; 33/0/0 | — |
| V301 df034951c5a2 | update_nested_collection · normal_json | 33; 30/3/0 | missing_or_misassigned_operation_fields:3 |
| V302 85855b58f8c0 | update_nested_collection · id_keyed_arrays | 33; 27/6/0 | missing_or_non_json_collection_selector:3; missing_or_misassigned_operation_fields:3 |
| V303 e77f2f110d6c | update_nested_collection · full_paths | 33; 33/0/0 | — |
| V304 3a0de1b931b7 | update_record · normal_json | 33; 27/6/0 | array_fields_without_operation_object:3; wrong_or_incomplete_object_field_path:3 |
| V305 236a7dba15e5 | update_record · id_keyed_arrays | 33; 27/6/0 | array_fields_without_operation_object:3; missing_or_non_json_collection_selector:3 |
| V306 d15fc0f77763 | update_record · full_paths | 33; 33/0/0 | — |
| V307 488047d15b4b | update_record_nested · normal_json | 33; 33/0/0 | — |
| V308 63256eba166f | update_record_nested · id_keyed_arrays | 33; 30/3/0 | missing_or_non_json_collection_selector:3 |
| V309 107ca99ea151 | update_record_nested · full_paths | 33; 33/0/0 | — |
| V310 17d7fda68d45 | copy_value · id_keyed_arrays | 3; 0/3/0 | missing_or_non_json_collection_selector:3 |
| V311 7d42b0f42286 | copy_value · id_keyed_arrays | 33; 24/9/0 | missing_or_non_json_collection_selector:6; operation_label_used_as_array_key:3 |
| V312 fc5d1879350d | copy_record · normal_json | 33; 26/7/0 | mixed_array_values_and_named_fields:1; operation_label_used_as_array_key:3; missing_or_non_json_collection_selector:3 |
| V313 417d0e764248 | copy_record · id_keyed_arrays | 33; 27/6/0 | operation_label_used_as_array_key:3; missing_or_non_json_collection_selector:3 |
| V314 b94d3dc6a3cb | copy_record · full_paths | 33; 30/3/0 | operation_label_used_as_array_key:3 |
| V315 8de0c83d408a | copy_record_empty · normal_json | 33; 27/6/0 | operation_label_used_as_array_key:3; missing_or_non_json_collection_selector:3 |
| V316 aad93d4451b6 | copy_record_empty · id_keyed_arrays | 33; 27/6/0 | operation_label_used_as_array_key:3; missing_or_non_json_collection_selector:3 |
| V317 1cba582cd3d9 | copy_record_empty · full_paths | 33; 30/3/0 | operation_label_used_as_array_key:3 |
| V318 908c6ef4408c | copy_value · normal_json | 33; 27/6/0 | array_fields_without_operation_object:3; missing_or_non_json_collection_selector:3 |
| V319 b56858aa21b9 | copy_value · full_paths | 33; 30/3/0 | array_fields_without_operation_object:3 |
| V320 cb1ddc55d61f | copy_value_empty · normal_json | 33; 30/3/0 | array_fields_without_operation_object:3 |
| V321 ef631aa9e43e | copy_value_empty · id_keyed_arrays | 33; 24/9/0 | missing_or_non_json_collection_selector:6; operation_label_used_as_array_key:3 |
| V322 3b67993b8b7c | copy_value_empty · full_paths | 33; 26/7/0 | mixed_array_values_and_named_fields:1; operation_label_used_as_array_key:3; path_descends_beyond_primitive_element:3 |
| V323 76214b806e75 | remove_value · id_keyed_arrays | 33; 27/6/0 | missing_or_non_json_collection_selector:3; empty_patch_misses_required_change:3 |
| V324 51092bb13880 | remove_record · normal_json | 33; 27/6/0 | array_fields_without_operation_object:3; empty_patch_misses_required_change:3 |
| V325 905f4ea51ddb | remove_record · id_keyed_arrays | 33; 27/6/0 | array_fields_without_operation_object:3; empty_patch_misses_required_change:3 |
| V326 d6324e523e6f | remove_record · full_paths | 33; 27/6/0 | array_fields_without_operation_object:3; empty_patch_misses_required_change:3 |
| V327 77bdcfbb9307 | remove_record_last · normal_json | 33; 30/3/0 | empty_patch_misses_required_change:3 |
| V328 bdc384473f7a | remove_record_last · id_keyed_arrays | 33; 27/6/0 | array_fields_without_operation_object:3; empty_patch_misses_required_change:3 |
| V329 484cc666779c | remove_record_last · full_paths | 33; 27/6/0 | array_fields_without_operation_object:3; empty_patch_misses_required_change:3 |
| V330 2647fbdc0b92 | remove_value · normal_json | 33; 30/3/0 | empty_patch_misses_required_change:3 |
| V331 9c7b49b2339d | remove_value · full_paths | 33; 25/8/0 | array_fields_without_operation_object:5; empty_patch_misses_required_change:3 |
| V332 329051df7fa8 | remove_value_last · normal_json | 33; 30/3/0 | empty_patch_misses_required_change:3 |
| V333 bd8a851d6ff8 | remove_value_last · id_keyed_arrays | 33; 30/3/0 | empty_patch_misses_required_change:3 |
| V334 a01ae7710b85 | remove_value_last · full_paths | 33; 27/6/0 | array_fields_without_operation_object:3; empty_patch_misses_required_change:3 |
| V335 4f53cda18c2b | move_record · full_paths | 1; 0/0/1 | technical_cancelled_partial:1 |

## Failure taxonomy and supporting excerpts

Primary counts are disjoint and sum to all non-pass observations. “Unique cases” below removes repetitions within a model/test/format/prompt version; calls and unique cases are different denominators. A primary error can mask later errors; tags preserve directly observed co-occurrence, without claiming unexecuted semantics.

| Observed mechanism | Observations | Unique cases | Models | Formats / operations |
| --- | --- | --- | --- | --- |
| Bare string collection selector | 1285 | 409 | 9 | full_paths,id_keyed_arrays,normal_json / copy,move,no_change,remove,update |
| Source ID used as the whole path | 183 | 61 | 5 | full_paths,id_keyed_arrays,normal_json / copy,move |
| Markdown instead of the required raw JSON document | 121 | 41 | 3 | full_paths,id_keyed_arrays,normal_json / append,copy,move,no_change,remove,update |
| Invalid outer JSON escaping | 78 | 30 | 5 | full_paths,id_keyed_arrays,normal_json / copy,move,no_change,remove,update |
| Operation fields placed directly inside [] | 70 | 24 | 2 | full_paths,id_keyed_arrays,normal_json / copy,move,remove,update |
| Required change omitted | 39 | 13 | 2 | full_paths,id_keyed_arrays,normal_json / append,remove |
| Operation label used as an array key | 27 | 9 | 1 | full_paths,id_keyed_arrays,normal_json / copy |
| Remove selects the collection or uses from | 25 | 9 | 4 | full_paths,id_keyed_arrays,normal_json / remove |
| Retired redundant-assignment NOOP design confound | 21 | 7 | 3 | full_paths,id_keyed_arrays,normal_json / no_change |
| Unsupported operation token | 9 | 3 | 1 | id_keyed_arrays / append |
| Dot/bracket/index notation | 9 | 3 | 1 | id_keyed_arrays,normal_json / no_change |
| Wrong allowed operation / source preservation semantics | 6 | 2 | 1 | full_paths / copy |
| Unrelated information causes a database mutation | 6 | 2 | 1 | full_paths / no_change |
| Missing/misassigned fields | 6 | 2 | 1 | id_keyed_arrays,normal_json / update |
| Incomplete/wrong absolute field path | 4 | 2 | 2 | id_keyed_arrays,normal_json / update |
| Wrong selector value/type | 3 | 1 | 1 | normal_json / update |
| Path continues below a primitive | 3 | 1 | 1 | full_paths / copy |
| Mixed array values and named fields | 2 | 2 | 1 | full_paths,normal_json / copy |
| Benchmark execution timeout | 7 | 3 | 2 | id_keyed_arrays,normal_json / append,no_change |
| Browser execution context lost | 1 | 1 | 1 | full_paths / append |
| Interrupted partial attempt | 1 | 1 | 1 | full_paths / move |

### Bare string collection selector — 1285 observations

The output identifies a plausible element but omits the selector's JSON quotes, e.g. /items/item-17/count. Outer JSON can be valid while the custom path is invalid.

Possible intervention: Prompt: distinguish logical selector serialization from outer JSON encoding. Parser: keep strict typed selection. A future different output format could represent path parts as typed values; that is a new method, not a retrospective repair.

Example: `3b47f5d8e236fcb18d51e3aba9196857738a308fdc710761848fe017e3ca5204`; Desktop Qwen3.5-2B Q8_0; `db_v3_remove_record_last__value_patch`; `normal_json`; repetition 1; prompt `ae6d83c4769bdc852876d5ea0c1798cecdddebce0ba7f9e646f50c2531d8de97`.

Actual submitted text:
```text
[{"op":"remove","path":"/items/item-83"}]
```

Saved validation error: `An array path part must be a JSON scalar value, not an index or unquoted string`. Required operations: `['remove']`; actual operations: `['remove']`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\desktop-current-prompts-run\retired-pre-promotion-results\results\local-2542aed68e6bb077\01de1323d582c015912a0a741d13287eae549cb96430e74bceb2679204a602b3.json` JSON pointer `/`.


### Source ID used as the whole path — 183 observations

The from field contains item-17 or town-a without its collection and leading slash.

Possible intervention: Prompt: construct from the root, including the source collection. Parser must not infer missing collections.

Example: `bb12846d33957158a1bad9c7dc6803c9b7fa0302a289b692aea562bd68a21e1b`; Desktop Qwen3.5-2B Q8_0; `db_v3_move_value_empty__value_patch`; `normal_json`; repetition 1; prompt `7d6718a5149cb5321924c93ead28b1175386101f5f98721406dae3c9e901ffdc`.

Actual submitted text:
```text
[{"op":"move","from":"town-a","path":"/archived_locations"}]
```

Saved validation error: `A value path must be empty or start with /`. Required operations: `['move']`; actual operations: `['move']`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\desktop-current-prompts-run\retired-pre-promotion-results\results\local-2542aed68e6bb077\088ce9f1794b35fa72fab4bae09217923f500b1de57e7ec4dd11d074d4fe11cc.json` JSON pointer `/`.


### Markdown instead of the required raw JSON document — 121 observations

The response starts with a code fence. The official scorer rejects the whole text. This category does not imply that the fenced body would pass.

Possible intervention: Prompt: raw JSON only. A lenient transport wrapper would be an explicit parser-policy change and cannot change these historical scores.

Example: `96a4e6486d0f8e00e43b0dc246a4b0b83c16e0fdecfb9fe1266ea9c07e4e7a14`; Perchance Text Generator (remote model unspecified); `db_v3_no_change__value_patch`; `normal_json`; repetition 2; prompt `88e3c84243db70451d8477d1f49633f3354e04107b388124597a81471cc33af6`.

Actual submitted text:
```text
```json
[
  {
    "op": "replace",
    "path": "/items/\"item-83\"/count",
    "value": 2
  }
]
```
```

Saved validation error: `Expecting value: line 1 column 1 (char 0)`. Required operations: `[]`; actual operations: `[]`. Expected state: unchanged input.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\final-current-perchance-run\historical-results\7d6b5435f080a4b05220a06a8e0f1432fd559e6ad4c4b5a8e253eedbd4311906.json` JSON pointer `/`.


### Invalid outer JSON escaping — 78 observations

The quotes around a selector are not correctly escaped inside the operation JSON string; the complete response cannot be parsed.

Possible intervention: Prompt: separate the two serialization steps. A future structured output interface could enforce outer JSON, with independent validation of inner paths.

Example: `ce25f7398518f5bdf70e885a3c5483ea7721122b1c944bd6e8eaecef532884cb`; Desktop Qwen3.5-4B Q8_0; `db_v3_remove_record_last__value_patch`; `normal_json`; repetition 1; prompt `ae6d83c4769bdc852876d5ea0c1798cecdddebce0ba7f9e646f50c2531d8de97`.

Actual submitted text:
```text
[{"op": "remove", "path": "/items/"item-83"}]
```

Saved validation error: `Expecting ',' delimiter: line 1 column 36 (char 35)`. Required operations: `['remove']`; actual operations: `[]`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\desktop-current-prompts-run\retired-pre-promotion-results\results\local-28df315996a77e69\03d21a2ded0405cbfc0b09abf2d7259bdd54513a846f7cf40756ca8b880c6422.json` JSON pointer `/`.


### Operation fields placed directly inside [] — 70 observations

The output begins ["op": ...] and omits the object braces around an operation.

Possible intervention: Prompt/output format: require an array whose elements are objects; structured JSON output could address syntax. No silent brace repair.

Example: `efc0ddb6094e22fb4a23df4ec8138c95495298bec1a17db69c8876affba484d3`; Desktop Qwen3.5-4B Q8_0; `db_v3_move_record_empty__value_patch`; `full_paths`; repetition 0; prompt `16b4df4df90580c5b66d005ebaeb81e7a167314f7e06746afa5156f812b4add6`.

Actual submitted text:
```text
["op":"move","from":"item-17","path":"/storage"]
```

Saved validation error: `Expecting ',' delimiter: line 1 column 6 (char 5)`. Required operations: `['move']`; actual operations: `[]`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\desktop-current-prompts-run\retired-pre-promotion-results\results\local-28df315996a77e69\4cc59118c8c12408a823079f96a5f7b2e5e09bbd0eddf81a99b442154997f60e.json` JSON pointer `/`.


### Required change omitted — 39 observations

The model returns [] for a task whose expected state differs from the input.

Possible intervention: Prompt: distinguish genuinely irrelevant information from a required change, including transfers into an empty destination. This is a semantic failure.

Example: `f6a20e4d83a270a3c636dd218d8611ad7e5cdc1f5723ee02a299b94dfaf9ea41`; Desktop Qwen3.5-4B Q8_0; `db_v3_append_value_empty__value_patch`; `id_keyed_arrays`; repetition 2; prompt `0b040eea2330dbe7e1aa2fbde2308df23b12fc72c7718631d38b62ee079bad4e`.

Actual submitted text:
```text
[]
```

Saved validation error: `None`. Required operations: `['add']`; actual operations: `[]`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\final-other-local-run\final-other-local-evidence.tar.gz!results/local-28df315996a77e69/832ac0296ca973e03b64fd5f61f58246e83e51889546e2a1909b8a562fd8efe8.json` JSON pointer `/`.


### Operation label used as an array key — 27 observations

The model starts ["copy": {...}] or equivalent. Arrays cannot contain named members.

Possible intervention: Prompt/output format: retain the five operation objects and explicitly distinguish op from the array container.

Example: `045f132117e1030803adf7958149b4b66cf77e51187fde3999ba8d1191f0dad1`; Desktop Qwen3.5-4B Q8_0; `db_v3_copy_value_empty__value_patch`; `full_paths`; repetition 2; prompt `3b67993b8b7c0d4b1f8ad18d46da4cee8c1096da93ed2f6d6b405837e75e8120`.

Actual submitted text:
```text
["copy":{"op":"copy","from":"/locations/\"town-a\"","path":"/archived_locations"}}]
```

Saved validation error: `Expecting ',' delimiter: line 1 column 8 (char 7)`. Required operations: `['copy']`; actual operations: `[]`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\final-other-local-run\final-other-local-evidence.tar.gz!results/local-28df315996a77e69/0e8051f742b1d966e237f797a8cd1f6b0195576a1679ba347b5c8baaaf4f9e78.json` JSON pointer `/`.


### Remove selects the collection or uses from — 25 observations

The model uses path /locations and from town-a for Remove, instead of selecting the element in path.

Possible intervention: Prompt: Remove uses path to select the element; from is for Move/Copy.

Example: `aaa2988ccf14905a09c83a6a64b579b3b05321cca2e95c58b599bf811d3192ed`; Desktop Qwen3.5-4B Q8_0; `db_v3_remove_value_last__value_patch`; `normal_json`; repetition 0; prompt `f25c1c1b3840bd34d986bfdc1bd21dea9543632b20ae3ad5977c91834fb4f1d5`.

Actual submitted text:
```text
[{"op": "remove", "path": "/locations", "value": "town-a"}]
```

Saved validation error: `Remove path must select a collection element`. Required operations: `['remove']`; actual operations: `['remove']`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\desktop-current-prompts-run\retired-pre-promotion-results\results\local-28df315996a77e69\69db6437e4745ecca89b58d9f71e992d60c9736609744aa075b14805b2115b26.json` JSON pointer `/`.


### Retired redundant-assignment NOOP design confound — 21 observations

The old task explicitly requested setting a field to its already-current value while requiring an empty operation list. A redundant replace leaves the same state but fails the required-operation contract.

Possible intervention: Test design: separate this retired ambiguity from the revised unrelated-information NOOP. Preserve original failures and prompt hashes; do not reinterpret them as current NOOP failures.

Example: `7195e022a03bc176d394ec0ac886781353b760f9686b84115004309bb3a686ff`; Desktop Qwen3.5-2B Q8_0; `db_v3_no_change__value_patch`; `full_paths`; repetition 2; prompt `7eaa2a610fa97de67890b0f8347f0d9ac1e3eb43ad1fed693115583c07aa2428`.

Actual submitted text:
```text
[{"op":"replace","path":"/items/\"item-83\"/count","value":2}]
```

Saved validation error: `None`. Required operations: `[]`; actual operations: `['replace']`. Expected state: unchanged input.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\noop-unrelated-run\retired-active-results\desktop\results\local-2542aed68e6bb077\052705218d1e37b8f3c1e7827a7eaf525a5cc08498c4c551ba50801dfb194636.json` JSON pointer `/`.


### Unsupported operation token — 9 observations

For example append is emitted although the Append operation is encoded with op add.

Possible intervention: Prompt: keep the natural-language name and literal token mapping explicit. A new format could use different tokens only prospectively.

Example: `d7fc7544439147f76093cb11358515fbd840323dfba3bc23d121b5e26186f5d1`; Desktop Qwen3.5-4B Q8_0; `db_v3_append_value_empty__value_patch`; `id_keyed_arrays`; repetition 2; prompt `c017ef348ecad17bfa0542e6f04a44813c9ec43983afe58ec2062a5368a52d50`.

Actual submitted text:
```text
[{"op": "append", "path": "/locations", "value": "town-a"}]
```

Saved validation error: `Allowed operations are replace, add, remove, move and copy`. Required operations: `['add']`; actual operations: `['append']`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\desktop-current-prompts-run\retired-pre-promotion-results\results\local-28df315996a77e69\017788d3c78c9a4567d38fedc2215c65fbab91e140f40e5926d548b2ac3ed91e.json` JSON pointer `/`.


### Dot/bracket/index notation — 9 observations

The model emits items[0].name or items.item-42.name instead of the specified value path. Some are also unrelated NOOP mutations.

Possible intervention: Prompt: distinguish display/schema from permitted output path grammar. Do not activate positional selection to accommodate these outputs.

Example: `b62ffdcead390b0ca402d1285d00c52a9f9a39505c6dd4c5416c651646399819`; Desktop Qwen3.5-2B Q8_0; `db_v3_no_change__value_patch`; `id_keyed_arrays`; repetition 1; prompt `29981703e63f384f4c8bf6110780e4c0920f8425cae9b276421dbc3e6198ac91`.

Actual submitted text:
```text
[{"op":"replace","path":"items.item-42.name","value":"Blue"}]
```

Saved validation error: `A value path must be empty or start with /`. Required operations: `[]`; actual operations: `['replace']`. Expected state: unchanged input.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\final-other-local-run\before\results\local-2542aed68e6bb077\58ee3aa9483d4771baf7416e76f7e0507bab9ab321f20e1f2ded2ee2032a1581.json` JSON pointer `/`.


### Wrong allowed operation / source preservation semantics — 6 observations

A supported operation is syntactically valid but differs from the required task, for example Move instead of Copy or Add instead of Copy. Some saved final states can match while the explicit operation contract fails.

Possible intervention: Prompt: distinguish Move source removal, Copy source preservation, and the required direct operation. Keep method-contract failures distinct from state-only mismatches.

Example: `d2bd96ae522073ad5ea821a743e5b1b6988b285545d0a22c32d10f90a732f299`; Desktop Qwen3.5-2B Q8_0; `db_v3_copy_value_empty__value_patch`; `full_paths`; repetition 2; prompt `dfa547306eca71064019b4d40f2419f3850cf9d19a5126ba3b110aa9ab368b8e`.

Actual submitted text:
```text
[{"op":"move","from":"/locations/\"town-a\"","path":"/archived_locations"}]
```

Saved validation error: `None`. Required operations: `['copy']`; actual operations: `['move']`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\desktop-current-prompts-run\retired-pre-promotion-results\results\local-2542aed68e6bb077\241ff810adc39eedcdd01fc2f0c4845efc9c53cea705db6349dd32b2fc0ac9a7.json` JSON pointer `/`.


### Unrelated information causes a database mutation — 6 observations

The revised NOOP task concerns presentation information outside the fixed database, but the model changes a database field.

Possible intervention: Prompt: preserve database fields when the information requests no database change. This is a task/schema interpretation failure.

Example: `d9e57cea6459226c74b188471910c85d38fab75fec7b0f469aabc15378d83f56`; Desktop Qwen3.5-2B Q8_0; `db_v3_no_change__value_patch`; `full_paths`; repetition 0; prompt `7e1ffc312ff282f33c3cc9e5fc3cb8a7e58b9cf504ee3bb8073089a083670edf`.

Actual submitted text:
```text
[{"op":"replace","path":"/items/\"item-42\"/name","value":"Blue"}]
```

Saved validation error: `None`. Required operations: `[]`; actual operations: `['replace']`. Expected state: unchanged input.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\final-other-local-run\before\results\local-2542aed68e6bb077\15260bdb952b74129a7de56b2f786dc105d23e3b9aad65365e31dcdd4f73dbba.json` JSON pointer `/`.


### Missing/misassigned fields — 6 observations

A required path, from or value is absent or placed in the wrong field, including replace with from.

Possible intervention: Prompt: concise per-operation field roles. Parser should report the field and operation that failed.

Example: `098a272eaffcf227f58c84cb23a660d0cddd475ae658677217cb4df492cd5780`; Desktop Qwen3.5-2B Q8_0; `db_v3_update_nested_collection__value_patch`; `normal_json`; repetition 1; prompt `df034951c5a2b4ff1a17fde1d8599f99f2df0b6f2445c2427fa1b4f7273ca5a1`.

Actual submitted text:
```text
[{"op":"replace","from":"/workspace/inventory/items/item-26/count","value":7}]
```

Saved validation error: `Operation requires a string path and its value/from fields`. Required operations: `['replace']`; actual operations: `['replace']`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\final-other-local-run\final-other-local-evidence.tar.gz!results/local-2542aed68e6bb077/0f1298af959a5667113b4c27bfeaaa9443a41cd23b7e71bcf8b946102a288136.json` JSON pointer `/`.


### Incomplete/wrong absolute field path — 4 observations

The output splits an Update into from /items/item-17 plus path /count, or selects a nonexistent property.

Possible intervention: Prompt: an Update path includes the root, collection, element selector and relative field suffix.

Example: `f9f7367f6498c5e5e4516d886c93140ad2f3f3a1871fa22b7f8eeecbb9817704`; Perchance Text Generator (remote model unspecified); `db_v3_update_nested_collection__value_patch`; `id_keyed_arrays`; repetition 0; prompt `86b486ce17a547458600ea6b29355228f3cebf924c4324117b73fb32426c38ce`.

Actual submitted text:
```text
[
  {
    "op": "replace",
    "path": "/workspace/inventory/items \"item-26\"/count",
    "value": 7
  }
]
```

Saved validation error: `Missing or undefined property: items "item-26"`. Required operations: `['replace']`; actual operations: `['replace']`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\final-current-perchance-run\historical-results\6f4853fde7113802e5c84bc9f759dc90321e2280460dc41aaaae67c2cc830bc0.json` JSON pointer `/`.


### Wrong selector value/type — 3 observations

Observed form selects numeric 17 where the schema/data identify the element by string item-17; the selector matches zero elements.

Possible intervention: Prompt: preserve the full literal ID and its JSON type. Parser behavior is consistent with typed selection.

Example: `2f7e8f53ffe7a8f0693b8c06d1c42e582a6d6ef52c07f03836f2c847d9d45822`; Desktop Qwen3.5-2B Q8_0; `db_v3_update_record_nested__value_patch`; `normal_json`; repetition 0; prompt `7c4420933d958baeff36a3b737d5f412b2cb4d58e09f4eb3fe34ebb47c14344c`.

Actual submitted text:
```text
[{"op":"replace","path":"/items/17/details/durability","value":80}]
```

Saved validation error: `Collection selector 17 must match exactly one element; found 0`. Required operations: `['replace']`; actual operations: `['replace']`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\desktop-current-prompts-run\retired-pre-promotion-results\results\local-2542aed68e6bb077\5930ef367a55c95fdb50740f44dd5b6665fad310b038334db750969431d4e75a.json` JSON pointer `/`.


### Path continues below a primitive — 3 observations

A source such as /locations/"town-a"/town-a selects the primitive and then tries to descend through it.

Possible intervention: Prompt: whole-element sources stop at the primitive selector; the value has no child fields.

Example: `6b3e2201965ae7a757622edd4efb93a5eeffb719ab1d91fa3e580481cf94af4c`; Desktop Qwen3.5-2B Q8_0; `db_v3_copy_value_empty__value_patch`; `full_paths`; repetition 2; prompt `3b67993b8b7c0d4b1f8ad18d46da4cee8c1096da93ed2f6d6b405837e75e8120`.

Actual submitted text:
```text
[{"op":"copy","from":"/locations/\"town-a\"/town-a","path":"/archived_locations"}]
```

Saved validation error: `Value path continues through a scalar`. Required operations: `['copy']`; actual operations: `['copy']`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\final-other-local-run\final-other-local-evidence.tar.gz!results/local-2542aed68e6bb077/765ee67c7bc911ff7b4cec8f51f8afa6b7767a35e81dd68b8fdeb6b286a3f9d1.json` JSON pointer `/`.


### Mixed array values and named fields — 2 observations

The model emits ["copy", "from": ..., "path": ...], combining a string array element and object fields.

Possible intervention: Prompt/output format: each operation is one object with op/from/path fields.

Example: `16939bea8244acb3ff63525f7a05589d34ae969120d8e648650d6881bd69216c`; Perchance Text Generator (remote model unspecified); `db_v3_copy_record__value_patch`; `normal_json`; repetition 2; prompt `fc5d1879350d1f71855d1a450ad4043be689a503ec4a171f3fe115faadb41ec4`.

Actual submitted text:
```text
["copy", "from": "/items/\"item-17\"", "path": "/storage"]
```

Saved validation error: `Expecting ',' delimiter: line 1 column 16 (char 15)`. Required operations: `['copy']`; actual operations: `[]`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\final-current-perchance-run\repo\results\perchance-text-generator\24ba50064ee870404e319f5cdba9867b6a18231a15af94275e170de0283e7270.json` JSON pointer `/`.


### Benchmark execution timeout — 7 observations

The saved workflow reached its benchmark watchdog. It is an execution outcome, not an incorrect completed answer.

Possible intervention: Runtime diagnosis only; no selective retries. Preserve the terminal deadline and partial evidence.

Example: `90a6933ef3c276657d19a1a8cebe38d0c1fc4cc7d4e560ceef7c171a2e467f29`; Unity Qwen3.5-27B UD-IQ2_XXS (Unsloth); `db_v3_no_change__value_patch`; `id_keyed_arrays`; repetition 0; prompt `a617d1007beb6e6a498fe32305447e9a2ec094e2c9ef48213f27bc6caccd3f0c`.

Actual submitted text:
```text
The user wants me to perform a database update based on a specific instruction.

**Instruction Analysis:**
1.  **Target Collection:** `/items`
2.  **Target Element:** The element with `item_id` value "item-83".
3.  **Action:** Set the existing field at relative path `/count` to `2`.
4.  **Current State:**
    *   `item-83` currently has `count`: 2.
    *   The instruction asks to set it to 2.

**Verification:**
*   Current value of `item-83`'s `count` is 2.
*   New value requested is 2.
*   Since the value is already 2, no change is technically needed to the data state. However, the instruction says "Set its existing field... to 2". In database operations, if the value is already the target value, an update operation might still be generated to reflect the instruction, or it might be considered a no-op.
*   Looking at the prompt's constraints: "Use the new information to determine what changes, if any, are needed in the current data."
*   If the value is already 2, setting it to 2 results in no change.
*   However, usually, if an instruction explicitly says "Set X to Y", and X is already Y, the operation is valid but redundant.
*   Let's check the current data again.
    *   `"item-83": { "item_id": "item-83", "name": "Potion", "count": 2 }`
*   The instruction says: "Set its existing field at relative path '/count' to 2".
*   Current value: 2. New value: 2.
*   Strictly speaking, no change is needed.
*   However, sometimes these tasks expect the operation to be performed regardless. But the prompt says "determine what changes, if any, are needed". If the value is already correct, no change is needed.
*   Wait, let me re-read the instruction carefully. "Set its existing field at relative path '/count' to 2".
*   Is it possible the user made a typo and meant a different value? No, I must follow the instruction.
*   If the instruction says "Set count to 2" and count is already 2, the database state does not change.
*   Therefore, the array of operations should be empty `[]`.

Let's double check if I missed anything.
Current data:
```json
{
  "items": {
    "item-42": { "item_id": "item-42", "name": "Sword", "count": 3 },
    "item-17": { "item_id": "item-17", "name": "Sword", "count": 8 },
    "item-83": { "item_id": "item-83", "name": "Potion", "count": 2 },
    "item-26": { "item_id": "item-26", "name": "Shield", "count": 6 }
  }
}
```
Target: `item
```

Saved validation error: `Timed out after 120 seconds`. Required operations: `None`; actual operations: `None`. Expected state: unchanged input.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\unity-12gb-run\evidence-27b\repo-27b\results\qwen35-27b-ud-iq2_xxs\09cfc9236f68dd0d4d3ab0e5e03c8665a1658a0d0fffc4442836e51e7780f0c6.json` JSON pointer `/`.


### Browser execution context lost — 1 observations

Perchance Frame.evaluate failed because navigation destroyed the execution context; no completed text was saved.

Possible intervention: Provider/transport issue. The explicitly authorized recovery attempt is a separate call, never a copied success.

Example: `ff0ac07c27911815bde90faca89617e5cfeb1e272cd89a4039a816e91235cc24`; Perchance Text Generator (remote model unspecified); `db_v3_append_record__value_patch`; `full_paths`; repetition 0; prompt `b18ce33ac3da048141876d6a9d312e0d0c20043e9e9f11d817918d870beaaf77`.

Actual submitted text:
```text

```

Saved validation error: `Frame.evaluate: Execution context was destroyed, most likely because of a navigation`. Required operations: `None`; actual operations: `None`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\final-current-perchance-run\infrastructure-recovery\original-error.json` JSON pointer `/`.


### Interrupted partial attempt — 1 observations

An explicitly stopped driver left a partial attempt, later resumed by the normal driver.

Possible intervention: Preserve the partial attempt and completed replacement separately; do not count the partial as a completed model failure.

Example: `449229cc0ac0d0de70ed977a0f56df8a910485a6af4006f10a34ab24a73fb0e1`; Desktop Qwen3.5-2B Q8_0; `db_v3_move_record__value_patch`; `full_paths`; repetition 2; prompt `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.

Actual submitted text:
```text
None
```

Saved validation error: `Stopped`. Required operations: `None`; actual operations: `None`. Expected state: changed as recorded in the complete evidence JSONL.

Source: `C:\Users\Isaac\Documents\Codex\2026-10-15\task-3\final-other-local-run\final-other-local-evidence.tar.gz!results/local-2542aed68e6bb077/e4e06c6ff5e529eaf253d4bafcf1abdf8699e6788aa46347c12b35b50ad1d0e5.json` JSON pointer `/attempts/0`.

## Original Q4_K_M review and the small clarification

Exact model: desktop `local-81e2a88130ccfa4e`, `Qwen3.5-9B-Q4_K_M.gguf`, original session `f60401dbfced4faba95bd7c73b1e41f1`. Coverage: 186 completed observations, 62 test/format cases × three repetitions; 138 failures read, 48 passes retained as controls. Original failure mechanisms: missing_or_non_json_collection_selector=135, wrong_remove_selection_level_or_field_role=3.

The clean original candidate is `db_v3_update_record__value_patch`, Normal JSON, repetition 0. Task excerpt: “In the collection at "/items", find the element whose "item_id" value is "item-17". Set its existing field at relative path "/count" to 9. A relative path starts at that element.” The original instruction already said “Strings must include their JSON quotation marks and normal JSON escaping” and “A path is itself a JSON string in the output operation. Escape its internal quotation marks and backslashes as required by JSON.”

Actual response:
```json
[{"op":"replace","path":"/items/item-17/count","value":9}]
```
Saved error: `An array path part must be a JSON scalar value, not an index or unquoted string`. Expected change: only item-17 count 8→9; all other fields/elements unchanged. The response selects the intended collection, ID, field, operation and value, but loses the required quotes around the string selector. That makes instruction/serialization clarity a plausible optimization target; it is not evidence that the evaluator should accept the submitted path.

One small proposed clarification, without a fixture-specific expected patch: **“Construct the value path first, keeping the double quotes around every string collection selector; then JSON-encode the entire path for the path or from field. After decoding that outer JSON string, the selector must still contain its own double quotes.”** This retrospective makes no prompt edit. Later OPRO evidence is reported separately and does not replace this original example.

Strong alternatives were whole-element Move/Copy sources (the same quote loss in from), and malformed outer operation arrays. Genuine wrong operations/omitted changes are weaker first clarity candidates because they involve task semantics as well as representation.

## Saved OPRO candidate evaluations

These are selected candidate trials on the existing benchmark model, not full-suite regressions and not Codex benchmark accuracy. Codex was the prompt writer. Writer requests/responses and candidate feedback are provenance; only raw trial calls enter the observation counts. Short-circuited candidates retain their untested coverage gaps. Baseline references in session summaries can point to an existing observation and are not automatically fresh calls.

| Session | Target | Raw trials / outcomes | Candidate attempts (saved scope score) |
| --- | --- | --- | --- |
| 047d4c1e920e4eae9e5c47c28b7dfbf5 | {'definition_id': '78d900f51e67a85f6fc07310b76f5842d4a5e14e257382fbb34428b47a24bcdc', 'test_id': 'db_v3_remove_value__value_patch', 'variant_id': 'id_keyed_arrays'} | 72 / {'PASS': 69, 'FAIL': 3} | 1: complete, 36/36 recorded; required 36 |
| 066ea62ce6bc4dcc8780ee60f6664032 | {'definition_id': '04ec5b8e1f7b05a2c85256cf6b076829e776cdde911ed6e6d122f8c59bff445f', 'test_id': 'db_v3_copy_value__value_patch', 'variant_id': 'id_keyed_arrays'} | 75 / {'FAIL': 9, 'PASS': 66} | 1: origin_failed, 0/3 recorded; required 36; 2: complete, 36/36 recorded; required 36 |
| 06bf576e9de6443bbfa7c04610cfa7bb | {'definition_id': '484b0b712bd87644c96957168f631c7b30cba75ba6667f6ef2eaee27d4cf1308', 'test_id': 'db_v3_update_record__value_patch', 'variant_id': 'normal_json'} | 99 / {'FAIL': 30, 'PASS': 69} | 1: complete, 24/33 recorded; required 33; 2: complete, 33/33 recorded; required 33 |
| 0bd9ed24ccc846b297812264855f167e | {'definition_id': '820a953b86d08a7d5c884d7bb10b3b47a939ecc0068b1f18f0a8a1885065f357', 'test_id': 'db_v3_move_record__value_patch', 'variant_id': 'normal_json'} | 144 / {'PASS': 102, 'FAIL': 42} | 1: complete, 33/36 recorded; required 36; 2: complete, 30/36 recorded; required 36; 3: complete, 36/36 recorded; required 36 |
| 893b170b5e6c42ddab7ca30354fde02f | {'definition_id': '47fe16c91e51e86d042131e5863de1b4300a0e19ae5d865ba6d587d3d9cdfa28', 'test_id': 'db_v3_update_record__value_patch', 'variant_id': 'full_paths'} | 33 / {'FAIL': 21, 'PASS': 12} | no candidate attempt |

Reviewed winners: Update session `06bf576e9de6443bbfa7c04610cfa7bb` attempt 2; Move `0bd9ed24ccc846b297812264855f167e` attempt 3; Copy `066ea62ce6bc4dcc8780ee60f6664032` attempt 2; Remove `047d4c1e920e4eae9e5c47c28b7dfbf5` attempt 1. Shared guidance was adapted into the normal builder rather than claiming byte-for-byte winner reuse everywhere; Copy/Remove have their operation-specific winners. Full candidate hashes, exact sent prompts and session sources are retained in the summary/registry. The final manifest SHA256 is `c4d63783b40c1352a769ac548ce1beff36c39d9eaacb58dfe69642e0e5bdb0d3`.

## Coverage by saved run/session

The 177-observation runs exclude the separately revised nine NOOP observations. Their combined 186 totals must be explicitly assembled; neither is silently presented as a fresh full regression. Unity baselines, promoted runs and final runs have separate sessions. This table includes every collected model/session/kind group; exact version membership remains in the inventory.

| Model / provider | Session / kind | Obs · unique test/format cases | PASS / FAIL / technical | Reps |
| --- | --- | --- | --- | --- |
| Desktop Qwen3.5-2B Q8_0 | 130078f07bc14e4fa5c056d47924b490 / benchmark | 177 · 59 | 87 / 90 / 0 | 0,1,2 |
| Desktop Qwen3.5-2B Q8_0 | 4de75d091ec74122806daeed366e6657 / benchmark | 106 · 36 | 28 / 78 / 0 | 0,1,2 |
| Desktop Qwen3.5-2B Q8_0 | 6fc7c41137ec48e1bc092c6e32d9ddc7 / benchmark | 81 · 27 | 50 / 30 / 1 | 0,1,2 |
| Desktop Qwen3.5-2B Q8_0 | 9a369b3662a44d3c9f180c1cde1cbac6 / benchmark | 9 · 3 | 0 / 9 / 0 | 0,1,2 |
| Desktop Qwen3.5-2B Q8_0 | f60401dbfced4faba95bd7c73b1e41f1 / benchmark | 186 · 62 | 63 / 123 / 0 | 0,1,2 |
| Desktop Qwen3.5-4B Q8_0 | 130078f07bc14e4fa5c056d47924b490 / benchmark | 177 · 59 | 174 / 3 / 0 | 0,1,2 |
| Desktop Qwen3.5-4B Q8_0 | 6fc7c41137ec48e1bc092c6e32d9ddc7 / benchmark | 186 · 62 | 99 / 87 / 0 | 0,1,2 |
| Desktop Qwen3.5-4B Q8_0 | 9a369b3662a44d3c9f180c1cde1cbac6 / benchmark | 9 · 3 | 9 / 0 / 0 | 0,1,2 |
| Desktop Qwen3.5-4B Q8_0 | f60401dbfced4faba95bd7c73b1e41f1 / benchmark | 186 · 62 | 51 / 135 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_M | 047d4c1e920e4eae9e5c47c28b7dfbf5 / opro_trial | 72 · 12 | 69 / 3 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_M | 066ea62ce6bc4dcc8780ee60f6664032 / opro_trial | 75 · 12 | 66 / 9 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_M | 06bf576e9de6443bbfa7c04610cfa7bb / opro_trial | 99 · 11 | 69 / 30 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_M | 0bd9ed24ccc846b297812264855f167e / opro_trial | 144 · 12 | 102 / 42 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_M | 130078f07bc14e4fa5c056d47924b490 / benchmark | 177 · 59 | 90 / 87 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_M | 54ea2231f710429d870e5bb054cdbd33 / benchmark | 186 · 62 | 174 / 12 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_M | 893b170b5e6c42ddab7ca30354fde02f / opro_trial | 33 · 11 | 12 / 21 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_M | 9a369b3662a44d3c9f180c1cde1cbac6 / benchmark | 9 · 3 | 9 / 0 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_M | db2eb3a9f9904299a6c9bab251e42a7f / benchmark | 186 · 62 | 186 / 0 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_M | f60401dbfced4faba95bd7c73b1e41f1 / benchmark | 186 · 62 | 48 / 138 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_S | 0006d379e8034c8b95a72a136c2097a4 / benchmark | 186 · 62 | 45 / 141 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_S | 130078f07bc14e4fa5c056d47924b490 / benchmark | 177 · 59 | 126 / 51 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_S | 4de75d091ec74122806daeed366e6657 / benchmark | 186 · 62 | 186 / 0 / 0 | 0,1,2 |
| Desktop Qwen3.5-9B Q4_K_S | 9a369b3662a44d3c9f180c1cde1cbac6 / benchmark | 9 · 3 | 9 / 0 / 0 | 0,1,2 |
| Desktop Qwen3-VL-8B-Instruct Q4_K_M | 130078f07bc14e4fa5c056d47924b490 / benchmark | 177 · 59 | 151 / 26 / 0 | 0,1,2 |
| Desktop Qwen3-VL-8B-Instruct Q4_K_M | 6fc7c41137ec48e1bc092c6e32d9ddc7 / benchmark | 186 · 62 | 164 / 21 / 1 | 0,1,2 |
| Desktop Qwen3-VL-8B-Instruct Q4_K_M | 9a369b3662a44d3c9f180c1cde1cbac6 / benchmark | 9 · 3 | 9 / 0 / 0 | 0,1,2 |
| Desktop Qwen3-VL-8B-Instruct Q4_K_M | f60401dbfced4faba95bd7c73b1e41f1 / benchmark | 186 · 62 | 42 / 144 / 0 | 0,1,2 |
| Perchance Text Generator (remote model unspecified) | provider-current / benchmark | 187 · 62 | 174 / 12 / 1 | 0,1,2 |
| Perchance Text Generator (remote model unspecified) | provider-original / benchmark | 186 · 62 | 169 / 17 / 0 | 0,1,2 |
| Unity Qwen3.5-27B IQ2_M (Bartowski) | 2134239622f4437fbfa32767f87e989d / benchmark | 9 · 3 | 9 / 0 / 0 | 0,1,2 |
| Unity Qwen3.5-27B IQ2_M (Bartowski) | 569edb88b72842c09ca78a3026deb28a / benchmark | 186 · 62 | 186 / 0 / 0 | 0,1,2 |
| Unity Qwen3.5-27B IQ2_M (Bartowski) | d11ca9e35d4f462cae3d222d578ae718 / benchmark | 186 · 62 | 78 / 108 / 0 | 0,1,2 |
| Unity Qwen3.5-27B IQ2_M (Bartowski) | f895ce576bdf48c7bfb6cdda756e4bc0 / benchmark | 186 · 62 | 177 / 9 / 0 | 0,1,2 |
| Unity Qwen3.5-27B UD-IQ2_XXS (Unsloth) | 2134239622f4437fbfa32767f87e989d / benchmark | 9 · 3 | 9 / 0 / 0 | 0,1,2 |
| Unity Qwen3.5-27B UD-IQ2_XXS (Unsloth) | 569edb88b72842c09ca78a3026deb28a / benchmark | 186 · 62 | 186 / 0 / 0 | 0,1,2 |
| Unity Qwen3.5-27B UD-IQ2_XXS (Unsloth) | d77ce126919a4e9e92438170ca73f738 / benchmark | 186 · 62 | 75 / 105 / 6 | 0,1,2 |
| Unity Qwen3.5-27B UD-IQ2_XXS (Unsloth) | f895ce576bdf48c7bfb6cdda756e4bc0 / benchmark | 186 · 62 | 177 / 9 / 0 | 0,1,2 |
| Unity Qwen3.5-9B Q4_K_M | 2134239622f4437fbfa32767f87e989d / benchmark | 9 · 3 | 9 / 0 / 0 | 0,1,2 |
| Unity Qwen3.5-9B Q4_K_M | 569edb88b72842c09ca78a3026deb28a / benchmark | 186 · 62 | 180 / 6 / 0 | 0,1,2 |
| Unity Qwen3.5-9B Q4_K_M | 7f4b286db3954026a4bfcb2f942b60fd / benchmark | 186 · 62 | 54 / 132 / 0 | 0,1,2 |
| Unity Qwen3.5-9B Q4_K_M | f895ce576bdf48c7bfb6cdda756e4bc0 / benchmark | 186 · 62 | 126 / 60 / 0 | 0,1,2 |
| Unity Qwen3.5-9B Q8_0 | 2134239622f4437fbfa32767f87e989d / benchmark | 9 · 3 | 9 / 0 / 0 | 0,1,2 |
| Unity Qwen3.5-9B Q8_0 | 2924fec0c2d3453cba0bdce0e3f68e0c / benchmark | 186 · 62 | 51 / 135 / 0 | 0,1,2 |
| Unity Qwen3.5-9B Q8_0 | 569edb88b72842c09ca78a3026deb28a / benchmark | 186 · 62 | 186 / 0 / 0 | 0,1,2 |
| Unity Qwen3.5-9B Q8_0 | f895ce576bdf48c7bfb6cdda756e4bc0 / benchmark | 186 · 62 | 162 / 24 / 0 | 0,1,2 |

## Final propagation and transitions

| Cohort | Prior requested scope | Final / 186 | Transitions |
| --- | --- | --- | --- |
| Desktop Qwen3.5-9B Q4_K_M | 174 | 186 | {'preserved_pass': 174, 'corrected_failure': 12} |
| Desktop Qwen3-VL-8B-Instruct Q4_K_M | 160 | 164 | {'preserved_pass': 156, 'prior_pass_inconclusive': 1, 'remaining_failure': 18, 'corrected_failure': 8, 'regression': 3} |
| Desktop Qwen3.5-4B Q8_0 | 183 | 99 | {'preserved_pass': 99, 'regression': 84, 'remaining_failure': 3} |
| Desktop Qwen3.5-2B Q8_0 | 87 | 78 | {'preserved_pass': 63, 'corrected_failure': 15, 'remaining_failure': 84, 'regression': 24} |
| Desktop Qwen3.5-9B Q4_K_S | 135 | 186 | {'preserved_pass': 135, 'corrected_failure': 51} |
| Unity Qwen3.5-9B Q4_K_M | 126 | 180 | {'preserved_pass': 126, 'corrected_failure': 54, 'remaining_failure': 6} |
| Unity Qwen3.5-9B Q8_0 | 162 | 186 | {'preserved_pass': 162, 'corrected_failure': 24} |
| Unity Qwen3.5-27B UD-IQ2_XXS (Unsloth) | 186 | 186 | {'preserved_pass': 186} |
| Unity Qwen3.5-27B IQ2_M (Bartowski) | 186 | 186 | {'preserved_pass': 186} |

Perchance: 169→174/186; 158 preserved passes, 16 corrected failures, 11 regressions and one remaining failure. Final Unity: Q4_K_M 126→180, Q8_0 162→186, UD-IQ2_XXS 186→186, Bartowski IQ2_M 186→186. Final native/Perchance requested coverage totals 1860 cases. The terminal VL timeout is retained as inconclusive, not a completed wrong answer. The provider technical retry is additional attempt evidence, not an additional requested case.

The transitions JSONL contains all adjacent saved benchmark observations matched by exact model/test/format/repetition, their before/after prompt hashes and outcomes. These chronological transitions are descriptive; changed prompts, historical NOOP revisions, runtime builds and hardware can confound causal attribution. The supplied final-cohort comparison records the explicitly reviewed baseline pairing.

The 4B regression is substantial: 84 former passes fail, comprising 81 malformed wrappers and three unsupported append tokens; the historical diagnostic compared all 186 paired controls. Its earlier counterfactual wrapper analysis is not a regrade and was not repeated here. The submitted raw streams match the saved outputs. Historical full GGUF hashes are absent for 4B, 2B and VL; name/size/mtime matches do not establish cryptographic identity.

Unity’s six final Q4_K_M failures are the ID-keyed Move primitive cases `db_v3_move_value__value_patch` and `db_v3_move_value_empty__value_patch`, all three repetitions. Unity emits `"from":"/locations/town-a"`; matched desktop calls retain `"from":"/locations/\"town-a\""`. Same GGUF SHA256 `cd76ec205963b3b33350093e6904d9de16c4e666fd104e1f632d25c7f15f2a13`, messages, seeds and requested sampling were verified. Windows/GTX1080/Clang and Linux/TitanX/GNU execution environments differ. Missing quotes explain the grades; the cause of generation divergence is not isolated.

## Technical/setup outcomes and capability limits

Keep technical outcomes out of semantic/formatting model-error totals. The inventory retains all saved terminal timeouts, including older completed watch-dog outcomes. The final VL append_record/normal_json/repetition-0 case has a 120-second watchdog, no text/chunks, and no observed OOM/crash; backend prompt processing stalled, with exact subsystem unresolved. The stopped 2B partial attempt is preserved alongside the eventual completed call. Perchance’s destroyed browser context has no completed generation; its single explicitly authorized retry is separately preserved and passes. No failed model answer was selectively retried in this retrospective.

Perchance setup evidence includes a slow dependency/browser health probe and an offered installation Yes/No flow; no installation was accepted. Existing Playwright/browser files subsequently passed the probe after a byte-identical local cache copy. Those setup/health checks, allocation/readiness events, failed Unity launch/discovery repairs and writer setup/template errors are operational evidence, not scored observations. Auxiliary documents remain in the source inventory; absence of a raw completed call is never a fabricated baseline success.

Perchance is a remote service scheduled only for the eligible 8 GB tier. Seed forwarding is experimental/unverified; actual sampling, cache/context controls, provider defaults and remote model version are unknown where not observed. Repetitions are independent service attempts. Unavailable measurements remain null/not applicable. The native records retain applied sampling, seeds, runtime provenance and placement evidence.

No parser bug is established by a strict rejection of malformed JSON, bare string selectors, wrong path levels or wrong literal tokens. A richer diagnostic could explain the precise field/serialization layer without changing grading; an explicit future output-format comparison could reduce syntax burden. Both require separately reviewed implementations and new evidence. The retired NOOP contract is the evidenced test-design ambiguity; final-state agreement and operation-contract agreement are kept separate.

## Completeness, limitations and deliverables

All discovered in-scope non-pass observations have a resolved primary classification; no generic malformed/unclassified residual remains. Coverage is exhaustive for the saved source corpus, not a claim that every proposed candidate, unexecuted Unity plan or unsaved request ran. Early stopped candidates and baseline-only optimization sessions have the recorded coverage only. No new samples were generated to fill gaps. Archives predating the original930 are inspected only for retrospective reconciliation and are excluded from the study window; nothing was restored into active discovery.

Raw host timestamps are retained. The desktop clock was observed approximately twelve minutes ahead of independent/Unity time, so cross-host chronology and unmeasured timing comparisons are limited. The report does not infer elapsed performance from that skew or attribute platform divergence to a particular GPU numerical mechanism. Original source JSON, prompts, raw outputs, settings and scores remain unchanged.

Companion files in the same directory:

- `2026-10-16-retrospective-summary.json`: counts, integrity, model identities, session/candidate provenance and exclusions.
- `2026-10-16-observation-inventory.jsonl`: every independent observation, original outcome, exact prompt key, repetitions and all source references.
- `2026-10-16-prompt-versions.jsonl`: complete actual messages and counts, grouped first by exact prompt content.
- `2026-10-16-failure-evidence.jsonl`: every non-pass actual output, saved validation/score, source and expected state.
- `2026-10-16-transitions.jsonl`: exact before/after observation and prompt keys.
- `2026-10-16-source-files.jsonl`: inspected JSON byte hashes and locations, including archive members.
- `2026-10-16-final-cohort-comparison.json`: saved reviewed final pairing.
