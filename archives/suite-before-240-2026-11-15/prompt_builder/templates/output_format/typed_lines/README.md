# Typed lines

This folder owns the requested typed-line syntax and database rules. Its active
`format.json` selects `typed_lines`.

Current semantic evaluation uses the shared intent grammar through
`evaluation/output_formats.py` and the `array-identities-intent-v3` host. The
independent strict validator in `evaluation/format_compliance.py` checks exact
record headers, adjacent value/destination lines, slash-path syntax and typed
value labels without recovery, state access or operation application. A strict
format failure never changes the intent verdict.

The syntax contract is `instructions.txt`. Set/append/change require one typed
value line; remove has none; move/copy require an immediately following `to:`
line. Blank lines may separate complete records. `none` denotes no change.
Complete JSON object/list payloads and their empty-label forms are supported.
Data-dependent target restrictions and collection identity resolution remain
semantic checks, not format repair.

Retired typed/Ember decoders are not restored. Historical responses and their
saved scores remain unchanged.
