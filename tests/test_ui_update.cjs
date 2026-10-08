const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('static/app.js', 'utf8');
const code = source.slice(source.indexOf('let lastPageInteraction'), source.indexOf('async function init()'));
async function scenario({revision='new',kiosk=false,dialog=false,focused=false,recent=false,fail=false}={}) {
 let reloaded=0, marked=0;
 const button={classList:{add(){marked++;}},dataset:{},setAttribute(){}};
 const context={Date,document:{addEventListener(){},documentElement:{dataset:{uiVersion:'old'}},querySelector(){return dialog;},activeElement:{matches(){return focused;}}},fetch:async()=>{if(fail)throw Error('offline');return {ok:true,json:async()=>({revision})}},$:()=>button,t:k=>k,isKioskDisplay:()=>kiosk,location:{reload(){reloaded++;}}};
 vm.createContext(context);vm.runInContext(code,context);
 if(!recent)vm.runInContext('lastPageInteraction = 0',context);
 await vm.runInContext('checkPageVersion()',context);
 return {reloaded,marked};
}
(async()=>{
 assert.deepEqual(await scenario({revision:'old'}),{reloaded:0,marked:0});
 assert.deepEqual(await scenario(),{reloaded:0,marked:1});
 assert.equal((await scenario({kiosk:true})).reloaded,1);
 for(const guard of [{dialog:true},{focused:true},{recent:true}])assert.equal((await scenario({kiosk:true,...guard})).reloaded,0);
 assert.deepEqual(await scenario({fail:true}),{reloaded:0,marked:0});
 console.log('PASS: version match, remote update notice, idle kiosk reload, modal/focus/activity guards, offline retry');
})().catch(e=>{console.error(e);process.exit(1);});
