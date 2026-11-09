const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const bundle=fs.readFileSync(path.join(__dirname,'GrammarForge/grammarForgeBundle.js'),'utf8');
const names=[...bundle.matchAll(/'((?:grammarForge|scriptForge)\/[^']+\.js)'/g)].map(m=>m[1]).filter(name=>name.startsWith('grammarForge/'));
const context=vm.createContext({console});
for(const name of names) vm.runInContext(fs.readFileSync(path.join(__dirname,'GrammarForge',name),'utf8'),context,{filename:name});
module.exports=vm.runInContext('GrammarForge',context);
