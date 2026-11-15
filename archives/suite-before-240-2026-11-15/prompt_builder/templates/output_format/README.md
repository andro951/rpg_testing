# Output formats

| Folder | Output shape | Scope |
| --- | --- | --- |
| json_dot | JSON operation objects with dot-path strings | Selected baseline |
| json_slash | JSON operations with typed ID/value slash paths | Researched custom protocol, not positional RFC 6902 |
| path_list | One-line operations with bracketed unquoted path components | Researched path-list protocol |
| literal_line | Dot-path lines with text: or json: values | Literal-text protocol |
| end_marked_line | Literal string text ending at the final pipe | End-marker protocol |
| free_format | No prescribed output serialization | Separate named-table experiment design |
| typed_lines | Operation/path line and typed value line | Restricted Ember protocol |
| two_line_text | Operation/path line and JSON value: line | Retained inactive method |

These formats are not all enabled or guaranteed to support every case. The selection remains unchanged. Each folder owns its output instructions; free-format's format.txt remains empty.

All revised prompt contexts use the general system restriction from common/layout/system.txt. No per-case database structure is inserted. Syntax fragments may be unchanged from their original sources, but complete original-prompt parity no longer holds. Source lineage is retained in common/reference/format_sources.json, not old schema-bearing prompt snapshots.

The existing production path resolution/evaluation still has schema dependencies; this package does not implement a replacement. See common/VALIDATION_NOTES.md. ID-keyed and full-path renderers also need an agreed ID-field convention without quietly reintroducing case metadata.
