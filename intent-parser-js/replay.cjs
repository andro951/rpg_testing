'use strict';

const fs = require('node:fs');
const crypto = require('node:crypto');
const { isDeepStrictEqual } = require('node:util');
const { parseIntent, convertIntent, applyPatch } = require('./index.cjs');

/** Offline software evaluation only. Expected states are never supplied to normalization. */
function replayPrepared(records, options = {}) {
  if (!Array.isArray(records)) throw new Error('Prepared records must be an array');
  const results = records.map((record, index) => {
    const rawOutput = record.output ?? record.text;
    if (typeof rawOutput !== 'string') throw new Error(`Record ${index} lacks textual output`);
    const result = {
      index,
      name: record.name ?? null,
      rawOutput,
      rawSha256: crypto.createHash('sha256').update(rawOutput, 'utf8').digest('hex'),
    };
    try {
      const ir = parseIntent(rawOutput, options);
      const custom = convertIntent(ir, record.input, options);
      // The selected external patch format is exclusive. Application is a separate test stage.
      const canonicalCustom = options.json_patch ? convertIntent(ir, record.input, { ...options, json_patch: false }) : custom;
      const finalState = applyPatch(record.input, canonicalCustom, options);
      Object.assign(result, { accepted: true, patch: custom, finalState });
      if (Object.hasOwn(record, 'expected')) result.expectedStateMatches = isDeepStrictEqual(finalState, record.expected);
      if (Object.hasOwn(record, 'reject')) result.expectedRejectionMatches = record.reject === false;
    } catch (error) {
      Object.assign(result, { accepted: false, error: error.message });
      if (Object.hasOwn(record, 'expected')) result.expectedStateMatches = false;
      if (Object.hasOwn(record, 'reject')) result.expectedRejectionMatches = record.reject === true;
    }
    return result;
  });
  return {
    mode: 'offline-prepared-output-replay',
    liveInference: false,
    format: options.json_patch ? 'rfc6902' : 'custom',
    total: results.length,
    accepted: results.filter(r => r.accepted).length,
    rejected: results.filter(r => !r.accepted).length,
    results,
  };
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const filename = args.find(a => !a.startsWith('--'));
  if (!filename) {
    console.error('Usage: node replay.cjs prepared-records.json [--json-patch]');
    process.exitCode = 2;
  } else {
    try {
      const records = JSON.parse(fs.readFileSync(filename, 'utf8'));
      process.stdout.write(JSON.stringify(replayPrepared(records, { json_patch: args.includes('--json-patch') }), null, 2) + '\n');
    } catch (error) {
      console.error(error.message);
      process.exitCode = 1;
    }
  }
}

module.exports = { replayPrepared };
