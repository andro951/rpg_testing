# Alias review: explicit choices, no hidden acceptance

Enabled core: `add`, `append`, `insert` → append; `update`; `remove`, `delete`; `copy`; `move`. `insert` only works as append when no positional requirement is present. Unknown fields, including before/after/index, reject rather than discard placement intent.

Directional labels enabled: `from`/`source`, `to`/`destination`. `path` can fill the remaining role when exactly one directional label fixes the other. `path1`/`path2` alone cannot establish direction. Collection-to-collection unlabeled paths reject. Numeric order never supplies missing intent.

## Candidates needing explicit design review

| Candidate | Why not silently enable |
|---|---|
| push | JavaScript appends one or more values; stack conventions imply top insertion, not always an unordered collection append. Could alias only for a single explicit value. |
| enqueue | Usually queue-tail append, but implies queue semantics. Could accept under the system's collection contract. |
| extend / concat / addAll / AddRange | Usually appends each member of a supplied collection, not the collection itself. Cannot safely alias single-value append. |
| prepend / unshift | Positional front insertion. Reject rather than reinterpret. |
| set / assign / put | Often creates missing keys or replaces existing keys; update requires an existing target. Could accept only with existing-target check if desired. |
| replace | Often exact value replacement, compatible with current update; some APIs mean text substitution or replacing collection members. Candidate alias only in explicit operation position. |
| merge / patch | May change selected fields recursively rather than replace a value. Not an update alias. |
| erase / discard / drop | Could mean remove one element, silently ignore a missing target, or remove an entire collection/table. Context-dependent. |
| pop / shift / RemoveAt | Positional removal or return-value semantics, inconsistent with ID-selected removal. Reject. |
| clear / empty / truncate | Removes all members, not one selected element. Reject as remove alias. |
| clone / duplicate | Strong copy candidates, but shallow/deep copy ambiguity; our copy is complete independent JSON copy appended to another list. |
| transfer / relocate | Often move, but transfer can also mean copy. Do not infer deletion. |
| sourcePath / destinationPath | Clear directional label candidates. |
| collection / array / list | Suggests destination collection but source may itself be a collection; not universally directional. |
| value | A literal payload label for update/append; should not globally mean source path. |

These distinctions reflect familiar conventions in JavaScript arrays, Python lists, C# List<T>, JSON Patch and JSON Merge Patch. This is a semantic review, not a claim to have exhaustively surveyed every language or all meanings of each English word. No new aliases above are enabled without review.

## Delimiters and boundaries

Enabled label delimiters: `:`, `=`, `=>`, `->`. Semicolon remains an operation boundary; comma separates components/path parts; dot/slash separate path parts. Quoted text is never split on these characters. Explicit path arrays preserve literal separator characters and typed values.

Plain whitespace does not mark a label. Newlines can continue a labeled operation. Explicit operation groups or semicolons determine operation boundaries; without a unique boundary, reject. Expanding these policies must preserve the principle that two plausible interpretations cause rejection, never guessed updates.
