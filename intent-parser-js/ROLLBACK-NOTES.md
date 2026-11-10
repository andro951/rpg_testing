# Current-contract rollback checkpoint

Reconstructed from the delivered JavaScript baseline and independently tested cross-language behavior after the original working checkout was unavailable. This is not represented as a byte-identical recovery of the lost checkout.

Generic `replace` and `set` aliases are not enabled. No RFC input importer, automatic dialect guard, or input-dialect replay bridge is included. Standard RFC6902 remains an optional output format, as originally requested. Host-specific current-format adapters may explicitly map their native operation vocabulary separately.

Preserved independently reviewed changes: exact enclosing JSON fences; quoted operations and transfer paths; unique complete interpretation of value-first objects; JSON keys matching reserved labels; Unicode and numeric-underflow rejection; unified primitive/object identity collision checks; bounded separator-only runs.

All 5,602 baseline deterministic checks plus 47 current-contract revision checks pass. These are saved/synthetic tests, not new model runs. Historical archives are unchanged and are not part of this regression source.
