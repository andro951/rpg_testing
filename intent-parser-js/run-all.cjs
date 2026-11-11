const {spawnSync}=require('node:child_process');
for(const file of ['unified-formats.test.cjs','grammar-first.test.cjs','test.cjs','end-to-end.test.cjs','optional-order.test.cjs','whitespace.test.cjs','identity-edge.test.cjs','api.test.cjs','replay.test.cjs','json-safety.test.cjs','current-revision.test.cjs']){
 const result=spawnSync(process.execPath,[require('node:path').join(__dirname,file)],{stdio:'inherit'});
 if(result.status!==0)process.exit(result.status||1);
}
