'use strict';
const api=require('./index.cjs'),assert=require('node:assert/strict');let passed=0;
for(const f of require('./current-revision-fixtures.json')){let actual;try{actual=api.applyPatch(f.input,api.normalizeIntent(f.text,f.input));}catch(error){if(f.reject){passed++;continue;}throw error;}assert(!f.reject,`${f.name}: expected rejection`);assert.deepEqual(actual,f.expected,f.name);passed++;}
assert.throws(()=>api.normalizeIntent('set path:a value:1',{a:0}));assert.throws(()=>api.normalizeIntent('replace path:a value:1',{a:0}));passed+=2;
const text='remove path:a'+ '\n,\n,'.repeat(2000)+'\nremove path:b';assert.deepEqual(api.applyPatch({a:1,b:2},api.normalizeIntent(text,{a:1,b:2})),{});passed++;
console.log(JSON.stringify({passed,failed:0,scope:'current-contract independent safety and syntax; legacy generic aliases absent'}));
