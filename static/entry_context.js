(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.PiEntryContext = api;
})(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";

  function isWindowsManagerEntry(search, displayMode) {
    if (displayMode === "kiosk") return false;
    const params = new URLSearchParams(search || "");
    return params.get("entry") === "windows-manager";
  }

  return Object.freeze({ isWindowsManagerEntry });
});
