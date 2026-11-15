# Context diagnostic candidates

Place these files under repository scripts/context_candidates/:
- .gitattributes
- .gitignore
- generate_candidates.py
- stage_bramble.py
- fixtures/The-Last-Light-at-Bramble-Bridge-new-game.json
- fixtures/PROVENANCE.txt
- fixtures/The-Last-Light-at-Bramble-Bridge-materialization.json
- fixtures/bramble-array-audit.json

Run from the repository with its normal Python environment:
```
python scripts/context_candidates/generate_candidates.py
python scripts/context_candidates/stage_bramble.py
```

Scripts locate the repository relative to their own path and write ONLY beneath their script directory. They do not edit the active suite or invoke models. Generated directories, rendered_prompts and measurements need not be committed. The medical/shipping data is entirely synthetic. Bramble is the exact authentic new-game fixture, hash-checked before use. Do not reformat or modify the canonical fixture bytes.

Generated candidates have six independent actions and 108 rendered message arrays each. Current prompt templates and evaluator are used directly. Measurements include characters/UTF8 bytes and a cumulative self-review replay with four reference answers. Token counts remain null until measured with each actual model tokenizer/chat template. Correct reference answers do not bound wrong-answer or reasoning lengths.

Bramble's largest initial prompt is 50,983 characters, potentially above 12k tokens depending on tokenizer. No claim of context fit is made. Preserve the full state and cumulative review workflow; measure all three views and six formats before picking a common GPU-safe budget or candidate tier.
