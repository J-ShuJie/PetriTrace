const test = require("node:test");
const assert = require("node:assert/strict");
const { presetHistoryBounds } = require("../static/history_range.js");
const now = Date.parse("2026-09-30T12:00:00Z");
for (const [mode, days] of Object.entries({day: 1, threeDays: 3, week: 7})) {
 test(`${mode}: fixed duration independent of sample density`, () => {
  const bounds = presetHistoryBounds(mode, now);
  assert.equal(bounds.end, now);
  assert.equal(bounds.end - bounds.start, days * 86400000);
 });
}
test("one new capture advances the range without changing its duration", () => {
 const before = presetHistoryBounds("day", now);
 const after = presetHistoryBounds("day", now + 60000);
 assert.equal(after.start - before.start, 60000);
 assert.equal(after.end - before.end, 60000);
});
test("DST transition still represents 24 elapsed hours", () => {
 const bounds = presetHistoryBounds("day", Date.parse("2026-10-25T12:00:00+01:00"));
 assert.equal(bounds.end - bounds.start, 86400000);
});
test("all and custom never use a hidden automatic preset", () => {
 for(const mode of ["auto","all","custom","unknown"]) assert.equal(presetHistoryBounds(mode,now),null);
});
