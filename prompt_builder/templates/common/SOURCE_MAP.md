# Source lineage and current ownership

The starting data and task sentences originated in the former test_builder/fixtures.json and builder.task_text. Expected final data and representative patches were exported from the old oracle before deleting the builder. They are now ordinary editable case files.

Original source commit: a64cc029837a33d4b67a6a8e4b5d686497ef943c. The independent pre-change check matched 38 base messages and 24 catalog messages. See archives/prompt-builder-parity for exact preserved content and hashes.

Current text ownership is only in these template folders. prompt_builder/builder.py reads case files, presentation.py renders starting data, and template_text.py fills the layouts. requested_change.txt is literal text, including any template-looking symbols; comments are recognized only in layout templates. Expected answers never enter assembly.

Original output-protocol file names and hashes in reference/format_sources.json are provenance pointers, not runtime inputs. Paths referring to test_builder describe the deleted historical source at the above commit. typed_lines is the new folder name; legacy names inside archived evidence remain unchanged.

The schema-free version intentionally removes per-case schema descriptions and revises general array rules. ID-keyed and full-path views now explicitly preserve container kinds using data-derived markers. These final prompts are not claimed equivalent to old experimental conditions.

Archived experiment inputs, raw responses and scores were not rewritten. The old executable builder was removed, not hidden in an archive. Historical tests retain frozen definitions and references rather than importing that builder.
