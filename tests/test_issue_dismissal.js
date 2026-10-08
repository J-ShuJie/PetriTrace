const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('static/app.js','utf8');
const block = source.slice(source.indexOf('let dismissedIssues'), source.indexOf('function currentStatusIssues'));
test('dismissal survives reload, clears on recovery and allows a new event',()=>{
 const saved = new Map();
 const ctx=vm.createContext({localStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)}});
 vm.runInContext(block,ctx);
 assert.equal(vm.runInContext('visibleStatusIssues([{key:"analysis:1"}]).length',ctx),1);
 vm.runInContext('dismissedIssues=["analysis:1"];saveDismissedIssues()',ctx);
 assert.equal(vm.runInContext('visibleStatusIssues([{key:"analysis:1"}]).length',ctx),0);
 const again=vm.createContext({localStorage:ctx.localStorage});vm.runInContext(block,again);
 assert.equal(vm.runInContext('visibleStatusIssues([{key:"analysis:1"}]).length',again),0);
 assert.equal(vm.runInContext('visibleStatusIssues([{key:"analysis:2"}]).length',again),1);
 vm.runInContext('dismissedIssues=["cameraIssue"];visibleStatusIssues([])',again);
 assert.equal(vm.runInContext('visibleStatusIssues([{key:"cameraIssue"}]).length',again),1);
});
