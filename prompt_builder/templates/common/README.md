# Prompt templates: start here

These are the actual editable sources used by `python -m prompt_builder`. No schema.json is required, and no test-specific schema description is sent to a model.

## Four content folders

- **common/**: shared instructions, layout, and selected cases/formats.
- **input_format/**: one folder per way of displaying the same starting data. `notes.txt` is model-facing; `format.json` selects a serializer.
- **output_format/**: one folder per requested response style. Edit its complete `path_rules.txt` and `format.txt`, or its dedicated `user.txt` layout. `format.json` selects its output reader.
- **test_cases/**: one descriptive folder per actual task. Everything that varies with that task belongs there.

## A test case

- `starting_data.json`: the exact initial database.
- `requested_change.txt`: the exact task sentence sent to the model. It is read directly, not regenerated from hidden task patterns.
- `expected_result.json`: the correct final database, used only in grading.
- `expected_patch.json`: a representative correct patch with canonical ID-based dot paths, used only for a separate difference flag.

Editing task wording does not magically update its reference answers. Maintain the expected result and patch together. The builder checks that the patch produces that result before generating the suite. Neither answer file is accessible to prompt assembly.

## Edit once

Change shared rules here, format wording in its format folder, or case text in its case folder. Generated previews and frozen test definitions are outputs, not alternative editable sources. Rebuild after editing.

`${name}` in layout files is a substitution. The `{# ... #}` comment at the top of each layout explains exactly which file or serializer supplies every name; those comments are removed before sending. Section order, heading text and whitespace are editable directly. An unknown placeholder fails with its file name rather than disappearing silently. Values inserted from task/data files are never recursively expanded as templates.

## Select or add

`common/selection.json` selects the default 13 cases, three input views, and JSON-dot output. `python -m prompt_builder --list` discovers available folders. A new case or a copied output folder using an existing decoder requires no Python edit: change its files and select its folder. Extra unreferenced text files are not silently inserted. An entirely new serialization or response syntax still needs a compatible serializer/reader in code; wording alone cannot implement one.

Example from the repository root:

```sh
python -m prompt_builder --output build/prompt-suite
python -m prompt_builder --output build/all-formats --input-formats normal_json id_keyed_arrays full_paths named_tables --output-formats json_dot json_slash path_list literal_line end_marked_line two_line_text typed_lines free_format
```

The default creates 13 test definitions, 38 unique prompts, and 114 observations per model at three repetitions. Compilation does not call a model. All eight output choices are implemented; the retained `typed_lines` protocol is intentionally narrower, so unsupported case/format combinations are listed with reasons, never changed into easier tasks. `free_format` prescribes no output syntax, so parser recovery is not a complete semantic judgment of unrecognized prose.

## Important boundaries

Database arrays are unordered collections of objects with unique IDs or unique primitive values. Output operation lists remain ordered because patches execute sequentially. Object-array IDs are inferred from exactly one shared unique scalar `id` or `*_id` field. Other names or multiple eligible fields are rejected instead of guessed. Empty arrays obtain identity information only from newly supplied values, not from expected answers. This is an explicit current implementation limit, not a hidden case schema.

The ID-keyed and full-path views now carry container markers derived from the starting data, so deleting schema hints does not erase the distinction between objects and arrays. Normal JSON is ordinary JSON. These deliberate input changes are not claimed to reproduce historical prompts.

See `PARITY.md` for the before-change check and `VALIDATION_NOTES.md` for grading. Legacy evidence remains under `archives/` and `experiments/`; the superseded builder code is removed.
