const assert=require('node:assert/strict');const fs=require('node:fs');const {replayPrepared}=require('./replay.cjs');
const records=[...JSON.parse(fs.readFileSync(__dirname+'/parity-fixtures.json','utf8')),...JSON.parse(fs.readFileSync(__dirname+'/optional-parity-fixtures.json','utf8'))];
const before=JSON.stringify(records);const custom=replayPrepared(records);let passed=0;
for(const result of custom.results){assert.notEqual(result.expectedStateMatches,false,JSON.stringify(result));assert.notEqual(result.expectedRejectionMatches,false,JSON.stringify(result));assert.equal(result.rawOutput,records[result.index].text);passed++;}
assert.equal(JSON.stringify(records),before);passed++;
const sample=records.find(r=>r.expected);const changed={...sample,expected:{deliberately:'wrong'}};
const first=replayPrepared([sample]).results[0],second=replayPrepared([changed]).results[0];assert.deepEqual(first.patch,second.patch);assert.equal(second.expectedStateMatches,false);passed++;
const std=replayPrepared([sample],{json_patch:true});assert.equal(std.format,'rfc6902');assert.equal(std.results[0].patch[0].op,'replace');passed++;
assert.equal(std.liveInference,false);passed++;
console.log(JSON.stringify({passed,failed:0,records:records.length,scope:'saved prepared-output replay, raw preservation, expected-state oracle isolated from normalizer'}));
