from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SecondaryDialogStructureTests(unittest.TestCase):
    def test_settings_and_diagnostics_are_same_page_dialogs(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="settingsDialog"', html)
        self.assertIn('id="diagnosticsDialog"', html)
        self.assertIn('id="settingsDialogOpen"', html)
        self.assertIn('id="diagnosticsDialogOpen"', html)
        self.assertIn('id="errorBox"', html)
        self.assertIn('id="systemDetailsList"', html)

    def test_three_layer_status_structure_keeps_summary_on_top_and_details_in_diagnostics(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        stylesheet = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        for element_id in (
            "topStorageViewToggle",
            "topStorageViewLabel",
            "topStorageRoute",
            "topStorageViewMenu",
            "topStorageViewCurrent",
            "topStorageViewLocal",
            "topStorageViewExternal",
            "topPhotoCount",
            "topPhotoEstimate",
            "topSystemStorage",
            "topStorageTrack",
            "topStorageFill",
            "topStoragePhotoMarker",
            "topAlert",
            "diagnosticsAlertOpen",
            "diagnosticEvents",
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertNotIn('<section class="status-grid">', html)
        diagnostics_start = html.index('id="diagnosticsDialog"')
        self.assertGreater(html.index('id="statusList"'), diagnostics_start)
        self.assertGreater(html.index('id="environmentList"'), diagnostics_start)
        self.assertIn("function currentStatusIssues(status)", javascript)
        self.assertIn("function loadDiagnosticEvents()", javascript)
        self.assertIn("function resolvedStorageView(status)", javascript)
        self.assertIn("function renderStorageViewMenu(status)", javascript)
        self.assertIn('storageView: "current"', javascript)
        self.assertIn('data-storage-view="current"', html)
        self.assertIn('data-storage-view="local"', html)
        self.assertIn('data-storage-view="external"', html)
        self.assertIn('aria-haspopup="menu"', html)
        self.assertIn(".top-storage-view-menu", stylesheet)
        self.assertNotIn("回退", javascript)
        self.assertIn('photoCount === null || photoCount === undefined', javascript)
        topbar_start = html.index('<div class="topbar-main">')
        topbar_end = html.index('</div>\n      <div id="topAlert"', topbar_start)
        self.assertLess(html.index('class="top-overview"', topbar_start), topbar_end)
        self.assertNotIn('class="overview-metric"', html)
        self.assertIn("role=\"alert\"", html)
        self.assertIn("role=\"progressbar\"", html)
        self.assertIn(".top-alert", stylesheet)

    def test_ui_does_not_open_secondary_browser_windows(self):
        javascript = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("window.open(", javascript)
        self.assertIn("dialog.showModal()", javascript)

    def test_windows_manager_entry_is_presentation_only_and_kiosk_safe(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        entry_context = (ROOT / "static" / "entry_context.js").read_text(encoding="utf-8")
        stylesheet = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

        self.assertNotIn('id="windowsManagerContext"', html)
        self.assertIn('id="windowsManagerReturn"', html)
        self.assertIn('id="windowsManagerEntryToast"', html)
        self.assertIn('href="picameracontrol://manage"', html)
        self.assertIn('data-i18n-aria-label="returnToWindowsManager"', html)
        self.assertIn('data-i18n="openedByWindowsManager"', html)
        self.assertIn('lucide-monitor', html)
        self.assertNotIn('lucide-arrow-left-to-line', html)
        self.assertIn('filename=\'entry_context.js\'', html)
        self.assertIn('params.get("entry") === "windows-manager"', entry_context)
        self.assertIn('displayMode === "kiosk"', entry_context)
        self.assertIn('$("windowsManagerReturn").hidden = !isManagerEntry', javascript)
        self.assertIn('showManagerEntryToast(isManagerEntry)', javascript)
        self.assertIn('MANAGER_ENTRY_TOAST_DURATION_MS = 3000', javascript)
        self.assertIn(".manager-return-button:focus-visible", stylesheet)
        self.assertIn(".manager-return-button[hidden]", stylesheet)
        self.assertIn(".manager-entry-toast.is-visible", stylesheet)
        self.assertIn("prefers-reduced-motion: reduce", stylesheet)
        self.assertNotIn(".manager-context", stylesheet)
        self.assertNotIn("Authorization", entry_context)
        self.assertNotIn("fetch(", entry_context)

    def test_lucide_icons_are_local_and_attributed(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        stylesheet = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        for icon_name in ("settings", "activity", "monitor", "x"):
            self.assertTrue((ROOT / "static" / "icons" / "lucide" / f"{icon_name}.svg").is_file())
            self.assertIn(f"lucide-{icon_name}", html)
            self.assertIn(f'url("icons/lucide/{icon_name}.svg")', stylesheet)
        self.assertNotIn("<svg", html)
        self.assertTrue((ROOT / "static" / "icons" / "lucide" / "LICENSE.txt").is_file())

    def test_settings_form_keeps_text_and_controls_inside_the_dialog_grid(self):
        stylesheet = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn('input:not([type="checkbox"])', stylesheet)
        self.assertIn("box-sizing: border-box", stylesheet)
        self.assertIn("grid-column: 1 / -1", stylesheet)
        self.assertIn("overflow-wrap: anywhere", stylesheet)

    def test_external_storage_settings_are_progressive_and_never_format_silently(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        app_python = (ROOT / "app.py").read_text(encoding="utf-8")
        for element_id in (
            "storagePolicy",
            "externalDeviceSelect",
            "localReserveMb",
            "externalStorageStatusList",
            "externalSnapshotBtn",
            "externalEjectBtn",
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('class="settings-group external-storage-group"', html)
        self.assertIn("function renderExternalStorageStatus(external = {})", javascript)
        self.assertIn('post("/api/external-storage/snapshot")', javascript)
        self.assertIn('post("/api/external-storage/eject")', javascript)
        self.assertIn('@app.post("/api/external-storage/snapshot")', app_python)
        self.assertIn('@app.post("/api/external-storage/eject")', app_python)
        self.assertNotIn('id="externalFormatBtn"', html)
        self.assertNotIn('/api/external-storage/format', app_python)
        self.assertNotIn('value="local_only"', html)
        self.assertIn('value="local_preferred"', html)
        self.assertIn('value="external_preferred"', html)
        self.assertIn('localStorageLowMessage', javascript)
        self.assertIn('externalStorageLowMessage', javascript)
        self.assertNotIn('id="externalAutoSync"', html)
        self.assertNotIn('id="externalSyncIntervalSeconds"', html)
        self.assertNotIn('id="localCleanupPolicy"', html)
        self.assertNotIn('id="localCleanupDays"', html)
        self.assertIn('id="externalSnapshotBtn"', html)

    def test_history_has_data_driven_range_modes_and_independent_time_ticks(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        for mode in ("day", "threeDays", "week", "all", "custom"):
            self.assertIn(f'data-history-mode="{mode}"', html)
        self.assertIn('id="historyRangeSummary"', html)
        self.assertIn('id="historyStart" type="datetime-local" step="1"', html)
        self.assertIn('id="historyEnd" type="datetime-local" step="1"', html)
        self.assertNotIn('data-history-mode="auto"', html)
        self.assertIn("window.PiHistoryRange.presetHistoryBounds", javascript)
        self.assertIn("history_range.js", html)
        self.assertIn("const targetTicks", javascript)
        self.assertNotIn("Date.now() - 60 * 60 * 1000", javascript)

    def test_history_charts_support_point_inspection_and_paginated_details(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        stylesheet = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        for canvas_id in ("environmentHistoryChart", "colonyHistoryChart"):
            self.assertIn(f'id="{canvas_id}"', html)
        self.assertEqual(html.count('class="history-tooltip hidden"'), 2)
        self.assertIn('id="historyDetails" class="history-details"', html)
        self.assertIn('id="historyDetails" class="history-details" open', html)
        self.assertIn('id="historyPrevPage"', html)
        self.assertIn('id="historyNextPage"', html)
        self.assertIn('t("viewPhoto")', javascript)
        self.assertIn("function nearestHistoryPoint(canvas, clientX, clientY = null", javascript)
        self.assertIn("function wireHistoryChartInteractions(canvasId, chartName)", javascript)
        self.assertIn("pageSize: 25", javascript)
        self.assertIn("touch-action: pan-y", stylesheet)
        self.assertIn("min-height: 44px", stylesheet)


if __name__ == "__main__":
    unittest.main()
