(function attachHistoryRange(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.PiHistoryRange = api;
}(typeof globalThis !== "undefined" ? globalThis : this, function buildHistoryRange() {
  // Rolling durations, not calendar midnights: identical elapsed time across DST.
  const DAYS = { day: 1, threeDays: 3, week: 7 };
  function presetHistoryBounds(mode, now = Date.now()) {
    const days = DAYS[mode];
    if (!days || !Number.isFinite(now)) return null;
    return { start: now - days * 86400000, end: now };
  }
  return { presetHistoryBounds };
}));
