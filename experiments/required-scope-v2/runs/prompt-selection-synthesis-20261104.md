# CSC 592 prompt-selection evidence (working synthesis)

The research selects complete recipes for a model and required state-update tasks, not a path syntax in isolation. The strongest original baseline in the available fixed-recipe comparisons was dot-path JSON overall; the aggregate combines non-independent cohorts and is not a population estimate. Earlier evidence also showed that slash or path-list recipes could outperform dot JSON for particular models or cases.

The first instruction-only copy, dot promptcopy_v1, scored 24/54 on its reserved-ID development cases, matching the 24/54 original. This is evidence that one copy did not improve those cases, not that prompt optimization generally plateaued. The independently restructured dot promptcopy_v2 scored 33/54 on the same model and development cases, with nine gains and no regressions. Those gains came from quote-ID and slash-ID removal cases in development. Its separately frozen heldout evaluation did not show a general improvement across models:

| Model | Original | Copy v2 | Copy wins / regressions |
| --- | ---: | ---: | ---: |
| VL8 Q4 | 28/53 | 44/53 | 17 / 1 |
| 4B Q8 | 24/54 | 18/54 | 6 / 12 |
| 9B Q4_K_M | 24/54 | 15/54 | 3 / 12 |
| 2B Q8 | 21/53 | 9/53 | 3 / 15; 11 inconclusive |
| 9B Q4_K_S | 24/54 | 18/54 | 6 / 12 |

The two 53-pair models each have one excluded observation whose outcome was uncertain after controller exits; it was not retried. The 2B copy also has eleven inconclusive outcomes, not semantic failures. The six heldout fixtures were each represented three ways and repeated three times. They are not 54 independent tasks. The case set contains plain and reserved IDs as paired cases; these results should not be generalized beyond those cases.

Literal-line v1 and v2 are representation/parser branches from the preserved pre-optimization dot baseline, not descendants of the instruction-only copy. Their one-update-per-line contract accepts unquoted string text, but still needs a reversible encoding for newlines, backslashes and boundary whitespace. Typed non-string values retain JSON encoding; complex object additions therefore still require JSON serialization. Independent round-trip tests cover actual newline versus literal backslash-n, literal backslash-quote versus escaped quote, empty text and boundary spaces. A parser passing those tests does not prove a model will produce the contract reliably.

In literal v1's safe-ID development test on one 9B model, the original scored 39/54 and literal v1 21/54. The revised literal v2 scored 36/54 on those same development cases: nine wins and twelve regressions versus the original. The separately frozen nine-task heldout comparison produced mixed model-specific outcomes, with the literal format improving two models, tying two and regressing on one. Results are full recipes with different output contracts and instructions, not an isolated estimate of path syntax.

The separate safe-text-heldout-v1 cohort directly tested difficult field text using controlled simple IDs. Across five models and nine observations per fixture per model, the literal recipe passed 39/45 newline observations versus 30/45 original and 30/45 quote observations versus 17/45 original. It passed just 6/45 boundary-space observations versus 42/45 original. These are six fixtures shown in three presentations and repeated three times; they are not 45 independent tasks. For exact text preservation, even one boundary-space change is an incorrect update. Per-model audits preserve gains and regressions and should be used over aggregate scores when selecting a deployment recipe.

Safe generated IDs reduce the practical importance of earlier failures involving special characters inside ID selectors. They do not remove the need to preserve genuine user text, nested identity targeting, unrelated fields, and array additions/removals. Model outputs are resolved by the adapter, and model-side selector mistakes remain semantic failures. Previous results and all raw observations are preserved.

Both heldout cohorts are archived with raw observations, matched audits and summaries. The fixed comparison and all prior prompt versions remain preserved. No additional prompt revision has been tuned on heldout outputs. The reserved-ID development cases suggest a useful direction for future development, but their focus on arbitrary special-character IDs is less representative if production IDs are constrained. A further GPU run is not justified without a new development question and independent evaluation plan; the desktop GPU has been released.

Perchance is deferred: the previous CDP attempt timed out, and Windows denied an attempt to inspect browser command lines. Ordinary process-name and port checks did not establish the listener's profile ownership. No browser-profile, session, credential or browser manipulation was performed to work around that uncertainty.
