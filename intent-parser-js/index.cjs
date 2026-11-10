'use strict';

const { parseIntent, parseIntentWithDiagnostics } = require('./parse.cjs');
const { convertIntent, applyPatch } = require('./patch.cjs');
const { buildPrompt } = require('./prompt.cjs');

/** Return only the selected patch format, without applying it to the caller's data. */
function normalizeIntent(text, document, options = {}) {
  const ir = parseIntent(text, options);
  return convertIntent(ir, document, options);
}

module.exports = {
  buildPrompt,
  parseIntent,
  parseIntentWithDiagnostics,
  convertIntent,
  normalizeIntent,
  applyPatch,
};
