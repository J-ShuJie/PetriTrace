const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/app.js','utf8');
const axisSource=source.slice(source.indexOf('function makeTimeAxis('),source.indexOf('function timeTickLabel('));
const context={TIME_STEPS_MS:[60000,3600000,86400000],state:{history:{mode:'day',bounds:{start:0,end:86400000}}}};
vm.createContext(context);vm.runInContext(axisSource,context);
test('time preset filters do not compress sparse samples into a full day',()=>{
 const a=context.makeTimeAxis([{timestampMs:3600000},{timestampMs:4800000}],800);
 assert.equal(a.first,3600000);assert.equal(a.last,4800000);
 assert.equal(a.xFor(a.first),a.left);assert.equal(a.xFor(a.last),a.right);
});
test('single and empty samples retain a finite nonzero axis',()=>{
 for(const r of [[],[{timestampMs:3600000}]]){const a=context.makeTimeAxis(r,800);assert.ok(Number.isFinite(a.span)&&a.span>0);}
});

vm.runInContext(source.slice(source.indexOf('function nearestHistoryPoint('),source.indexOf('function historyTablePage(')),context);
test('click hit testing uses both coordinates and CSS pixel tolerance',()=>{
 const canvas={width:800,height:400,historyHitPoints:[{index:3,x:200,y:100}],getBoundingClientRect:()=>({left:10,top:20,width:400,height:200})};
 assert.equal(context.nearestHistoryPoint(canvas,110,70),3);
 assert.equal(context.nearestHistoryPoint(canvas,121,70),3);
 assert.equal(context.nearestHistoryPoint(canvas,123,70),null);
 assert.equal(context.nearestHistoryPoint(canvas,110,140),null);
 assert.equal(context.nearestHistoryPoint(canvas,128,70,20),3);
});
test('empty charts cannot pin a data point',()=>{
 const canvas={width:800,height:400,historyHitPoints:[],getBoundingClientRect:()=>({left:0,top:0,width:800,height:400})};
 assert.equal(context.nearestHistoryPoint(canvas,200,100),null);
});
