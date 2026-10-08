const test = require("node:test");
const assert = require("node:assert/strict");

const { isWindowsManagerEntry } = require("../static/entry_context.js");

test("only the explicit manager entry marker enables the manager return control", () => {
  assert.equal(isWindowsManagerEntry("?entry=windows-manager", "remote"), true);
  assert.equal(isWindowsManagerEntry("?entry=Windows-Manager", "remote"), false);
  assert.equal(isWindowsManagerEntry("?entry=other", "remote"), false);
  assert.equal(isWindowsManagerEntry("", "remote"), false);
});

test("kiosk display always suppresses Windows manager presentation", () => {
  assert.equal(isWindowsManagerEntry("?entry=windows-manager&display=kiosk", "kiosk"), false);
});

test("unrelated query parameters do not imply manager context", () => {
  assert.equal(isWindowsManagerEntry("?display=remote&token=windows-manager", "remote"), false);
});
