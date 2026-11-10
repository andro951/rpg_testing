"""Independent, deterministic intent parsing and state-aware patch conversion.

Snake-case Python APIs and camelCase aliases have the same positional arguments,
JSON-shaped return values, and option keys as the JavaScript/C# ports.
"""
from .parse import parse_intent, parse_intent_with_diagnostics
from .patch import IntentError, apply_patch, convert_intent


def normalize_intent(text, document, options=None):
    return convert_intent(parse_intent(text, options), document, options)


parseIntent = parse_intent
parseIntentWithDiagnostics = parse_intent_with_diagnostics
convertIntent = convert_intent
normalizeIntent = normalize_intent
applyPatch = apply_patch

from .prompt import build_prompt
from .replay import replay_prepared
buildPrompt = build_prompt
replayPrepared = replay_prepared
