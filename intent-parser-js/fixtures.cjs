const base={items:[{id:'a',name:'Map',count:1},{id:'b',name:'Key',count:1}],archive:[]};
module.exports=[
 {name:'update',input:base,fields:{op:'update',path:'["items","a","count"]',value:'2'},expected:{items:[{id:'a',name:'Map',count:2},base.items[1]],archive:[]}},
 {name:'append',input:base,fields:{op:'append',path:'["archive"]',value:'{"id":"c","name":"Gem"}'},expected:{items:base.items,archive:[{id:'c',name:'Gem'}]}},
 {name:'remove',input:base,fields:{op:'remove',path:'["items","a"]'},expected:{items:[base.items[1]],archive:[]}},
 {name:'copy',input:base,fields:{op:'copy',from:'["items","a"]',to:'["archive"]'},expected:{items:base.items,archive:[base.items[0]]}},
 {name:'move',input:base,fields:{op:'move',from:'["items","a"]',to:'["archive"]'},expected:{items:[base.items[1]],archive:[base.items[0]]}},
 {name:'root append',input:[],fields:{op:'append',path:'[]',value:'{"id":"x"}'},expected:[{id:'x'}]},
 {name:'escaped pointer',input:{'a/b':{'~':0}},fields:{op:'update',path:'["a/b","~"]',value:'1'},expected:{'a/b':{'~':1}}},
 {name:'literal separators',input:{'a.b/c d':{'x:y':0}},fields:{op:'update',path:'["a.b/c d","x:y"]',value:'4'},expected:{'a.b/c d':{'x:y':4}}},
 {name:'quoted keyword',input:{items:[{id:'remove',text:'before'}]},fields:{op:'update',path:'["items","remove","text"]',value:'"after"'},expected:{items:[{id:'remove',text:'after'}]}},
 {name:'unicode',input:{'箱':[{id:'é',text:'x'}]},fields:{op:'update',path:'["箱","é","text"]',value:'"→😀"'},expected:{'箱':[{id:'é',text:'→😀'}]}},
 {name:'prototype property',input:JSON.parse('{"__proto__":{"x":1}}'),fields:{op:'update',path:'["__proto__","x"]',value:'2'},expected:JSON.parse('{"__proto__":{"x":2}}')},
];
