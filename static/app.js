const $ = (id) => document.getElementById(id);

let intervalDirty = false;
let statusRequest = null;
let managerEntryToastTimer = null;
let managerEntryToastHideTimer = null;
const MANAGER_ENTRY_TOAST_DURATION_MS = 3000;
const MANAGER_ENTRY_TOAST_EXIT_MS = 180;
const state = {
  config: null,
  language: "en",
  displayMode: "remote",
  entrySource: null,
  status: null,
  photos: [],
  photoLimit: 8,
  photosAllLoaded: false,
  photosExhausted: false,
  selected: new Set(),
  history: {
    records: [], visibleRecords: [], mode: "day", totalCount: 0, hiddenEarlierCount: 0,
    activeIndex: null, activeChart: null, pointerY: null, pinned: false,
    page: 1, pageSize: 25,
  },
  colonyBackend: "opencfu",
  screenIdleTimeoutSeconds: 60,
  storageView: "current",
};

const I18N = {
  zh: {
    appTitle: "PetriTrace",
    loadingStatus: "正在读取状态...",
    unknown: "未知",
    running: "运行中",
    stopped: "已停止",
    intervalLabel: "拍照/记录间隔",
    secondsUnit: "秒",
    applyInterval: "应用间隔",
    startCapture: "开始定时拍照",
    stopCapture: "停止",
    captureNow: "立即拍一张",
    refresh: "刷新",
    openSettings: "打开设置",
    openDiagnostics: "打开诊断",
    returnToWindowsManager: "返回 Windows 管理器",
    openedByWindowsManager: "已由 Windows 管理器打开",
    closeDialog: "关闭",
    diagnosticsTitle: "诊断",
    dismissAlert: "忽略本次提示",
    captureStorageSummary: "拍摄与储存摘要",
    openStorageView: "切换顶部储存容量的查看对象",
    storageViewMenu: "储存容量查看对象",
    followCurrentStorage: "跟随当前写入",
    viewLocalStorage: "查看本地",
    viewExternalStorage: "查看外置",
    currentWriteStorage: "当前写入：{target}",
    viewingStorage: "正在查看：{target}",
    localStorageName: "本地",
    externalStorageName: "外置",
    localRelay: "本地接力",
    externalRelay: "外置接力",
    storageViewDetail: "{count} 张 · 剩余 {free}",
    storageUnavailable: "未连接或不可用",
    storedPhotos: "已存照片",
    photoCountValue: "{count} 张",
    estimateRemaining: "按现有照片平均大小，预计还可拍约 {count} 张",
    estimateUnavailable: "拍摄余量将在有照片后估算",
    systemReservedValue: "系统及保留 {value}",
    otherReservedValue: "其他及保留 {value}",
    photoStorageValue: "照片 {count} 张 · {size}",
    compactEstimateRemaining: "预计可拍 {count} 张",
    compactEstimateUnavailable: "尚不可估算",
    storageUsage: "储存空间",
    storageUsageValue: "已用 {used} / 共 {total}",
    storageFreeValue: "剩余 {free}",
    attentionRequired: "需要注意",
    attentionSummary: "检测到 {count} 项异常：{items}",
    viewDiagnostics: "查看诊断",
    currentIssuesTitle: "当前异常",
    recentIssuesTitle: "最近异常记录",
    noCurrentIssues: "当前未检测到异常。",
    noRecordedIssues: "没有已记录的异常。",
    sessionCaptureCount: "本次运行拍摄",
    cameraIssue: "相机异常",
    storageIssue: "储存异常",
    sensorIssue: "传感器异常",
    sensorDifferenceIssue: "传感器读数差异过大",
    powerIssue: "供电异常",
    lightIssue: "灯带异常",
    captureIssue: "拍照异常",
    analysisIssue: "菌落分析异常",
    captureScreen: "截取当前屏幕",
    openScreenshot: "打开截屏",
    downloadScreenshot: "下载截屏",
    screenshotHint: "用于远程检修触摸屏、kiosk 和页面状态。",
    screenshotReady: "截屏已更新：{filename}",
    screenshotUnavailable: "还没有截屏。",
    lightOff: "灯关",
    lightOn: "常亮",
    lightMode: "灯带",
    lightEffective: "实际亮灯",
    lightPreSeconds: "拍照前亮灯",
    lightPostSeconds: "拍照后保持",
    lightBrightness: "灯带亮度",
    screenIdleTimeout: "触控屏自动熄屏（秒，0 = 永不）",
    screenWakeNotice: "屏幕已唤醒，请再次触摸",
    environmentTitle: "环境",
    systemDetailsTitle: "系统详情",
    sensorA: "传感器 A",
    sensorB: "传感器 B",
    sensorDelta: "传感器差异",
    powerStatus: "供电",
    cpuTemp: "CPU 温度",
    ext5v: "EXT5V",
    normal: "正常",
    warning: "提醒",
    settingsTitle: "设置",
    saveSettings: "保存设置",
    languageLabel: "界面语言",
    stopServiceOnExit: "Windows 启动窗口退出时停止 Pi Web 服务",
    stopServiceHint: "默认关闭：电脑端窗口关闭后，Pi 仍继续运行。启用后，Windows 启动窗口会保持打开，并在退出时尽量停止 Pi Web 服务。",
    settingsSaved: "设置已保存。",
    generalSettingsTitle: "常规",
    captureLightingTitle: "拍照与照明",
    externalStorageTitle: "外部储存",
    externalStorageDescription: "本地优先在本地达到安全余量后由外置盘接力；外置优先直接写外置盘，缺席或容量不足时由本地接力。",
    storagePolicy: "储存策略",
    storageLocalPreferred: "本地优先，本地满后外置接力",
    storageExternalPreferred: "外置优先，缺席或满盘时本地接力",
    externalDevice: "多盘时使用的外置设备",
    externalDeviceAuto: "自动选择最早检测到的可写设备",
    externalDeviceSaved: "已保存的设备：{uuid}",
    localReserveMb: "储存安全余量（MB，本地与外置）",
    copySnapshotNow: "将当前数据复制到外置盘",
    safeEject: "安全弹出",
    externalDisabled: "已关闭",
    externalDisconnected: "未连接",
    externalConnected: "已连接",
    externalMigrating: "正在迁移本地暂存",
    externalCopyingSnapshot: "正在复制时间快照",
    externalReady: "可用",
    externalError: "异常",
    externalUnformatted: "未格式化",
    externalStorageIssue: "外置储存异常",
    externalStorageRequired: "外置优先模式下未找到可写设备",
    externalStorageNeedsFormat: "检测到未格式化设备；建议使用 NTFS。软件不会自动格式化。",
    externalStorageReadOnly: "检测到只读外置设备",
    localStorageLowIssue: "本地储存即将用尽",
    localStorageLowMessage: "本地只剩 {free}，已达到 {reserve} 的安全余量；请插入或更换外置盘。",
    externalStorageLowIssue: "外置储存即将用尽",
    externalStorageLowMessage: "外置盘 {device} 只剩 {free}，已达到 {reserve} 的安全余量；请准备安全弹出并更换储存盘。",
    externalLowSpace: "容量不足",
    externalStateLabel: "状态",
    externalDeviceLabel: "设备",
    externalFilesystemLabel: "文件系统",
    externalCapacityLabel: "剩余 / 总容量",
    externalLastSyncLabel: "最近操作",
    externalVerifiedLabel: "本轮校验",
    externalCleanedLabel: "已迁移并清理本地",
    externalNotConnectedHint: "未连接外置设备；照片继续保存在本地。",
    externalDisabledHint: "当前为仅本地模式。",
    externalReadyHint: "外置储存可用；多盘时可手动选择，未选择则使用最早检测到的可写设备。",
    externalSnapshotQueued: "已固定按键时刻的数据清单，正在执行一次性复制。",
    localSpillIssue: "本地已达安全余量",
    localSpillMessage: "后续新数据正在写入外置盘；已有本地数据不会被迁移。",
    externalFallbackIssue: "本地接力已启用",
    externalFallbackMessage: "外置盘缺席或容量不足，由本地接力保存新数据；请插入或更换外置盘。",
    externalEjected: "外置设备已安全弹出。",
    statusTitle: "状态",
    recentErrorTitle: "最近错误",
    recentPhotosTitle: "最近照片",
    selectPhoto: "选择",
    selectAll: "全选当前页",
    clearSelection: "清空选择",
    downloadSelected: "下载所选",
    deleteSelected: "删除所选",
    reloadPhotos: "刷新记录",
    loadMorePhotos: "加载更多",
    loadAllPhotos: "加载全部",
    photosLoadedCount: "本页 {count} 条",
    selectedCount: "已选 {count} 条",
    noPhotos: "还没有照片。",
    download: "下载",
    delete: "删除",
    none: "无",
    yes: "是",
    no: "否",
    statusRunning: "运行",
    statusCapturing: "正在拍照",
    statusCaptureCount: "已拍数量",
    statusLastPhoto: "最后照片",
    statusCamera: "相机",
    statusStorage: "储存",
    statusFreeSpace: "剩余空间",
    statusPhotoDir: "照片目录",
    statusWifi: "当前 Wi-Fi",
    statusWifiSignal: "Wi-Fi 信号",
    statusDownloadRate: "下载速率",
    statusUploadRate: "上传速率",
    statusLanIp: "当前网络 IP",
    statusTailscaleIp: "Tailscale IP",
    ready: "就绪",
    abnormal: "异常",
    invalidInterval: "拍照间隔必须是正数。",
    confirmDeleteOne: "删除拍摄记录 {filename}？照片、缩略图、菌落结果和该次温湿度数据将一并删除。",
    confirmDeleteMany: "删除选中的 {count} 条拍摄记录？包括照片、菌落结果和该次温湿度数据。",
    noSelection: "请先选择照片。",
    historyTitle: "环境与菌落历史",
    environmentChartTitle: "拍照时的温湿度",
    colonyChartTitle: "菌落数量",
    photoColumn: "照片",
    colonyCountColumn: "菌落数",
    sensorATemperature: "传感器 A 温度",
    sensorBTemperature: "传感器 B 温度",
    sensorAHumidity: "传感器 A 湿度",
    sensorBHumidity: "传感器 B 湿度",
    loadHistory: "查询",
    exportCsv: "导出 CSV",
    historyRangeMode: "历史时间范围",
    historyModeDay: "近1天",
    historyModeThreeDays: "近3天",
    historyModeWeek: "近1周",
    historyPresetSummary: "{range}：{count} 个拍照数据点。",
    historyModeAll: "全部",
    historyModeCustom: "自定义",
    historyAllSummary: "全部范围：已显示全部 {count} 个拍照数据点。",
    historyCustomSummary: "自定义范围：已显示 {count} 个拍照数据点。",
    historyStart: "开始时间",
    historyEnd: "结束时间",
    timeColumn: "时间",
    actionColumn: "操作",
    historyDetailsTitle: "详细记录",
    photoColumn: "照片 / 文件名",
    photoUnavailable: "照片不可用",
    historyDetailsCount: "当前 {count} 条",
    historyPagination: "历史明细分页",
    previousPage: "上一页",
    nextPage: "下一页",
    pageStatus: "第 {page} / {pages} 页",
    viewPhoto: "查看照片",
    environmentChartAria: "拍照时温湿度历史图。悬停或轻点数据点查看精确数值；方向键可切换数据点。",
    colonyChartAria: "菌落数量历史图。悬停或轻点数据点查看精确数值；方向键可切换数据点。",
    historyPointHint: "轻点固定；再次轻点或按 Escape 关闭",
    historyCount: "{count} 个环境记录点，{colonies} 个菌落计数结果",
    noHistory: "该范围内还没有记录。",
    chartNoData: "暂无历史数据",
    photoEvent: "拍照",
    captureErrorEvent: "拍照失败",
  },
  en: {
    appTitle: "PetriTrace",
    loadingStatus: "Loading status...",
    unknown: "Unknown",
    running: "Running",
    stopped: "Stopped",
    intervalLabel: "Capture / record interval",
    secondsUnit: "sec",
    applyInterval: "Apply Interval",
    startCapture: "Start Timed Capture",
    stopCapture: "Stop",
    captureNow: "Capture Now",
    refresh: "Refresh",
    openSettings: "Open settings",
    openDiagnostics: "Open diagnostics",
    returnToWindowsManager: "Return to Windows Manager",
    openedByWindowsManager: "Opened by Windows Manager",
    closeDialog: "Close",
    diagnosticsTitle: "Diagnostics",
    dismissAlert: "Dismiss this notification",
    captureStorageSummary: "Capture and storage summary",
    openStorageView: "Choose which storage capacity is shown in the header",
    storageViewMenu: "Storage capacity view",
    followCurrentStorage: "Follow current write target",
    viewLocalStorage: "View local storage",
    viewExternalStorage: "View external storage",
    currentWriteStorage: "Writing to: {target}",
    viewingStorage: "Viewing: {target}",
    localStorageName: "Local",
    externalStorageName: "External",
    localRelay: "Local relay",
    externalRelay: "External relay",
    storageViewDetail: "{count} photos · {free} free",
    storageUnavailable: "Disconnected or unavailable",
    storedPhotos: "Stored photos",
    photoCountValue: "{count} photos",
    estimateRemaining: "About {count} more at the current average photo size",
    estimateUnavailable: "Remaining capacity will be estimated after a photo is stored",
    systemReservedValue: "System & reserved {value}",
    otherReservedValue: "Other & reserved {value}",
    photoStorageValue: "Photos {count} · {size}",
    compactEstimateRemaining: "Est. {count} more",
    compactEstimateUnavailable: "Estimate unavailable",
    storageUsage: "Storage",
    storageUsageValue: "{used} used / {total} total",
    storageFreeValue: "{free} free",
    attentionRequired: "Attention required",
    attentionSummary: "{count} issue(s) detected: {items}",
    viewDiagnostics: "View diagnostics",
    currentIssuesTitle: "Current Issues",
    recentIssuesTitle: "Recent Issue Log",
    noCurrentIssues: "No current issues detected.",
    noRecordedIssues: "No recorded issues.",
    sessionCaptureCount: "This-session captures",
    cameraIssue: "Camera issue",
    storageIssue: "Storage issue",
    sensorIssue: "Sensor issue",
    sensorDifferenceIssue: "Sensor readings differ too much",
    powerIssue: "Power issue",
    lightIssue: "Light issue",
    captureIssue: "Capture issue",
    analysisIssue: "Colony analysis issue",
    captureScreen: "Capture Screen",
    openScreenshot: "Open Screenshot",
    downloadScreenshot: "Download Screenshot",
    screenshotHint: "For remote checks of the touchscreen, kiosk, and page state.",
    screenshotReady: "Screenshot updated: {filename}",
    screenshotUnavailable: "No screenshot yet.",
    lightOff: "Light Off",
    lightOn: "Always On",
    lightMode: "Light",
    lightEffective: "Light output",
    lightPreSeconds: "Pre-light",
    lightPostSeconds: "Post-light",
    lightBrightness: "Light brightness",
    screenIdleTimeout: "Touchscreen sleep timeout (seconds, 0 = never)",
    screenWakeNotice: "Screen awake — touch again",
    environmentTitle: "Environment",
    systemDetailsTitle: "System Details",
    sensorA: "Sensor A",
    sensorB: "Sensor B",
    sensorDelta: "Sensor delta",
    powerStatus: "Power",
    cpuTemp: "CPU temp",
    ext5v: "EXT5V",
    normal: "Normal",
    warning: "Warning",
    settingsTitle: "Settings",
    saveSettings: "Save Settings",
    languageLabel: "Interface language",
    stopServiceOnExit: "Stop Pi web service when the Windows launcher exits",
    stopServiceHint: "Default off: the Pi keeps running after the Windows window closes. When enabled, the Windows launcher stays open and tries to stop the Pi web service on exit.",
    settingsSaved: "Settings saved.",
    generalSettingsTitle: "General",
    captureLightingTitle: "Capture and lighting",
    externalStorageTitle: "External storage",
    externalStorageDescription: "Local-first lets external storage take over after the local safety reserve is reached. External-first writes directly outside; local storage takes over when it is absent or full.",
    storagePolicy: "Storage policy",
    storageLocalPreferred: "Local first, external spillover when full",
    storageExternalPreferred: "External first, local relay when absent or full",
    externalDevice: "External device when several are present",
    externalDeviceAuto: "Automatically use the earliest detected writable device",
    externalDeviceSaved: "Saved device: {uuid}",
    localReserveMb: "Storage safety reserve (MB, local and external)",
    copySnapshotNow: "Copy current data snapshot to external drive",
    safeEject: "Safely eject",
    externalDisabled: "Disabled",
    externalDisconnected: "Disconnected",
    externalConnected: "Connected",
    externalMigrating: "Moving local fallback data",
    externalCopyingSnapshot: "Copying point-in-time snapshot",
    externalReady: "Available",
    externalError: "Error",
    externalUnformatted: "Unformatted",
    externalStorageIssue: "External storage issue",
    externalStorageRequired: "No writable device found while external-first mode is active",
    externalStorageNeedsFormat: "An unformatted device was detected. NTFS is recommended. The software will not format it automatically.",
    externalStorageReadOnly: "A read-only external device was detected",
    localStorageLowIssue: "Local storage nearly full",
    localStorageLowMessage: "Only {free} remains locally, reaching the {reserve} safety reserve. Attach or replace an external drive.",
    externalStorageLowIssue: "External storage nearly full",
    externalStorageLowMessage: "External drive {device} has only {free} remaining, reaching the {reserve} safety reserve. Prepare to eject it safely and replace the drive.",
    externalLowSpace: "Low capacity",
    externalStateLabel: "State",
    externalDeviceLabel: "Device",
    externalFilesystemLabel: "Filesystem",
    externalCapacityLabel: "Free / total",
    externalLastSyncLabel: "Last operation",
    externalVerifiedLabel: "Verified this run",
    externalCleanedLabel: "Migrated and removed locally",
    externalNotConnectedHint: "No external device connected; photos continue to use local storage.",
    externalDisabledHint: "Local-only mode is active.",
    externalReadyHint: "External storage is available. With several drives, choose one manually or use the earliest detected writable drive.",
    externalSnapshotQueued: "The data inventory was fixed at button time; the one-off copy is running.",
    localSpillIssue: "Local safety reserve reached",
    localSpillMessage: "New data is being written externally; existing local data is not migrated.",
    externalFallbackIssue: "Local relay is active",
    externalFallbackMessage: "The external drive is absent or full, so local storage is taking over new data. Insert or replace the external drive.",
    externalEjected: "External device safely ejected.",
    statusTitle: "Status",
    recentErrorTitle: "Recent Error",
    recentPhotosTitle: "Recent Photos",
    selectPhoto: "Select",
    selectAll: "Select page",
    clearSelection: "Clear Selection",
    downloadSelected: "Download Selected",
    deleteSelected: "Delete Selected",
    reloadPhotos: "Refresh records",
    loadMorePhotos: "Load More",
    loadAllPhotos: "Load All",
    photosLoadedCount: "Showing {count}",
    selectedCount: "{count} selected",
    noPhotos: "No photos yet.",
    download: "Download",
    delete: "Delete",
    none: "None",
    yes: "Yes",
    no: "No",
    statusRunning: "Running",
    statusCapturing: "Capturing",
    statusCaptureCount: "Capture count",
    statusLastPhoto: "Last photo",
    statusCamera: "Camera",
    statusStorage: "Storage",
    statusFreeSpace: "Free space",
    statusPhotoDir: "Photo directory",
    statusWifi: "Current Wi-Fi",
    statusWifiSignal: "Wi-Fi signal",
    statusDownloadRate: "Download rate",
    statusUploadRate: "Upload rate",
    statusLanIp: "Current network IP",
    statusTailscaleIp: "Tailscale IP",
    ready: "Ready",
    abnormal: "Error",
    invalidInterval: "Capture interval must be a positive number.",
    confirmDeleteOne: "Delete capture {filename}, including photo, thumbnail, colony results and capture-linked sensor data?",
    confirmDeleteMany: "Delete {count} captures, including photos, colony results and capture-linked sensor data?",
    noSelection: "Select photos first.",
    historyTitle: "Environment and Colony History",
    environmentChartTitle: "Temperature and humidity at capture",
    colonyChartTitle: "Colony count",
    photoColumn: "Photo",
    colonyCountColumn: "Colony count",
    sensorATemperature: "Sensor A temperature",
    sensorBTemperature: "Sensor B temperature",
    sensorAHumidity: "Sensor A humidity",
    sensorBHumidity: "Sensor B humidity",
    loadHistory: "Load",
    exportCsv: "Export CSV",
    historyRangeMode: "History time range",
    historyModeDay: "Last day",
    historyModeThreeDays: "Last 3 days",
    historyModeWeek: "Last week",
    historyPresetSummary: "{range}: {count} capture data points.",
    historyModeAll: "All",
    historyModeCustom: "Custom",
    historyAllSummary: "All range: showing all {count} capture data points.",
    historyCustomSummary: "Custom range: showing {count} capture data points.",
    historyStart: "Start",
    historyEnd: "End",
    timeColumn: "Time",
    actionColumn: "Action",
    historyDetailsTitle: "Detailed records",
    photoColumn: "Photo / filename",
    photoUnavailable: "Photo unavailable",
    historyDetailsCount: "{count} shown",
    historyPagination: "History detail pages",
    previousPage: "Previous",
    nextPage: "Next",
    pageStatus: "Page {page} / {pages}",
    viewPhoto: "View photo",
    environmentChartAria: "Temperature and humidity history at capture. Hover or tap a point for exact values; use arrow keys to move between points.",
    colonyChartAria: "Colony count history. Hover or tap a point for exact values; use arrow keys to move between points.",
    historyPointHint: "Tap to pin; tap again or press Escape to close",
    historyCount: "{count} environment samples, {colonies} colony results",
    noHistory: "No samples in this range.",
    chartNoData: "No history data",
    photoEvent: "Photo",
    captureErrorEvent: "Capture failed",
  },
  de: {
    appTitle: "PetriTrace",
    loadingStatus: "Status wird geladen...",
    unknown: "Unbekannt",
    running: "Läuft",
    stopped: "Gestoppt",
    intervalLabel: "Aufnahme-/Protokollintervall",
    secondsUnit: "Sek.",
    applyInterval: "Intervall übernehmen",
    startCapture: "Zeitaufnahme starten",
    stopCapture: "Stopp",
    captureNow: "Jetzt aufnehmen",
    refresh: "Aktualisieren",
    openSettings: "Einstellungen öffnen",
    openDiagnostics: "Diagnose öffnen",
    returnToWindowsManager: "Zum Windows-Manager zurückkehren",
    openedByWindowsManager: "Vom Windows-Manager geöffnet",
    closeDialog: "Schließen",
    diagnosticsTitle: "Diagnose",
    dismissAlert: "Diesen Hinweis ausblenden",
    captureStorageSummary: "Aufnahme- und Speicherübersicht",
    openStorageView: "Angezeigten Speicherplatz im Kopfbereich wechseln",
    storageViewMenu: "Speicherplatzansicht",
    followCurrentStorage: "Aktuellem Schreibziel folgen",
    viewLocalStorage: "Lokalen Speicher anzeigen",
    viewExternalStorage: "Externen Speicher anzeigen",
    currentWriteStorage: "Schreibziel: {target}",
    viewingStorage: "Anzeige: {target}",
    localStorageName: "Lokal",
    externalStorageName: "Extern",
    localRelay: "Lokale Übernahme",
    externalRelay: "Externe Übernahme",
    storageViewDetail: "{count} Fotos · {free} frei",
    storageUnavailable: "Nicht verbunden oder nicht verfügbar",
    storedPhotos: "Gespeicherte Fotos",
    photoCountValue: "{count} Fotos",
    estimateRemaining: "Bei aktueller mittlerer Dateigröße noch etwa {count} Fotos",
    estimateUnavailable: "Die Restkapazität wird nach dem ersten Foto geschätzt",
    systemReservedValue: "System & reserviert {value}",
    otherReservedValue: "Sonstiges & reserviert {value}",
    photoStorageValue: "Fotos {count} · {size}",
    compactEstimateRemaining: "Noch ca. {count}",
    compactEstimateUnavailable: "Noch nicht schätzbar",
    storageUsage: "Speicher",
    storageUsageValue: "{used} belegt / {total} gesamt",
    storageFreeValue: "{free} frei",
    attentionRequired: "Aufmerksamkeit erforderlich",
    attentionSummary: "{count} Problem(e) erkannt: {items}",
    viewDiagnostics: "Diagnose anzeigen",
    currentIssuesTitle: "Aktuelle Probleme",
    recentIssuesTitle: "Letzte Problemereignisse",
    noCurrentIssues: "Keine aktuellen Probleme erkannt.",
    noRecordedIssues: "Keine Probleme protokolliert.",
    sessionCaptureCount: "Aufnahmen dieser Sitzung",
    cameraIssue: "Kameraproblem",
    storageIssue: "Speicherproblem",
    sensorIssue: "Sensorproblem",
    sensorDifferenceIssue: "Sensorwerte weichen zu stark ab",
    powerIssue: "Stromversorgungsproblem",
    lightIssue: "Lichtproblem",
    captureIssue: "Aufnahmeproblem",
    analysisIssue: "Problem bei der Kolonieanalyse",
    captureScreen: "Bildschirm aufnehmen",
    openScreenshot: "Screenshot öffnen",
    downloadScreenshot: "Screenshot herunterladen",
    screenshotHint: "Für Fernprüfung von Touchscreen, Kiosk und Seitenzustand.",
    screenshotReady: "Screenshot aktualisiert: {filename}",
    screenshotUnavailable: "Noch kein Screenshot.",
    lightOff: "Licht aus",
    lightOn: "Dauerlicht",
    lightMode: "Lichtband",
    lightEffective: "Lichtausgabe",
    lightPreSeconds: "Vorlicht",
    lightPostSeconds: "Nachlicht",
    lightBrightness: "Lichthelligkeit",
    screenIdleTimeout: "Touchscreen ausschalten (Sekunden, 0 = nie)",
    screenWakeNotice: "Bildschirm aktiv – bitte erneut berühren",
    environmentTitle: "Umgebung",
    systemDetailsTitle: "Systemdetails",
    sensorA: "Sensor A",
    sensorB: "Sensor B",
    sensorDelta: "Sensorabweichung",
    powerStatus: "Stromversorgung",
    cpuTemp: "CPU-Temperatur",
    ext5v: "EXT5V",
    normal: "Normal",
    warning: "Warnung",
    settingsTitle: "Einstellungen",
    saveSettings: "Einstellungen speichern",
    languageLabel: "Sprache der Oberfläche",
    stopServiceOnExit: "Pi-Webdienst beenden, wenn der Windows-Starter beendet wird",
    stopServiceHint: "Standard: aus. Der Pi läuft weiter, wenn das Windows-Fenster geschlossen wird. Wenn aktiv, bleibt der Windows-Starter offen und versucht beim Beenden den Pi-Webdienst zu stoppen.",
    settingsSaved: "Einstellungen gespeichert.",
    generalSettingsTitle: "Allgemein",
    captureLightingTitle: "Aufnahme und Beleuchtung",
    externalStorageTitle: "Externer Speicher",
    externalStorageDescription: "Bei Lokal zuerst übernimmt das externe Laufwerk nach Erreichen der lokalen Sicherheitsreserve. Bei Extern zuerst übernimmt der lokale Speicher, wenn das Laufwerk fehlt oder voll ist.",
    storagePolicy: "Speicherstrategie",
    storageLocalPreferred: "Lokal zuerst, extern weiter bei vollem Speicher",
    storageExternalPreferred: "Extern zuerst, lokale Übernahme bei Abwesenheit oder vollem Laufwerk",
    externalDevice: "Externes Laufwerk bei mehreren Geräten",
    externalDeviceAuto: "Frühest erkanntes beschreibbares Laufwerk automatisch verwenden",
    externalDeviceSaved: "Gespeichertes Laufwerk: {uuid}",
    localReserveMb: "Speicher-Sicherheitsreserve (MB, lokal und extern)",
    copySnapshotNow: "Aktuellen Datenstand auf externes Laufwerk kopieren",
    safeEject: "Sicher auswerfen",
    externalDisabled: "Deaktiviert",
    externalDisconnected: "Nicht verbunden",
    externalConnected: "Verbunden",
    externalMigrating: "Lokale Ausweichdaten werden verschoben",
    externalCopyingSnapshot: "Zeitpunktkopie wird erstellt",
    externalReady: "Verfügbar",
    externalError: "Fehler",
    externalUnformatted: "Nicht formatiert",
    externalStorageIssue: "Problem mit externem Speicher",
    externalStorageRequired: "Im Modus Extern zuerst wurde kein beschreibbares Laufwerk gefunden",
    externalStorageNeedsFormat: "Ein unformatiertes Laufwerk wurde erkannt. NTFS wird empfohlen. Die Software formatiert nicht automatisch.",
    externalStorageReadOnly: "Ein schreibgeschütztes externes Laufwerk wurde erkannt",
    localStorageLowIssue: "Lokaler Speicher fast voll",
    localStorageLowMessage: "Lokal sind nur noch {free} frei; die Sicherheitsreserve von {reserve} ist erreicht. Externes Laufwerk anschließen oder wechseln.",
    externalStorageLowIssue: "Externer Speicher fast voll",
    externalStorageLowMessage: "Auf dem externen Laufwerk {device} sind nur noch {free} frei; die Sicherheitsreserve von {reserve} ist erreicht. Sicher auswerfen und Laufwerk wechseln.",
    externalLowSpace: "Kapazität knapp",
    externalStateLabel: "Status",
    externalDeviceLabel: "Laufwerk",
    externalFilesystemLabel: "Dateisystem",
    externalCapacityLabel: "Frei / gesamt",
    externalLastSyncLabel: "Letzter Vorgang",
    externalVerifiedLabel: "Diesmal geprüft",
    externalCleanedLabel: "Lokal verschoben und entfernt",
    externalNotConnectedHint: "Kein externes Laufwerk verbunden; Fotos werden weiterhin lokal gespeichert.",
    externalDisabledHint: "Der Modus Nur lokal ist aktiv.",
    externalReadyHint: "Externer Speicher ist verfügbar. Bei mehreren Laufwerken manuell wählen oder das frühest erkannte beschreibbare Laufwerk verwenden.",
    externalSnapshotQueued: "Die Datenliste wurde beim Tastendruck fixiert; die einmalige Kopie läuft.",
    localSpillIssue: "Lokale Sicherheitsreserve erreicht",
    localSpillMessage: "Neue Daten werden extern geschrieben; vorhandene lokale Daten werden nicht verschoben.",
    externalFallbackIssue: "Lokale Übernahme aktiv",
    externalFallbackMessage: "Das externe Laufwerk fehlt oder ist voll; der lokale Speicher übernimmt neue Daten. Laufwerk einsetzen oder wechseln.",
    externalEjected: "Externes Laufwerk sicher ausgeworfen.",
    statusTitle: "Status",
    recentErrorTitle: "Letzter Fehler",
    recentPhotosTitle: "Neueste Fotos",
    selectPhoto: "Auswählen",
    selectAll: "Seite auswählen",
    clearSelection: "Auswahl löschen",
    downloadSelected: "Auswahl herunterladen",
    deleteSelected: "Auswahl löschen",
    reloadPhotos: "Aufnahmen aktualisieren",
    loadMorePhotos: "Mehr laden",
    loadAllPhotos: "Alle laden",
    photosLoadedCount: "{count} angezeigt",
    selectedCount: "{count} ausgewählt",
    noPhotos: "Noch keine Fotos.",
    download: "Herunterladen",
    delete: "Löschen",
    none: "Keine",
    yes: "Ja",
    no: "Nein",
    statusRunning: "Läuft",
    statusCapturing: "Aufnahme läuft",
    statusCaptureCount: "Anzahl Aufnahmen",
    statusLastPhoto: "Letztes Foto",
    statusCamera: "Kamera",
    statusStorage: "Speicher",
    statusFreeSpace: "Freier Speicher",
    statusPhotoDir: "Fotoverzeichnis",
    statusWifi: "Aktuelles WLAN",
    statusWifiSignal: "WLAN-Signal",
    statusDownloadRate: "Downloadrate",
    statusUploadRate: "Uploadrate",
    statusLanIp: "Aktuelle Netzwerk-IP",
    statusTailscaleIp: "Tailscale-IP",
    ready: "Bereit",
    abnormal: "Fehler",
    invalidInterval: "Das Aufnahmeintervall muss eine positive Zahl sein.",
    confirmDeleteOne: "Aufnahme {filename} samt Foto, Vorschaubild, Koloniezählung und zugehörigen Messwerten löschen?",
    confirmDeleteMany: "{count} Aufnahmen samt Fotos, Koloniezählungen und zugehörigen Messwerten löschen?",
    noSelection: "Bitte zuerst Fotos auswählen.",
    historyTitle: "Umgebungs- und Kolonieverlauf",
    environmentChartTitle: "Temperatur und Feuchte bei Aufnahme",
    colonyChartTitle: "Koloniezahl",
    photoColumn: "Foto",
    colonyCountColumn: "Koloniezahl",
    sensorATemperature: "Sensor A Temperatur",
    sensorBTemperature: "Sensor B Temperatur",
    sensorAHumidity: "Sensor A Feuchte",
    sensorBHumidity: "Sensor B Feuchte",
    loadHistory: "Laden",
    exportCsv: "CSV exportieren",
    historyRangeMode: "Zeitraum des Verlaufs",
    historyModeDay: "Letzter Tag",
    historyModeThreeDays: "Letzte 3 Tage",
    historyModeWeek: "Letzte Woche",
    historyPresetSummary: "{range}: {count} Aufnahmepunkte.",
    historyModeAll: "Alle",
    historyModeCustom: "Benutzerdefiniert",
    historyAllSummary: "Gesamter Bereich: alle {count} Aufnahmepunkte werden angezeigt.",
    historyCustomSummary: "Benutzerdefinierter Bereich: {count} Aufnahmepunkte werden angezeigt.",
    historyStart: "Start",
    historyEnd: "Ende",
    timeColumn: "Zeit",
    actionColumn: "Aktion",
    historyDetailsTitle: "Detaillierte Einträge",
    photoColumn: "Foto / Dateiname",
    photoUnavailable: "Foto nicht verfügbar",
    historyDetailsCount: "{count} angezeigt",
    historyPagination: "Seiten der Verlaufsdetails",
    previousPage: "Zurück",
    nextPage: "Weiter",
    pageStatus: "Seite {page} / {pages}",
    viewPhoto: "Foto anzeigen",
    environmentChartAria: "Temperatur- und Feuchteverlauf bei der Aufnahme. Punkt mit Maus oder Berührung wählen; Pfeiltasten wechseln den Datenpunkt.",
    colonyChartAria: "Verlauf der Koloniezahl. Punkt mit Maus oder Berührung wählen; Pfeiltasten wechseln den Datenpunkt.",
    historyPointHint: "Antippen zum Fixieren; erneut tippen oder Escape zum Schließen",
    historyCount: "{count} Umweltmesspunkte, {colonies} Koloniezählungen",
    noHistory: "Keine Messpunkte in diesem Zeitraum.",
    chartNoData: "Keine Verlaufsdaten",
    photoEvent: "Foto",
    captureErrorEvent: "Aufnahmefehler",
  },
};

async function requestJson(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || JSON.stringify(data));
  }
  return data;
}

async function post(url, payload = {}) {
  return requestJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

Object.assign(I18N.zh, {"captureWorkspace": "拍摄控制", "captureWorkspaceHint": "定时采集与单次记录", "exportTitle": "导出", "exportRange": "导出此范围", "exportSelected": "导出所选", "exportRecord": "导出此记录", "downloadOriginal": "下载原图", "previousPhoto": "上一张", "nextPhoto": "下一张", "zoomPhoto": "放大 / 适应", "exportScope": "范围", "exportCurrent": "当前筛选范围", "exportContents": "包含内容", "exportAllContents": "全选内容", "exportPhotos": "原始照片", "exportCounts": "菌落计数（两种算法及状态）", "exportCaptureSensors": "拍摄时温湿度", "exportEnvironment": "独立环境采样（按时间范围）", "exportFormatHint": "单类数据为 CSV；照片或多类内容为 ZIP", "exportStartAction": "开始导出", "exportCalculating": "正在估算…", "exportEstimate": "{records} 条记录 · {photos} 张照片 · {environment} 条独立采样 · 约 {size} MB · {format}", "exportSubmitted": "请求已提交，文件生成后浏览器将开始下载。", "pageCapacity": "本页 {count} 条 · 每页25条", "chartSampled": "图表已按区间保留峰值与趋势，详细记录和导出保持原始数据。"});
Object.assign(I18N.en, {"captureWorkspace": "Capture", "captureWorkspaceHint": "Scheduled collection and individual captures", "exportTitle": "Export", "exportRange": "Export range", "exportSelected": "Export selected", "exportRecord": "Export this record", "downloadOriginal": "Original image", "previousPhoto": "Previous photo", "nextPhoto": "Next photo", "zoomPhoto": "Zoom / fit", "exportScope": "Scope", "exportCurrent": "Current filter", "exportContents": "Include", "exportAllContents": "Select all contents", "exportPhotos": "Original photos", "exportCounts": "Colony counts (both algorithms and status)", "exportCaptureSensors": "Capture-time temperature and humidity", "exportEnvironment": "Independent environmental samples (time range)", "exportFormatHint": "One data category: CSV. Photos or multiple categories: ZIP.", "exportStartAction": "Start export", "exportCalculating": "Estimating…", "exportEstimate": "{records} records · {photos} photos · {environment} independent samples · approx. {size} MB · {format}", "exportSubmitted": "Request submitted. Your browser will download the file once it is prepared.", "pageCapacity": "{count} on this page · 25 per page", "chartSampled": "Chart retains interval extrema and trends; records and exports contain original data."});
Object.assign(I18N.de, {"captureWorkspace": "Aufnahme", "captureWorkspaceHint": "Zeitplan und einzelne Aufnahmen", "exportTitle": "Exportieren", "exportRange": "Zeitraum exportieren", "exportSelected": "Auswahl exportieren", "exportRecord": "Aufnahme exportieren", "downloadOriginal": "Originalbild", "previousPhoto": "Vorheriges Foto", "nextPhoto": "Nächstes Foto", "zoomPhoto": "Vergrößern / einpassen", "exportScope": "Bereich", "exportCurrent": "Aktueller Filter", "exportContents": "Inhalt", "exportAllContents": "Alle Inhalte wählen", "exportPhotos": "Originalfotos", "exportCounts": "Koloniezählungen (beide Verfahren und Status)", "exportCaptureSensors": "Temperatur und Feuchte zur Aufnahme", "exportEnvironment": "Unabhängige Umgebungsmessungen (Zeitraum)", "exportFormatHint": "Eine Datenart: CSV. Fotos oder mehrere Arten: ZIP.", "exportStartAction": "Export starten", "exportCalculating": "Wird geschätzt…", "exportEstimate": "{records} Aufnahmen · {photos} Fotos · {environment} Messungen · ca. {size} MB · {format}", "exportSubmitted": "Anfrage gesendet. Der Download beginnt nach der Vorbereitung.", "pageCapacity": "{count} auf dieser Seite · 25 pro Seite", "chartSampled": "Diagramm mit Intervall-Extremwerten; Einträge und Export enthalten Originaldaten."});

Object.assign(I18N.zh, {reloadPage: "重新加载网页", updateReady: "界面已更新，点击重新加载网页"});
Object.assign(I18N.en, {reloadPage: "Reload page", updateReady: "Interface updated. Click to reload the page"});
Object.assign(I18N.de, {reloadPage: "Seite neu laden", updateReady: "Oberfläche aktualisiert. Zum Neuladen klicken"});
Object.assign(I18N.zh, {"recordHeaderCount": "本页 {count} 条 / 每页25条 · 共 {total} 条", "recordCountCompact": "{count} 条记录", "applyRange": "应用范围", "refreshEverything": "刷新设备状态、图表和记录"});
Object.assign(I18N.en, {"recordHeaderCount": "{count} on page / 25 per page · {total} total", "recordCountCompact": "{count} records", "applyRange": "Apply range", "refreshEverything": "Refresh device status, charts and records"});
Object.assign(I18N.de, {"recordHeaderCount": "{count} auf Seite / 25 je Seite · {total} gesamt", "recordCountCompact": "{count} Einträge", "applyRange": "Zeitraum anwenden", "refreshEverything": "Gerätestatus, Diagramme und Einträge aktualisieren"});
Object.assign(I18N.zh, {locateRecord:"定位此拍摄记录",historyPointHint:"点击定位下方记录；按 Esc 取消定位。"});
Object.assign(I18N.en, {locateRecord:"Locate this capture",historyPointHint:"Click to locate the record below; Esc clears the marker."});
Object.assign(I18N.de, {locateRecord:"Aufnahme zuordnen",historyPointHint:"Klicken zeigt den Eintrag unten; Esc entfernt die Markierung."});
function t(key, vars = {}) {
  const value = (I18N[state.language] || I18N.en)[key] || I18N.zh[key] || key;
  return Object.entries(vars).reduce((text, [name, replacement]) => text.replaceAll(`{${name}}`, String(replacement)), value);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

function detectDisplayMode() {
  const params = new URLSearchParams(window.location.search);
  return params.get("display") === "kiosk" ? "kiosk" : "remote";
}

function isKioskDisplay() {
  return state.displayMode === "kiosk";
}

function applyDisplayMode() {
  document.body.classList.toggle("kiosk-display", isKioskDisplay());
}

function showManagerEntryToast(visible) {
  const toast = $("windowsManagerEntryToast");
  window.clearTimeout(managerEntryToastTimer);
  window.clearTimeout(managerEntryToastHideTimer);
  managerEntryToastTimer = null;
  managerEntryToastHideTimer = null;
  toast.classList.remove("is-visible");

  if (!visible) {
    toast.hidden = true;
    return;
  }

  toast.hidden = false;
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      if (state.entrySource === "windows-manager") {
        toast.classList.add("is-visible");
      }
    });
  });
  managerEntryToastTimer = window.setTimeout(() => {
    toast.classList.remove("is-visible");
    managerEntryToastHideTimer = window.setTimeout(() => {
      toast.hidden = true;
      managerEntryToastHideTimer = null;
    }, MANAGER_ENTRY_TOAST_EXIT_MS);
    managerEntryToastTimer = null;
  }, MANAGER_ENTRY_TOAST_DURATION_MS);
}

function applyEntryContext() {
  const isManagerEntry = window.PiEntryContext.isWindowsManagerEntry(window.location.search, state.displayMode);
  state.entrySource = isManagerEntry ? "windows-manager" : null;
  document.body.classList.toggle("windows-manager-entry", isManagerEntry);
  $("windowsManagerReturn").hidden = !isManagerEntry;
  showManagerEntryToast(isManagerEntry);
}

function row(label, value) {
  return `<dt>${label}</dt><dd>${value ?? ""}</dd>`;
}

function formatRate(kbps) {
  if (!Number.isFinite(kbps)) {
    return t("none");
  }
  if (kbps >= 1000) {
    return `${(kbps / 1000).toFixed(2)} Mbit/s`;
  }
  return `${kbps.toFixed(1)} kbit/s`;
}

function numberLocale() {
  return state.language === "de" ? "de-DE" : state.language === "en" ? "en-US" : "zh-CN";
}

function formatInteger(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.round(number).toLocaleString(numberLocale()) : "—";
}

function formatStorageMb(value) {
  const megabytes = Number(value);
  if (!Number.isFinite(megabytes)) return "—";
  if (megabytes >= 1024) {
    return `${(megabytes / 1024).toLocaleString(numberLocale(), { maximumFractionDigits: 1 })} GB`;
  }
  return `${Math.max(0, Math.round(megabytes)).toLocaleString(numberLocale())} MB`;
}

function formatStorageBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes)) return "—";
  const megabytes = bytes / (1024 * 1024);
  if (megabytes >= 1024) return formatStorageMb(megabytes);
  if (megabytes >= 1) {
    return `${megabytes.toLocaleString(numberLocale(), { maximumFractionDigits: 1 })} MB`;
  }
  const kilobytes = Math.max(0, bytes / 1024);
  return `${kilobytes.toLocaleString(numberLocale(), { maximumFractionDigits: 0 })} KB`;
}

function formatSensor(sensor) {
  if (!sensor || sensor.status !== "ok") {
    return t("abnormal");
  }
  return `${sensor.temperature_c} °C / ${sensor.humidity_percent} %RH`;
}

function formatTime(value) {
  if (!value) {
    return t("none");
  }
  return String(value).replace("T", " ").slice(0, 19);
}

function toDateTimeLocal(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function historyPointCapacity() {
  const canvas = $("colonyHistoryChart") || $("environmentHistoryChart");
  const plotWidth = Math.max(240, (canvas?.clientWidth || canvas?.width || 1100) - 128);
  return Math.max(80, Math.min(400, Math.floor(plotWidth / 3)));
}

function ensureCustomHistoryRange() {
  const visible = state.history.visibleRecords || [];
  if (!$("historyStart").value) {
    const first = visible[0]?.timestampMs;
    $("historyStart").value = toDateTimeLocal(new Date(Number.isFinite(first) ? first : Date.now() - 24 * 60 * 60_000));
  }
  if (!$("historyEnd").value) {
    const last = visible[visible.length - 1]?.timestampMs;
    $("historyEnd").value = toDateTimeLocal(new Date(Number.isFinite(last) ? last : Date.now()));
  }
}

function queryStringFromHistoryFilters(extra = {}) {
  const mode = state.history.mode || "day";
  const params = new URLSearchParams({ mode, ...extra });
  const bounds = window.PiHistoryRange.presetHistoryBounds(mode);
  if (bounds) {
    state.history.requestBounds = bounds;
    params.set("mode", "custom");
    params.set("limit", "all");
    params.set("start", toDateTimeLocal(new Date(bounds.start)));
    params.set("end", toDateTimeLocal(new Date(bounds.end)));
  } else if (mode === "all") {
    params.set("limit", "all");
  } else {
    ensureCustomHistoryRange();
    params.set("limit", "all");
    const start = $("historyStart").value;
    const end = $("historyEnd").value;
    if (start) params.set("start", start);
    if (end) params.set("end", end);
  }
  return params.toString();
}

Object.assign(I18N.zh, {"screenTools": "屏幕检修", "lightPreSeconds": "拍照前亮灯（秒）", "lightPostSeconds": "拍照后保持（秒）", "lightBrightness": "灯带亮度（0–1）"});
Object.assign(I18N.en, {"screenTools": "Display inspection", "lightPreSeconds": "Light before capture (s)", "lightPostSeconds": "Light after capture (s)", "lightBrightness": "LED brightness (0–1)"});
Object.assign(I18N.de, {"screenTools": "Bildschirmprüfung", "lightPreSeconds": "Licht vor Aufnahme (s)", "lightPostSeconds": "Licht nach Aufnahme (s)", "lightBrightness": "LED-Helligkeit (0–1)"});

Object.assign(I18N.zh, {exportChooseContents:"请选择要导出的内容。"});
Object.assign(I18N.en, {exportChooseContents:"Choose the contents to export."});
Object.assign(I18N.de, {exportChooseContents:"Wählen Sie die zu exportierenden Inhalte."});

function applyLanguage(language) {
  state.language = I18N[language] ? language : "en";
  localStorage.setItem("piCameraLanguage", state.language);
  document.documentElement.lang = { zh: "zh-CN", en: "en", de: "de" }[state.language];
  document.title = t("appTitle");
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.getAttribute("data-i18n"));
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
    node.setAttribute("aria-label", t(node.getAttribute("data-i18n-aria-label")));
  });
  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.setAttribute("title", t(node.getAttribute("data-i18n-title")));
  });
  renderStatus(state.status);
  if (state.latestScreenshot !== undefined) renderScreenshot(state.latestScreenshot, {showPreview: state.screenshotPreviewVisible});
  if (state.diagnosticEvents) renderDiagnosticEvents(state.diagnosticEvents);
  if ($("exportDialog").open) { $("exportStatus").textContent = state.exportSubmitted ? t("exportSubmitted") : ""; updateExportPreview(); }
  if ($("settingsSaved").textContent) $("settingsSaved").textContent = t("settingsSaved");
  renderPhotos();
  renderHistory();
  syncBulkControls();
}

function setBadge(running) {
  const badge = $("badge");
  badge.className = `badge ${running ? "running" : "stopped"}`;
  badge.textContent = running ? t("running") : t("stopped");
}

function showError(error) {
  $("errorBox").textContent = error?.message || String(error);
}

function setElementBusy(element, busy) {
  if (!element) return;
  element.classList.toggle("is-busy", busy);
  element.setAttribute("aria-busy", busy ? "true" : "false");
  if (element.tagName === "BUTTON") element.disabled = busy;
}

async function withBusy(element, task) {
  setElementBusy(element, true);
  try {
    return await task();
  } finally {
    setElementBusy(element, false);
  }
}

function mergeStatusPatch(patch) {
  state.status = { ...(state.status || {}), ...patch };
  renderStatus(state.status);
}

function mergeNestedStatusPatch(key, patch) {
  const current = state.status || {};
  state.status = { ...current, [key]: { ...(current[key] || {}), ...patch } };
  renderStatus(state.status);
}

function renderScreenshot(shot, options = {}) {
  const { showPreview = true } = options;
  state.latestScreenshot = shot;
  state.screenshotPreviewVisible = showPreview;
  const status = $("screenshotStatus");
  const openLink = $("screenshotOpenLink");
  const downloadLink = $("screenshotDownloadLink");
  const wrap = $("screenshotPreviewWrap");
  const image = $("screenshotPreview");
  if (!shot) {
    status.textContent = t("screenshotUnavailable");
    openLink.classList.add("disabled");
    downloadLink.classList.add("disabled");
    openLink.removeAttribute("href");
    downloadLink.removeAttribute("href");
    wrap.classList.add("hidden");
    image.removeAttribute("src");
    return;
  }
  const cacheBust = "v=" + Date.now();
  status.textContent = t("screenshotReady", { filename: shot.filename });
  openLink.href = shot.url + "?" + cacheBust;
  downloadLink.href = shot.download_url;
  openLink.classList.remove("disabled");
  downloadLink.classList.remove("disabled");
  if (showPreview) {
    image.src = shot.url + "?" + cacheBust;
    wrap.classList.remove("hidden");
  } else {
    wrap.classList.add("hidden");
    image.removeAttribute("src");
  }
}

async function loadLatestScreenshot() {
  try {
    const data = await requestJson("/api/display-screenshot/latest");
    renderScreenshot(data.screenshot, { showPreview: false });
  } catch (error) {
    renderScreenshot(null);
  }
}

async function captureScreen() {
  const button = $("captureScreenBtn");
  const wrap = $("screenshotPreviewWrap");
  const image = $("screenshotPreview");
  setElementBusy(button, true);
  wrap.classList.add("hidden");
  image.removeAttribute("src");
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  try {
    const data = await post("/api/display-screenshot");
    renderScreenshot(data.screenshot);
  } catch (error) {
    showError(error);
  } finally {
    setElementBusy(button, false);
  }
}

function selectedFilenames() {
  return Array.from(state.selected);
}

function photoPageSize() {
  const configured = Number(state.config?.photo_page_size);
  return Number.isFinite(configured) && configured > 0 ? configured : 8;
}

function syncPhotoPagingControls() {
  $("historyDetailsCount").textContent = t("recordHeaderCount", {count: (state.history.detailRecords || []).length, total: state.history.totalCount || 0});
}
function syncBulkControls() {
  const count = state.selected.size;
  $("selectedCount").textContent = t("selectedCount", { count });
  $("recordSelectionTools").hidden = count === 0;
  $("recordDefaultTools").hidden = count > 0;
  $("bulkDownloadBtn").disabled = count === 0;
  $("bulkDeleteBtn").disabled = count === 0;
  syncPhotoPagingControls();
}

function renderLightStatus(light) {
  const mode = light?.mode || "off";
  $("lightOffBtn").classList.toggle("active", mode === "off");
  $("lightOnBtn").classList.toggle("active", mode === "on");
}

function renderEnvironment(status) {
  const list = $("environmentList");
  if (!list || !status) return;
  const sensors = status.hardware?.sensors?.sensors || [];
  const delta = status.hardware?.sensors?.delta || {};
  const power = status.hardware?.power || {};
  list.innerHTML = [
    row(t("lightMode"), status.light?.mode === "on" ? t("lightOn") : t("lightOff")),
    row(t("lightEffective"), status.light?.effective_on ? t("yes") : t("no")),
    row(t("sensorA"), formatSensor(sensors[0])),
    row(t("sensorB"), formatSensor(sensors[1])),
    row(t("sensorDelta"), delta.ready ? `${delta.temperature_delta_c} °C / ${delta.humidity_delta_percent_points} %RH (${delta.warning ? t("warning") : t("normal")})` : t("none")),
    row(t("powerStatus"), power.under_voltage ? t("warning") : t("normal")),
  ].join("");
}

function renderSystemDetails(status) {
  const list = $("systemDetailsList");
  if (!list || !status) return;
  const power = status.hardware?.power || {};
  list.innerHTML = [
    row(t("statusWifi"), status.network?.wifi_ssid || t("none")),
    row(t("statusWifiSignal"), status.network?.wifi_signal ? `${status.network.wifi_signal}%` : t("none")),
    row(t("statusDownloadRate"), formatRate(status.network?.download_kbps)),
    row(t("statusUploadRate"), formatRate(status.network?.upload_kbps)),
    row(t("statusLanIp"), status.network?.lan_ipv4 || t("none")),
    row(t("statusTailscaleIp"), status.network?.tailscale_ipv4 || t("none")),
    row(t("cpuTemp"), power.cpu_temp_c ? `${power.cpu_temp_c} °C` : t("none")),
    row(t("ext5v"), power.ext5v_v ? `${power.ext5v_v.toFixed(3)} V` : t("none")),
  ].join("");
}

function externalStateLabel(value) {
  return t({
    disabled: "externalDisabled",
    disconnected: "externalDisconnected",
    connected: "externalConnected",
    migrating: "externalMigrating",
    copying_snapshot: "externalCopyingSnapshot",
    ready: "externalReady",
    error: "externalError",
    unformatted: "externalUnformatted",
  }[value] || "externalDisconnected");
}

function updateExternalDeviceOptions(external = {}) {
  const select = $("externalDeviceSelect");
  if (!select || document.activeElement === select) return;
  const selected = select.value || state.config?.external_device_uuid || "";
  const devices = Array.isArray(external.devices) ? external.devices : [];
  const options = [{ value: "", label: t("externalDeviceAuto") }];
  const writable = devices.filter((device) => device.uuid && device.supported && device.mount_path && !device.read_only);
  writable.forEach((device) => {
    const name = device.label || device.path || device.uuid;
    const details = [device.filesystem || t("externalUnformatted"), formatStorageBytes(device.size_bytes)]
      .filter(Boolean).join(" · ");
    options.push({ value: String(device.uuid), label: `${name} (${details})` });
  });
  if (selected && !options.some((option) => option.value === selected)) {
    options.push({ value: selected, label: t("externalDeviceSaved", { uuid: selected }) });
  }
  select.replaceChildren(...options.map((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    return option;
  }));
  select.value = selected;
  select.disabled = writable.length <= 1;
}

function renderExternalStorageStatus(external = {}) {
  const badge = $("externalStorageBadge");
  const list = $("externalStorageStatusList");
  if (!badge || !list) return;
  const storageState = external.state || "disconnected";
  const device = external.device || {};
  const displayState = external.low_space ? "low_space" : storageState;
  const displayStateLabel = external.low_space ? t("externalLowSpace") : externalStateLabel(storageState);
  badge.dataset.state = displayState;
  badge.textContent = displayStateLabel;
  updateExternalDeviceOptions(external);
  const freeMb = external.free_mb ?? (Number(device.free_bytes) / (1024 * 1024));
  const totalMb = external.total_mb ?? (Number(device.size_bytes) / (1024 * 1024));
  const capacity = Number.isFinite(Number(totalMb)) && Number(totalMb) > 0
    ? `${formatStorageMb(freeMb)} / ${formatStorageMb(totalMb)}`
    : t("none");
  list.innerHTML = [
    row(t("externalStateLabel"), escapeHtml(displayStateLabel)),
    row(t("externalDeviceLabel"), escapeHtml(device.label || device.path || t("none"))),
    row(t("externalFilesystemLabel"), escapeHtml(device.filesystem || t("none"))),
    row(t("externalCapacityLabel"), escapeHtml(capacity)),
    row(t("externalLastSyncLabel"), escapeHtml(formatTime(external.last_operation_at))),
    row(t("externalVerifiedLabel"), formatInteger(external.verified ?? 0)),
    row(t("externalCleanedLabel"), formatInteger(external.cleaned_local ?? 0)),
  ].join("");
  const hint = $("externalStorageHint");
  if (external.low_space) {
    hint.textContent = t("externalStorageLowMessage", {
      device: device.label || device.path || t("externalDeviceLabel"),
      free: formatStorageMb(external.free_mb),
      reserve: formatStorageMb(external.reserve_mb),
    });
  } else if (storageState === "unformatted") hint.textContent = t("externalStorageNeedsFormat");
  else if (storageState === "error") hint.textContent = external.last_error || t("externalStorageIssue");
  else if (storageState === "disabled") hint.textContent = t("externalDisabledHint");
  else if (storageState === "copying_snapshot") hint.textContent = t("externalSnapshotQueued");
  else if (["ready", "connected", "migrating"].includes(storageState)) hint.textContent = t("externalReadyHint");
  else hint.textContent = t("externalNotConnectedHint");
  $("externalSnapshotBtn").disabled = !external.connected || external.low_space || external.busy;
  $("externalEjectBtn").disabled = !external.connected || external.busy;
}

let dismissedIssues = [];
let dismissedIssueHistory = [];
try { dismissedIssueHistory = JSON.parse(localStorage.getItem("petritrace.dismissedIssueHistory") || "[]"); if (!Array.isArray(dismissedIssueHistory)) dismissedIssueHistory = []; } catch (_) {}
try { dismissedIssues = JSON.parse(localStorage.getItem("petritrace.dismissedIssues") || "[]"); if (!Array.isArray(dismissedIssues)) dismissedIssues = []; } catch (_) {}
function saveDismissedIssues() {
  try { localStorage.setItem("petritrace.dismissedIssues", JSON.stringify(dismissedIssues)); } catch (_) {}
}
function visibleStatusIssues(issues) {
  const active = new Set(issues.map(issue => issue.key));
  dismissedIssues = dismissedIssues.filter(key => active.has(key));
  saveDismissedIssues();
  return issues.filter(issue => !dismissedIssues.includes(issue.key));
}

function currentStatusIssues(status) {
  const issues = [];
  const seen = new Set();
  const add = (label, message, identity = label) => {
    const detail = String(message || t("abnormal"));
    const key = `${label}\n${detail}`;
    if (seen.has(key)) return;
    seen.add(key);
    issues.push({ label, message: detail, key: identity });
  };
  if (status.camera?.ready === false) add(t("cameraIssue"), status.camera.error, "cameraIssue");
  const localStorage = status.storage || {};
  if (localStorage.low_space) {
    add(t("localStorageLowIssue"), t("localStorageLowMessage", {
      free: formatStorageMb(localStorage.free_mb),
      reserve: formatStorageMb(localStorage.reserve_mb ?? state.config?.local_reserve_mb),
    }), "localStorageLowIssue");
  } else if (localStorage.ready === false) add(t("storageIssue"), localStorage.error, "storageIssue");
  const sensorStatus = status.hardware?.sensors;
  if (sensorStatus?.ready === false) add(t("sensorIssue"), sensorStatus.error || sensorStatus.delta?.message, "sensorIssue");
  (sensorStatus?.sensors || []).forEach((sensor) => {
    if (sensor.status !== "ok") add(`${t("sensorIssue")} · ${sensor.name || sensor.id || ""}`, sensor.error, `sensor:${sensor.id || sensor.name}`);
  });
  if (sensorStatus?.delta?.warning) {
    add(
      t("sensorDifferenceIssue"),
      `${sensorStatus.delta.temperature_delta_c} °C / ${sensorStatus.delta.humidity_delta_percent_points} %RH`, "sensorDifferenceIssue"
    );
  }
  const power = status.hardware?.power;
  if (power?.under_voltage) add(t("powerIssue"), `throttled=${power.throttled || "unknown"}`, "powerIssue");
  if (status.light?.last_error) add(t("lightIssue"), status.light.last_error, "lightIssue");
  if (status.last_error) add(t("captureIssue"), status.last_error, `capture:${status.last_capture_started_at || status.last_error}`);
  if (status.colony_counting?.last_error) add(t("analysisIssue"), status.colony_counting.last_error, `analysis:${status.colony_counting.last_error_id || status.colony_counting.last_error}`);
  const external = status.external_storage || {};
  if (external.state === "error") add(t("externalStorageIssue"), external.last_error, "externalStorageIssue");
  if (external.low_space) {
    const device = external.device || {};
    add(t("externalStorageLowIssue"), t("externalStorageLowMessage", {
      device: device.label || device.path || t("externalDeviceLabel"),
      free: formatStorageMb(external.free_mb),
      reserve: formatStorageMb(external.reserve_mb ?? state.config?.local_reserve_mb),
    }), "externalStorageLowIssue");
  }
  if (external.state === "unformatted") add(t("externalStorageIssue"), t("externalStorageNeedsFormat"), "externalStorageIssue");
  const captureStorage = status.capture_storage || {};
  if (state.config?.storage_policy === "local_preferred" && captureStorage.reason === "local_low_space") {
    add(t("localSpillIssue"), t("localSpillMessage"), "localSpillIssue");
  }
  if (
    state.config?.storage_policy === "external_preferred"
    && ["external_unavailable", "external_low_space"].includes(captureStorage.reason)
  ) add(t("externalFallbackIssue"), t("externalFallbackMessage"), "externalFallbackIssue");
  if (!external.connected && (external.devices || []).some((device) => device.read_only)) {
    add(t("externalStorageIssue"), t("externalStorageReadOnly"), "externalStorageIssue");
  }
  return issues;
}

function renderIssueList(container, issues, emptyKey) {
  if (!container) return;
  if (!issues.length) {
    container.innerHTML = `<p>${escapeHtml(t(emptyKey))}</p>`;
    return;
  }
  container.innerHTML = issues.map((issue) => `
    <div class="issue-item">
      <strong>${escapeHtml(issue.label)}</strong>
      ${issue.time ? `<span class="issue-time">${escapeHtml(formatTime(issue.time))}</span>` : ""}
      <span>${escapeHtml(issue.message || t("abnormal"))}</span>
    </div>
  `).join("");
}

function storageLocationLabel(location) {
  return t(location === "external" ? "externalStorageName" : "localStorageName");
}

function storageRelayLabel(status) {
  const reason = status.capture_storage?.reason;
  if (state.config?.storage_policy === "local_preferred" && reason === "local_low_space") {
    return t("externalRelay");
  }
  if (
    state.config?.storage_policy === "external_preferred"
    && ["external_unavailable", "external_low_space"].includes(reason)
  ) return t("localRelay");
  return "";
}

function currentStorageLocation(status) {
  const location = status.capture_storage?.location;
  if (["local", "external"].includes(location)) return location;
  return state.config?.storage_policy === "external_preferred" ? "external" : "local";
}

function resolvedStorageView(status) {
  return state.storageView === "current" ? currentStorageLocation(status) : state.storageView;
}

function storageSummaryForView(status, view) {
  return view === "external" ? (status.external_storage || {}) : (status.storage || {});
}

function storageViewDetail(storage, available = true) {
  if (!available || !Number(storage?.total_mb)) return t("storageUnavailable");
  return t("storageViewDetail", {
    count: formatInteger(storage.photo_count ?? 0),
    free: formatStorageMb(storage.free_mb),
  });
}

function renderStorageViewMenu(status) {
  const current = currentStorageLocation(status);
  const relay = storageRelayLabel(status);
  const local = status.storage || {};
  const external = status.external_storage || {};
  $("topStorageViewCurrentDetail").textContent = [storageLocationLabel(current), relay].filter(Boolean).join(" · ");
  $("topStorageViewLocalDetail").textContent = storageViewDetail(local, Number(local.total_mb) > 0);
  $("topStorageViewExternalDetail").textContent = storageViewDetail(external, Boolean(external.connected));
  document.querySelectorAll("[data-storage-view]").forEach((button) => {
    button.setAttribute("aria-checked", String(button.dataset.storageView === state.storageView));
  });
}

function setStorageViewMenu(open) {
  const menu = $("topStorageViewMenu");
  const toggle = $("topStorageViewToggle");
  menu.hidden = !open;
  toggle.setAttribute("aria-expanded", String(open));
}

function renderTopOverview(status) {
  const view = resolvedStorageView(status);
  const storage = storageSummaryForView(status, view);
  const current = currentStorageLocation(status);
  const relay = storageRelayLabel(status);
  const manuallyViewing = state.storageView !== "current";
  $("topStorageViewLabel").textContent = t(manuallyViewing ? "viewingStorage" : "currentWriteStorage", {
    target: storageLocationLabel(view),
  });
  const routeText = manuallyViewing
    ? [t("currentWriteStorage", { target: storageLocationLabel(current) }), relay].filter(Boolean).join(" · ")
    : relay;
  $("topStorageRoute").textContent = routeText;
  $("topStorageRoute").classList.toggle("relay", Boolean(relay));
  renderStorageViewMenu(status);

  const photoCount = storage.photo_count;
  $("topPhotoCount").textContent = photoCount === null || photoCount === undefined
    ? t("photoStorageValue", { count: "—", size: "—" })
    : t("photoStorageValue", { count: formatInteger(photoCount), size: formatStorageBytes(storage.photo_bytes) });
  const remainingValue = storage.estimated_remaining_photos;
  const remaining = Number(remainingValue);
  $("topPhotoEstimate").textContent = remainingValue !== null && remainingValue !== undefined && Number.isFinite(remaining)
    ? t("compactEstimateRemaining", { count: formatInteger(remaining) })
    : t("compactEstimateUnavailable");
  $("topStorageFree").textContent = t("storageFreeValue", { free: formatStorageMb(storage.free_mb) });
  const totalMb = Math.max(0, Number(storage.total_mb) || 0);
  const freeMb = Math.max(0, Number(storage.free_mb) || 0);
  const photoMb = Math.max(0, Number(storage.photo_bytes) || 0) / (1024 * 1024);
  const hasCapacity = totalMb > 0;
  const systemReservedMb = Math.max(0, totalMb - freeMb - photoMb);
  $("topSystemStorage").textContent = hasCapacity
    ? t(
      view === "external" ? "otherReservedValue" : "systemReservedValue",
      { value: formatStorageMb(systemReservedMb) },
    )
    : t("storageUnavailable");
  const systemPercent = totalMb ? Math.max(0, Math.min(100, (systemReservedMb / totalMb) * 100)) : 0;
  const photoPercent = totalMb ? Math.max(0, Math.min(100 - systemPercent, (photoMb / totalMb) * 100)) : 0;
  const occupiedPercent = totalMb ? Math.max(0, Math.min(100, ((totalMb - freeMb) / totalMb) * 100)) : 0;
  $("topStorageFill").style.width = `${systemPercent}%`;
  $("topStoragePhotoMarker").style.left = `${systemPercent}%`;
  $("topStoragePhotoMarker").style.width = `max(3px, ${photoPercent}%)`;
  $("topStoragePhotoMarker").classList.toggle("hidden", photoMb <= 0);
  $("topStorageFill").classList.toggle("warning", Boolean(storage.low_space));
  $("topStorageTrack").setAttribute("aria-valuenow", occupiedPercent.toFixed(1));
  $("topStorageTrack").setAttribute("aria-valuetext", [
    $("topStorageViewLabel").textContent,
    $("topStorageRoute").textContent,
    $("topSystemStorage").textContent,
    $("topPhotoCount").textContent,
    $("topStorageFree").textContent,
    $("topPhotoEstimate").textContent,
  ].join("; "));

  const issues = currentStatusIssues(status);
  const visibleIssues = visibleStatusIssues(issues);
  const alertBox = $("topAlert");
  alertBox.classList.toggle("hidden", visibleIssues.length === 0);
  if (issues.length) {
    $("topAlertText").textContent = t("attentionSummary", {
      count: visibleIssues.length,
      items: visibleIssues.map((issue) => issue.label).join(state.language === "en" ? ", " : "、"),
    });
  }
  renderIssueList($("errorBox"), issues, "noCurrentIssues");
}

function eventIssueLabel(event) {
  if (event.event_type === "analysis_error") return t("analysisIssue");
  if (event.event_type === "capture_error") return t("captureErrorEvent");
  return event.event_type || t("abnormal");
}

function renderDiagnosticEvents(events) {
  state.diagnosticEvents = events || [];
  const issues = (events || [])
    .filter((event) => Number(event.ok) === 0 || String(event.event_type || "").includes("error"))
    .slice(0, 12)
    .map((event) => ({
      label: eventIssueLabel(event),
      time: event.timestamp,
      message: event.message || event.reason || t("abnormal"),
    }));
  const history = [...issues, ...dismissedIssueHistory].sort((a,b) => String(b.time).localeCompare(String(a.time))).slice(0, 50);
  renderIssueList($("diagnosticEvents"), history, "noRecordedIssues");
}

async function loadDiagnosticEvents() {
  const data = await requestJson("/api/history/events?mode=all&limit=50");
  renderDiagnosticEvents(data.events || []);
}

function renderStatus(status) {
  if (!status) return;
  state.screenIdleTimeoutSeconds = Number(
    status.screen_idle?.timeout_seconds ?? state.screenIdleTimeoutSeconds ?? 60
  );
  setBadge(Boolean(status.running));
  $("summary").textContent = "";
  $("summary").hidden = true;
  const intervalInput = $("interval");
  if (!intervalDirty && document.activeElement !== intervalInput) {
    intervalInput.value = status.interval_seconds || 60;
  }
  renderTopOverview(status);
  $("statusList").innerHTML = [
    row(t("statusRunning"), status.running ? t("yes") : t("no")),
    row(t("statusCapturing"), status.is_capturing ? t("yes") : t("no")),
    row(t("sessionCaptureCount"), status.capture_count),
    row(t("storedPhotos"), status.storage?.photo_count ?? 0),
    row(t("statusLastPhoto"), status.last_photo || t("none")),
    row(t("statusCamera"), status.camera?.ready ? t("ready") : t("abnormal")),
    row(t("statusStorage"), status.storage?.ready ? t("ready") : t("abnormal")),
    row(t("statusFreeSpace"), formatStorageMb(status.storage?.free_mb)),
    row(t("statusPhotoDir"), status.storage?.photo_dir || ""),
  ].join("");
  renderLightStatus(status.light);
  renderEnvironment(status);
  renderSystemDetails(status);
  renderExternalStorageStatus(status.external_storage || {});
}

async function loadStatus() {
  if (statusRequest) return statusRequest;
  statusRequest = requestJson("/api/status")
    .then((status) => {
      state.status = status;
      renderStatus(state.status);
      return status;
    })
    .finally(() => {
      statusRequest = null;
    });
  return statusRequest;
}

function openPhotoViewer(filename) {
  const record = (state.history.detailRecords || []).find(r => r.filename === filename) || historyRecords().find(r => r.filename === filename) || {filename};
  const photo = record.photo || {filename, url:`/photos/${encodeURIComponent(filename)}`, download_url:`/download/${encodeURIComponent(filename)}`};
  state.viewerFilename = filename;
  const image = $("photoViewerImage"); image.src = photo.url; image.alt = filename; image.classList.remove("zoomed");
  $("photoViewerName").textContent = filename;
  $("photoViewerMeta").textContent = [formatTime(record.timestamp), `A ${historyMetric(record.sensor_a_temp_c," °C")} / ${historyMetric(record.sensor_a_humidity_percent," %RH")}`, `B ${historyMetric(record.sensor_b_temp_c," °C")} / ${historyMetric(record.sensor_b_humidity_percent," %RH")}`, `OpenCFU ${record.counts?.opencfu?.count ?? "—"} · MCount ${record.counts?.mcount?.count ?? "—"}`].join(" · ");
  $("photoViewerDownload").href = photo.download_url;
  $("photoViewerDownload").hidden = isKioskDisplay();
  const rows=state.history.detailRecords || [], index=rows.findIndex(r=>r.filename===filename);
  $("photoViewerPosition").textContent = index < 0 ? "" : `${(state.history.page-1)*25+index+1} / ${state.history.totalCount}`;
  $("photoViewerPrev").disabled = index <= 0 && state.history.page <= 1;
  $("photoViewerNext").disabled = index >= rows.length-1 && state.history.page >= (state.history.pages || 1);
  const viewer=$("photoViewer"); viewer.classList.remove("hidden");
  if (!viewer.open) { state.viewerReturnFocus=document.activeElement; viewer.showModal(); $("photoViewerClose").focus(); }
  document.body.classList.add("viewer-open");
}
async function navigatePhoto(direction) {
  if(state.viewerNavigating)return;
  state.viewerNavigating=true;
  try {
    let rows=state.history.detailRecords || [], index=rows.findIndex(r=>r.filename===state.viewerFilename)+direction;
    while (true) {
      if (index<0 || index>=rows.length) {
        const page=state.history.page+direction;
        if(page<1 || page>(state.history.pages || 1))return;
        await loadRecordPage(page);rows=state.history.detailRecords;index=direction>0?0:rows.length-1;
      }
      if(rows[index]?.photo){openPhotoViewer(rows[index].filename);return;}
      index+=direction;
    }
  } catch(error){showError(error);} finally {state.viewerNavigating=false;}
}
function closePhotoViewer() {
  const viewer=$("photoViewer"); if(!viewer.open)return;
  viewer.close();viewer.classList.add("hidden");document.body.classList.remove("viewer-open");
  $("photoViewerImage").removeAttribute("src");state.viewerFilename=null;state.viewerReturnFocus?.focus?.();
}

function colonyResultMarkup(photo, backend, label) {
  const result = photo.colony_counts?.[backend];
  let value = "…";
  let status = "pending";
  let title = "";
  if (result) {
    status = result.status || "error";
    if (result.count !== null && result.count !== undefined) value = String(result.count);
    else if (status === "error") value = "!";
    else value = "—";
    title = result.details?.error || (result.details?.flags || []).join(", ") || "";
  }
  return `<span class="colony-result colony-${escapeHtml(status)}" title="${escapeHtml(title)}"><strong>${label}</strong> ${escapeHtml(value)}</span>`;
}

function renderPhotos() { renderHistoryTable(historyRecords()); }

async function loadPhotos(options = {}) {
  if(options.reset) state.history.page=1;
  await loadHistory();
}

function numericInput(id, fallback) {
  const value = Number($(id).value);
  return Number.isFinite(value) ? value : fallback;
}

async function loadConfig() {
  state.config = await requestJson("/api/config");
  const language = state.config.ui_language || localStorage.getItem("piCameraLanguage") || "en";
  $("languageSelect").value = language;
  $("stopPiOnLauncherExit").checked = Boolean(state.config.stop_pi_service_on_launcher_exit);
  $("lightPreSeconds").value = state.config.light_pre_seconds ?? 1;
  $("lightPostSeconds").value = state.config.light_post_seconds ?? 1;
  $("lightBrightness").value = state.config.light_brightness ?? 0.35;
  state.screenIdleTimeoutSeconds = Number(state.config.screen_idle_timeout_seconds ?? 60);
  $("screenIdleTimeoutSeconds").value = state.screenIdleTimeoutSeconds;
  $("storagePolicy").value = state.config.storage_policy || "local_preferred";
  $("externalDeviceSelect").value = state.config.external_device_uuid || "";
  $("localReserveMb").value = state.config.local_reserve_mb ?? 5120;
  applyLanguage(language);
}

async function refreshAll() {
  await Promise.all([loadStatus(), loadPhotos()]);
}

function currentInterval() {
  const value = Number($("interval").value);
  if (!Number.isFinite(value) || value < 1) {
    throw new Error(t("invalidInterval"));
  }
  return Math.round(value);
}

async function saveConfig(payload) {
  state.config = await post("/api/config", payload);
  $("languageSelect").value = state.config.ui_language || state.language;
  $("stopPiOnLauncherExit").checked = Boolean(state.config.stop_pi_service_on_launcher_exit);
  $("lightPreSeconds").value = state.config.light_pre_seconds ?? 1;
  $("lightPostSeconds").value = state.config.light_post_seconds ?? 1;
  $("lightBrightness").value = state.config.light_brightness ?? 0.35;
  state.screenIdleTimeoutSeconds = Number(state.config.screen_idle_timeout_seconds ?? 60);
  $("screenIdleTimeoutSeconds").value = state.screenIdleTimeoutSeconds;
  $("storagePolicy").value = state.config.storage_policy || "local_preferred";
  updateExternalDeviceOptions(state.status?.external_storage || {});
  $("externalDeviceSelect").value = state.config.external_device_uuid || "";
  $("localReserveMb").value = state.config.local_reserve_mb ?? 5120;
  applyLanguage(state.config.ui_language || state.language);
  $("settingsSaved").textContent = t("settingsSaved");
  setTimeout(() => { $("settingsSaved").textContent = ""; }, 2500);
  return state.config;
}

async function applyInterval() {
  const config = await saveConfig({ interval_seconds: currentInterval() });
  intervalDirty = false;
  $("interval").value = config.interval_seconds || currentInterval();
  await loadStatus();
}

function historyValue(sample, key) {
  const raw = sample[key];
  if (raw === null || raw === undefined || raw === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function drawLine(ctx, points, color, xFor, yFor) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  let moved = false;
  points.forEach((point) => {
    if (point.value === null || !Number.isFinite(point.timestamp)) {
      moved = false;
      return;
    }
    const x = xFor(point.timestamp);
    const y = yFor(point.value);
    if (!moved) {
      ctx.moveTo(x, y);
      moved = true;
    } else {
      ctx.lineTo(x, y);
    }
  });
  if (moved) ctx.stroke();
  ctx.fillStyle = color;
  points.forEach((point) => {
    if (point.value === null || !Number.isFinite(point.timestamp)) return;
    ctx.beginPath();
    ctx.arc(xFor(point.timestamp), yFor(point.value), 2.2, 0, Math.PI * 2);
    ctx.fill();
  });
}

function chartRange(values, options = {}) {
  if (!values.length) return null;
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) {
    const margin = Math.max(1, Math.abs(min) * 0.1);
    min -= margin;
    max += margin;
  } else {
    const margin = Math.max((max - min) * 0.1, 0.5);
    min -= margin;
    max += margin;
  }
  if (options.floorZero) min = Math.max(0, Math.min(min, 0));
  if (Number.isFinite(options.min)) min = Math.max(options.min, min);
  if (Number.isFinite(options.max)) max = Math.min(options.max, max);
  if (min === max) max = min + 1;
  return { min, max };
}

function colonyChartRange(values) {
  if (!values.length) return null;
  const maximum = Math.max(0, ...values);
  const rawStep = Math.max(1, maximum / 4);
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalized = rawStep / magnitude;
  const niceNormalized = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  const step = Math.max(1, niceNormalized * magnitude);
  return { min: 0, max: step * 4 };
}

const TIME_STEPS_MS = [
  60_000, 5 * 60_000, 15 * 60_000, 30 * 60_000,
  60 * 60_000, 2 * 60 * 60_000, 3 * 60 * 60_000, 6 * 60 * 60_000, 12 * 60 * 60_000,
  24 * 60 * 60_000, 2 * 24 * 60 * 60_000, 3 * 24 * 60 * 60_000,
  5 * 24 * 60 * 60_000, 7 * 24 * 60 * 60_000, 14 * 24 * 60 * 60_000,
  30 * 24 * 60 * 60_000, 60 * 24 * 60 * 60_000, 90 * 24 * 60 * 60_000,
  180 * 24 * 60 * 60_000, 365 * 24 * 60 * 60_000,
];

function normalizedHistoryRecords() {
  const source = [...(state.history.records || [])];
  const located = state.history.locatedRecord;
  if (located && !source.some(record => record.filename === located.filename)) source.push(located);
  return source
    .map((record) => ({ ...record, timestampMs: Date.parse(record.timestamp) }))
    .filter((record) => Number.isFinite(record.timestampMs))
    .sort((a, b) => a.timestampMs - b.timestampMs);
}

function rebuildHistoryView() {
  const records = normalizedHistoryRecords();
  state.history.visibleRecords = records;
  state.history.hiddenEarlierCount = 0;
  return records;
}

function historyRecords() {
  return state.history.visibleRecords || [];
}

function syncHistoryRangeControls() {
  const mode = state.history.mode || "day";
  document.querySelectorAll("[data-history-mode]").forEach((button) => {
    const active = button.dataset.historyMode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  const custom = mode === "custom";
  $("historyStart").disabled = !custom;
  $("historyEnd").disabled = !custom;
  $("historyLoadBtn").textContent = t(custom ? "applyRange" : "refresh");
  $("historyLoadBtn").dataset.i18n = custom ? "applyRange" : "refresh";
}

function renderHistoryRangeSummary() {
  $("historyRangeSummary").textContent = t("recordCountCompact", {count: state.history.totalCount || 0});
}

function updateReadOnlyHistoryBounds(records) {
  if (["day", "threeDays", "week"].includes(state.history.mode) && state.history.bounds) {
    $("historyStart").value = toDateTimeLocal(new Date(state.history.bounds.start));
    $("historyEnd").value = toDateTimeLocal(new Date(state.history.bounds.end));
    return;
  }
  if (state.history.mode === "custom" || !records.length) return;
  $("historyStart").value = toDateTimeLocal(new Date(records[0].timestampMs));
  $("historyEnd").value = toDateTimeLocal(new Date(records[records.length - 1].timestampMs));
}

function makeTimeAxis(records, width) {
  const timestamps = records.map((record) => record.timestampMs);
  let first = Math.min(...timestamps);
  let last = Math.max(...timestamps);
  if (!timestamps.length) {
    first = Date.now() - 60 * 60_000;
    last = Date.now();
  } else if (first === last) {
    first -= 30 * 60_000;
    last += 30 * 60_000;
  }
  const left = 64;
  const right = width - 64;
  const span = Math.max(1, last - first);
  const targetTicks = Math.max(2, Math.min(10, Math.floor((right - left) / 90)));
  const minimumStep = span / targetTicks;
  const step = TIME_STEPS_MS.find((candidate) => candidate >= minimumStep) || TIME_STEPS_MS[TIME_STEPS_MS.length - 1];
  const ticks = [];
  for (let value = Math.ceil(first / step) * step; value <= last; value += step) ticks.push(value);
  if (!ticks.length) ticks.push(first, last);
  return {
    first,
    last,
    span,
    left,
    right,
    ticks,
    xFor: (timestamp) => left + (right - left) * ((timestamp - first) / span),
  };
}

function timeTickLabel(timestamp, span) {
  const date = new Date(timestamp);
  const locale = { zh: "zh-CN", en: "en-GB", de: "de-DE" }[state.language] || "zh-CN";
  if (span <= 2 * 24 * 60 * 60_000) {
    return new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
  }
  if (span <= 120 * 24 * 60 * 60_000) {
    return new Intl.DateTimeFormat(locale, { month: "2-digit", day: "2-digit" }).format(date);
  }
  if (span <= 800 * 24 * 60 * 60_000) {
    return new Intl.DateTimeFormat(locale, { year: "numeric", month: "2-digit" }).format(date);
  }
  return new Intl.DateTimeFormat(locale, { year: "numeric" }).format(date);
}

function prepareChart(canvas) {
  canvas.historyHitPoints = [];
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "#d7dde5";
  ctx.lineWidth = 1;
  ctx.strokeRect(0.5, 0.5, width - 1, height - 1);
  return { ctx, width, height };
}

function drawNoData(ctx) {
  ctx.fillStyle = "#617083";
  ctx.font = "16px Segoe UI, sans-serif";
  ctx.fillText(t("chartNoData"), 78, 44);
}

function drawTimeGrid(ctx, axis, top, bottom, showLabels) {
  ctx.strokeStyle = "#edf0f4";
  ctx.fillStyle = "#617083";
  ctx.font = "12px Segoe UI, sans-serif";
  ctx.textAlign = "center";
  axis.ticks.forEach((tick) => {
    const x = axis.xFor(tick);
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.stroke();
    if (showLabels) ctx.fillText(timeTickLabel(tick, axis.span), x, bottom + 24);
  });
  ctx.textAlign = "left";
}

function drawYAxis(ctx, range, axis, top, bottom, side, unit, integer = false) {
  const yFor = (value) => bottom - (bottom - top) * ((value - range.min) / (range.max - range.min));
  ctx.fillStyle = "#617083";
  ctx.font = "12px Segoe UI, sans-serif";
  ctx.textAlign = side === "left" ? "right" : "left";
  const x = side === "left" ? axis.left - 8 : axis.right + 8;
  for (let index = 0; index <= 4; index += 1) {
    const value = range.max - (range.max - range.min) * (index / 4);
    ctx.fillText(`${integer ? Math.round(value) : value.toFixed(1)} ${unit}`, x, top + (bottom - top) * (index / 4) + 4);
  }
  ctx.textAlign = "left";
  return yFor;
}

function drawHorizontalGrid(ctx, axis, top, bottom) {
  ctx.strokeStyle = "#e7ebf0";
  for (let i = 0; i <= 4; i += 1) {
    const y = top + (bottom - top) * (i / 4);
    ctx.beginPath();
    ctx.moveTo(axis.left, y);
    ctx.lineTo(axis.right, y);
    ctx.stroke();
  }
}

function drawHistorySelection(ctx, record, axis, top, bottom, markers = []) {
  if (!record) return;
  const x = axis.xFor(record.timestampMs);
  ctx.save();
  ctx.strokeStyle = "#334155";
  ctx.lineWidth = 1.4;
  ctx.setLineDash([5, 4]);
  ctx.beginPath();
  ctx.moveTo(x, top);
  ctx.lineTo(x, bottom);
  ctx.stroke();
  ctx.setLineDash([]);
  markers.forEach((marker) => {
    if (marker.value === null || !marker.yFor) return;
    const y = marker.yFor(marker.value);
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = marker.color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(x, y, 5.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  });
  ctx.restore();
}

function addHistoryHitPoints(canvas, records, valueFor, axis, yFor) {
  records.forEach((record, index) => {
    const value = valueFor(record);
    if (value !== null) canvas.historyHitPoints.push({ index, x: axis.xFor(record.timestampMs), y: yFor(value) });
  });
}

function drawEnvironmentHistory(records, sharedAxis) {
  const canvas = $("environmentHistoryChart");
  if (!canvas) return;
  const { ctx, width, height } = prepareChart(canvas);
  const axis = sharedAxis || makeTimeAxis(records, width);
  const top = 18;
  const bottom = height - 18;
  drawHorizontalGrid(ctx, axis, top, bottom);
  drawTimeGrid(ctx, axis, top, bottom, false);
  const temperatureSeries = [
    { key: "sensor_a_temp_c", color: "#d3455b" },
    { key: "sensor_b_temp_c", color: "#f59e0b" },
  ];
  const humiditySeries = [
    { key: "sensor_a_humidity_percent", color: "#2563eb" },
    { key: "sensor_b_humidity_percent", color: "#10b981" },
  ];
  const temperatures = temperatureSeries.flatMap((series) => records.map((record) => historyValue(record, series.key))).filter((value) => value !== null);
  const humidities = humiditySeries.flatMap((series) => records.map((record) => historyValue(record, series.key))).filter((value) => value !== null);
  const temperatureRange = chartRange(temperatures);
  const humidityRange = chartRange(humidities, { min: 0, max: 100 });
  const selected = Number.isInteger(state.history.activeIndex) ? records[state.history.activeIndex] : null;
  const markers = [];
  if (!temperatureRange && !humidityRange) {
    drawNoData(ctx);
    drawHistorySelection(ctx, selected, axis, top, bottom);
    return;
  }
  if (temperatureRange) {
    const yFor = drawYAxis(ctx, temperatureRange, axis, top, bottom, "left", "°C");
    temperatureSeries.forEach((series) => drawLine(ctx, records.map((record) => ({ timestamp: record.timestampMs, value: historyValue(record, series.key) })), series.color, axis.xFor, yFor));
    temperatureSeries.forEach(series => addHistoryHitPoints(canvas, records, record => historyValue(record, series.key), axis, yFor));
    temperatureSeries.forEach((series) => markers.push({ value: historyValue(selected || {}, series.key), yFor, color: series.color }));
  }
  if (humidityRange) {
    const yFor = drawYAxis(ctx, humidityRange, axis, top, bottom, "right", "%RH");
    humiditySeries.forEach((series) => drawLine(ctx, records.map((record) => ({ timestamp: record.timestampMs, value: historyValue(record, series.key) })), series.color, axis.xFor, yFor));
    humiditySeries.forEach(series => addHistoryHitPoints(canvas, records, record => historyValue(record, series.key), axis, yFor));
    humiditySeries.forEach((series) => markers.push({ value: historyValue(selected || {}, series.key), yFor, color: series.color }));
  }
  drawHistorySelection(ctx, selected, axis, top, bottom, markers);
}

function drawColonyHistory(records, sharedAxis) {
  const canvas = $("colonyHistoryChart");
  if (!canvas) return;
  const { ctx, width, height } = prepareChart(canvas);
  const axis = sharedAxis || makeTimeAxis(records, width);
  const top = 18;
  const bottom = height - 38;
  drawHorizontalGrid(ctx, axis, top, bottom);
  drawTimeGrid(ctx, axis, top, bottom, true);
  const points = records.map((record) => ({
    timestamp: record.timestampMs,
    value: historyValue(record.counts?.[state.colonyBackend] || {}, "count"),
  }));
  const values = points.map((point) => point.value).filter((value) => value !== null);
  const range = colonyChartRange(values);
  const selected = Number.isInteger(state.history.activeIndex) ? records[state.history.activeIndex] : null;
  if (!range) {
    drawNoData(ctx);
    drawHistorySelection(ctx, selected, axis, top, bottom);
    return;
  }
  const yFor = drawYAxis(ctx, range, axis, top, bottom, "left", "", true);
  const color = state.colonyBackend === "mcount" ? "#111827" : "#7c3aed";
  drawLine(ctx, points, color, axis.xFor, yFor);
  addHistoryHitPoints(canvas, records, record => historyValue(record.counts?.[state.colonyBackend] || {}, "count"), axis, yFor);
  drawHistorySelection(ctx, selected, axis, top, bottom, [{
    value: historyValue(selected?.counts?.[state.colonyBackend] || {}, "count"),
    yFor,
    color,
  }]);
}

function syncColonyBackendToggle() {
  document.querySelectorAll("[data-colony-backend]").forEach((button) => {
    const active = button.dataset.colonyBackend === state.colonyBackend;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function displayColonyResult(record) {
  const result = record.counts?.[state.colonyBackend];
  if (!result) return "…";
  if (result.count !== null && result.count !== undefined) return String(result.count);
  return result.status === "error" ? "!" : "—";
}

function formatHistoryExactTime(timestamp) {
  const date = new Date(timestamp);
  if (!Number.isFinite(date.getTime())) return formatTime(timestamp);
  const locale = { zh: "zh-CN", en: "en-GB", de: "de-DE" }[state.language] || "zh-CN";
  return new Intl.DateTimeFormat(locale, {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).format(date);
}

function historyMetric(value, unit = "") {
  const number = historyValue({ value }, "value");
  return number === null ? "—" : `${number}${unit}`;
}

function historyCountValue(record, backend) {
  const result = record.counts?.[backend];
  if (!result) return "…";
  if (result.count !== null && result.count !== undefined) return String(result.count);
  return result.status === "error" ? "!" : "—";
}

function historyTooltipMarkup(record) {
  const entries = [
    [t("sensorATemperature"), historyMetric(record.sensor_a_temp_c, " °C")],
    [t("sensorAHumidity"), historyMetric(record.sensor_a_humidity_percent, " %RH")],
    [t("sensorBTemperature"), historyMetric(record.sensor_b_temp_c, " °C")],
    [t("sensorBHumidity"), historyMetric(record.sensor_b_humidity_percent, " %RH")],
    ["OpenCFU", historyCountValue(record, "opencfu")],
    ["MCount", historyCountValue(record, "mcount")],
  ];
  return `
    <strong class="history-tooltip-time">${escapeHtml(formatHistoryExactTime(record.timestamp))}</strong>
    <dl>${entries.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>
    <span class="history-tooltip-hint">${escapeHtml(t("historyPointHint"))}</span>
  `;
}

function drawHistoryCharts(records = historyRecords()) {
  const canvas = $("colonyHistoryChart") || $("environmentHistoryChart");
  const sharedAxis = makeTimeAxis(records, canvas?.width || 1100);
  drawEnvironmentHistory(records, sharedAxis);
  drawColonyHistory(records, sharedAxis);
}

function hideHistoryTooltips() {
  ["environmentHistoryTooltip", "colonyHistoryTooltip"].forEach((id) => $(id)?.classList.add("hidden"));
}

function renderHistoryTooltip() {
  hideHistoryTooltips();
  const records = historyRecords();
  const index = state.history.activeIndex;
  const chartName = state.history.activeChart;
  if (!Number.isInteger(index) || !records[index] || !chartName) {
    $("historyPointAnnouncement").textContent = "";
    return;
  }
  const canvas = $(`${chartName}HistoryChart`);
  const tooltip = $(`${chartName}HistoryTooltip`);
  if (!canvas || !tooltip) return;
  const record = records[index];
  tooltip.innerHTML = historyTooltipMarkup(record);
  tooltip.classList.remove("hidden");
  const stage = canvas.closest(".history-chart-stage");
  const stageRect = stage.getBoundingClientRect();
  const canvasRect = canvas.getBoundingClientRect();
  const axis = makeTimeAxis(records, canvas.width);
  const x = (axis.xFor(record.timestampMs) / canvas.width) * canvasRect.width + canvasRect.left - stageRect.left;
  const anchorY = Number.isFinite(state.history.pointerY) ? state.history.pointerY : canvasRect.height / 2;
  const left = Math.max(6, Math.min(stageRect.width - tooltip.offsetWidth - 6, x - tooltip.offsetWidth / 2));
  const above = anchorY - tooltip.offsetHeight - 12;
  const below = anchorY + 12;
  const top = above >= 6 ? above : Math.min(stageRect.height - tooltip.offsetHeight - 6, below);
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${Math.max(6, top)}px`;
  $("historyPointAnnouncement").textContent = tooltip.textContent.trim().replace(/\s+/g, " ");
}

function setActiveHistoryPoint(index, chartName, pointerY = null, pinned = false) {
  const records = historyRecords();
  if (!Number.isInteger(index) || !records[index]) return;
  state.history.activeIndex = index;
  state.history.activeTimestamp = records[index].timestampMs;
  state.history.activeFilename = records[index].filename;
  state.history.activeChart = chartName;
  state.history.pointerY = pointerY;
  state.history.pinned = pinned;
  drawHistoryCharts(records);
  renderHistoryTooltip();
}

function clearActiveHistoryPoint() {
  state.history.locatedRecord = null;
  highlightLocatedRow();
  rebuildHistoryView();
  state.history.activeIndex = null;
  state.history.activeTimestamp = null;
  state.history.activeFilename = null;
  state.history.activeChart = null;
  state.history.pointerY = null;
  state.history.pinned = false;
  drawHistoryCharts();
  renderHistoryTooltip();
}

function nearestHistoryPoint(canvas, clientX, clientY = null, radius = 12) {
  if (clientY !== null) {
    const rect = canvas.getBoundingClientRect();
    let closest = null, distance = radius;
    for (const point of canvas.historyHitPoints || []) {
      const dx = rect.left + point.x / canvas.width * rect.width - clientX;
      const dy = rect.top + point.y / canvas.height * rect.height - clientY;
      const candidate = Math.hypot(dx, dy);
      if (candidate <= distance) { closest = point.index; distance = candidate; }
    }
    return closest;
  }
  const records = historyRecords();
  if (!records.length) return null;
  const rect = canvas.getBoundingClientRect();
  const canvasX = (clientX - rect.left) * (canvas.width / Math.max(1, rect.width));
  const axis = makeTimeAxis(records, canvas.width);
  if (canvasX < axis.left - 18 || canvasX > axis.right + 18) return null;
  let bestIndex = 0;
  let bestDistance = Infinity;
  records.forEach((record, index) => {
    const distance = Math.abs(axis.xFor(record.timestampMs) - canvasX);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  });
  return bestIndex;
}

function historyTablePage() { return {rows:state.history.detailRecords || [],pages:state.history.pages || 1}; }

async function loadRecordPage(page=state.history.page, query=state.history.recordQuery, generation=state.history.requestId, focus=null) {
  const id=(state.history.pageRequestId || 0)+1; state.history.pageRequestId=id;
  const params=new URLSearchParams(query || historyExportQuery());params.set("page",page);params.set("page_size",25);
  if(focus) params.set("focus",focus);
  const result=await requestJson(`/api/records?${params}`);
  if(id!==state.history.pageRequestId || generation!==state.history.requestId)return;
  state.history.detailRecords=result.records;state.history.page=result.page;state.history.pages=result.pages;state.history.totalCount=result.total;
  state.photos=result.records.filter(r=>r.photo).map(r=>r.photo);
  renderHistoryTable();
  return result;
}

function renderHistoryTable() {
  const { rows: pageRows, pages } = historyTablePage();
  $("historyRows").innerHTML = pageRows.map((record) => {
    const name = escapeHtml(record.filename);
    const photo = record.photo;
    const backend = state.colonyBackend;
    const thumb = photo ? `<button class="record-thumb" data-history-photo="${name}" aria-label="${escapeHtml(t("viewPhoto"))}"><img src="${escapeHtml(photo.thumbnail_url)}" alt="${name}" loading="lazy"></button>` : `<span class="record-missing">${t("photoUnavailable")}</span>`;
    return `<tr data-record-row="${name}" tabindex="0" aria-label="${escapeHtml(t("locateRecord"))} ${name}" class="${state.history.locatedRecord?.filename === record.filename ? "record-located" : ""}">
      <td><input type="checkbox" data-select-photo="${name}" aria-label="${escapeHtml(t("selectPhoto"))} ${name}" ${state.selected.has(record.filename) ? "checked" : ""}></td>
      <td><div class="record-photo">${thumb}<span class="record-filename" title="${name}">${name}</span></div></td>
      <td class="record-time">${escapeHtml(formatTime(record.timestamp))}</td>
      <td>${escapeHtml(historyMetric(record.sensor_a_temp_c, " °C"))}<br>${escapeHtml(historyMetric(record.sensor_a_humidity_percent, " %RH"))}</td>
      <td>${escapeHtml(historyMetric(record.sensor_b_temp_c, " °C"))}<br>${escapeHtml(historyMetric(record.sensor_b_humidity_percent, " %RH"))}</td>
      <td>${colonyResultMarkup({colony_counts:record.counts}, backend, backend === "mcount" ? "MCount" : "OpenCFU")}</td>
      <td><div class="record-actions"><button class="link-button" data-export-record="${name}">${t("exportTitle")}</button><button class="link-button danger" data-delete-record="${name}">${t("delete")}</button></div></td>
    </tr>`;
  }).join("") || `<tr><td colspan="7">${t("noHistory")}</td></tr>`;
  $("historyDetailsCount").textContent = t("historyDetailsCount", { count: state.history.totalCount || 0 });
  $("historyPageStatus").textContent = t("pageStatus", { page: state.history.page, pages });
  $("historyPrevPage").disabled = state.history.page <= 1;
  $("historyNextPage").disabled = state.history.page >= pages;
  $("historyRows").querySelectorAll("[data-history-photo]").forEach(button => button.addEventListener("click", () => openPhotoViewer(button.dataset.historyPhoto)));
  $("historyRows").querySelectorAll("[data-select-photo]").forEach(box => box.addEventListener("change", () => {
    if (box.checked) state.selected.add(box.dataset.selectPhoto); else state.selected.delete(box.dataset.selectPhoto);
    syncBulkControls();
  }));
  $("historyRows").querySelectorAll("[data-delete-record]").forEach(button => button.addEventListener("click", async () => {
    const filename = button.dataset.deleteRecord;
    if (!confirm(t("confirmDeleteOne", { filename }))) return;
    try { await withBusy(button, async () => {
      await requestJson(`/api/photos/${encodeURIComponent(filename)}`, {method:"DELETE"});
      state.selected.delete(filename); if(state.history.locatedRecord?.filename===filename)clearActiveHistoryPoint(); await refreshAll();
    }); } catch(error) { showError(error); }
  }));
  $("historyRows").querySelectorAll("[data-export-record]").forEach(button => button.addEventListener("click", () => openExport("selected", [button.dataset.exportRecord])));
  $("historyRows").querySelectorAll("[data-record-row]").forEach(row => {
    row.addEventListener("click", event => {
      if(event.target.closest("button,a,input"))return;
      locateFromRecord(row.dataset.recordRow);
    });
    row.addEventListener("keydown", event => {
      if(event.target !== row || !["Enter"," "].includes(event.key))return;
      event.preventDefault();locateFromRecord(row.dataset.recordRow);
    });
  });
  syncBulkControls();
}

function highlightLocatedRow() {
  document.querySelectorAll("[data-record-row]").forEach(row=>row.classList.toggle("record-located",row.dataset.recordRow===state.history.locatedRecord?.filename));
}
function locateFromRecord(filename) {
  const record=(state.history.detailRecords || []).find(row=>row.filename===filename);
  if(!record)return;
  if(state.history.pinned && state.history.locatedRecord?.filename===filename){clearActiveHistoryPoint();return;}
  state.history.locatedRecord=record;
  const records=rebuildHistoryView();
  const index=records.findIndex(row=>row.filename===filename);
  setActiveHistoryPoint(index,"environment",null,true);
  highlightLocatedRow();
}
function locateFromChart(index,chartName,pointerY=null) {
  const record=historyRecords()[index];if(!record)return;
  if(state.history.pinned && state.history.locatedRecord?.filename===record.filename){clearActiveHistoryPoint();return;}
  state.history.locatedRecord=record;
  setActiveHistoryPoint(index,chartName,pointerY,true);
  highlightLocatedRow();
}

function renderHistory() {
  const records = rebuildHistoryView();
  if (Number.isFinite(state.history.activeTimestamp)) {
    const selectedIndex = records.findIndex((record) => state.history.activeFilename ? record.filename === state.history.activeFilename : record.timestampMs === state.history.activeTimestamp);
    state.history.activeIndex = selectedIndex >= 0 ? selectedIndex : null;
    if (selectedIndex < 0) {
      state.history.activeTimestamp = null;
      state.history.activeChart = null;
      state.history.pinned = false;
    }
  }
  syncHistoryRangeControls();
  updateReadOnlyHistoryBounds(records);
  renderHistoryRangeSummary(records);
  $("chartSamplingNote").hidden = !state.history.sampled;
  drawHistoryCharts(records);
  renderHistoryTooltip();
  syncColonyBackendToggle();
  renderHistoryTable(records);
}

async function loadHistory() {
  const requestId = (state.history.requestId || 0) + 1;
  state.history.requestId = requestId;
  const query = queryStringFromHistoryFilters();
  const bounds = state.history.requestBounds;
  const focus = state.history.locatedRecord?.filename;
  const data = await requestJson(`/api/charts?${query}${focus ? `&focus=${encodeURIComponent(focus)}` : ""}`);
  if (requestId !== state.history.requestId) return; // ignore stale replies after switching range
  if(focus && state.history.locatedRecord?.filename===focus) {
    state.history.locatedRecord = data.focus_record || null;
    if(!data.focus_record) {state.history.activeIndex=null;state.history.activeTimestamp=null;state.history.activeChart=null;state.history.pinned=false;}
  }
  state.history.bounds = bounds;
  state.history.records = data.records || [];
  state.history.totalCount = Number(data.summary?.total ?? state.history.records.length);
  state.history.sampled = Boolean(data.sampled);
  state.history.recordQuery = query;
  await loadRecordPage(state.history.page,query,requestId);
  if(requestId!==state.history.requestId)return;
  renderHistory();
}

async function setHistoryMode(mode) {
  state.history.mode = ["day", "threeDays", "week", "all", "custom"].includes(mode) ? mode : "day";
  state.history.page = 1;
  state.history.locatedRecord = null;
  state.selected.clear();
  state.history.activeTimestamp = null;
  state.history.activeIndex = null;
  state.history.activeChart = null;
  state.history.pinned = false;
  if (state.history.mode === "custom") ensureCustomHistoryRange();
  syncHistoryRangeControls();
  await loadHistory();
}

function historyExportQuery() {
  if (state.history.mode === "all") return new URLSearchParams({ mode: "all" }).toString();
  if (state.history.mode === "custom") return queryStringFromHistoryFilters();
  const bounds = state.history.bounds || window.PiHistoryRange.presetHistoryBounds(state.history.mode);
  const params = new URLSearchParams({ mode: "custom", limit: "all" });
  if (bounds) {
    params.set("start", toDateTimeLocal(new Date(bounds.start)));
    params.set("end", toDateTimeLocal(new Date(bounds.end)));
  }
  return params.toString();
}

async function bulkDeleteSelected() {
  const filenames = selectedFilenames();
  if (!filenames.length) {
    alert(t("noSelection"));
    return;
  }
  if (!confirm(t("confirmDeleteMany", { count: filenames.length }))) return;
  const result = await post("/api/photos/bulk-delete", { filenames });
  (result.deleted || []).forEach(name => {state.selected.delete(name);if(state.history.locatedRecord?.filename===name)clearActiveHistoryPoint();});
  await refreshAll();
  if (result.errors?.length) throw new Error(result.errors.map(item => `${item.filename}: ${item.error}`).join("\n"));
}

function bulkDownloadSelected() { openExport("selected",selectedFilenames()); }
let exportPreviewId=0;
const EXPORT_PARTS_STORAGE = "piCameraExportParts.v1";
function restoreExportParts() {
  let saved = [];
  try { const value = JSON.parse(localStorage.getItem(EXPORT_PARTS_STORAGE)); if (Array.isArray(value)) saved = value; } catch {}
  document.querySelectorAll('[name="exportPart"]').forEach(input => { input.checked = saved.includes(input.value); });
}
function rememberExportParts() {
  // Disabled contents retain their preference when exporting selected records.
  const selected = [...document.querySelectorAll('[name="exportPart"]:checked')].map(input => input.value);
  try { localStorage.setItem(EXPORT_PARTS_STORAGE, JSON.stringify(selected)); } catch {}
}

function exportPayload() {
  const scope=$("exportScope").value;
  let start=null,end=null;
  if(scope==="custom") {start=$("exportStart").value;end=$("exportEnd").value;}
  else if(scope==="current") {const q=new URLSearchParams(historyExportQuery());start=q.get("start");end=q.get("end");}
  return {scope,start,end,filenames:state.exportSelection || [],parts:[...document.querySelectorAll('[name="exportPart"]:checked')].filter(e=>!e.disabled).map(e=>e.value)};
}
function openExport(scope="current",filenames=[]) {
  state.exportSelection=filenames.length?filenames:selectedFilenames();
  $("exportScope").querySelector('[value="selected"]').disabled=!state.exportSelection.length;
  $("exportScope").value=scope;$("exportStart").value=$("historyStart").value;$("exportEnd").value=$("historyEnd").value;
  state.exportSubmitted=false;$("exportStatus").textContent="";$("exportDialog").showModal();updateExportPreview();
}
async function updateExportPreview() {
  const id=++exportPreviewId,scope=$("exportScope").value;
  $("exportDates").hidden=scope!=="custom";$("exportEnvironment").disabled=scope==="selected";
  const eligibleParts=[...document.querySelectorAll('[name="exportPart"]')].filter(e=>!e.disabled);
  $("exportAllParts").checked=eligibleParts.length>0 && eligibleParts.every(e=>e.checked);
  $("exportSubmit").disabled=true;$("exportEstimate").textContent=t("exportCalculating");
  if (!eligibleParts.some(e=>e.checked)) { $("exportEstimate").textContent=t("exportChooseContents"); return; }
  try {
    const info=await post("/api/export/preview",exportPayload());if(id!==exportPreviewId)return;
    $("exportEstimate").textContent=t("exportEstimate",{records:info.records,photos:info.photos,environment:info.environment,size:(info.estimated_bytes/1048576).toFixed(1),format:info.format.toUpperCase()});
    $("exportSubmit").disabled=info.records===0 && info.environment===0;
  }catch(error){if(id===exportPreviewId)$("exportEstimate").textContent=error.message;}
}
async function startExport(event) {
  event.preventDefault();
  const payload=exportPayload();
  try {await post("/api/export/preview",payload);}catch(error){$("exportStatus").textContent=error.message;return;}
  const form=document.createElement("form");form.method="POST";form.action="/api/export";form.target="exportDownloadFrame";form.hidden=true;
  const field=document.createElement("input");field.name="payload";field.value=JSON.stringify(payload);form.append(field);document.body.append(form);form.submit();form.remove();
  state.exportSubmitted=true;$("exportStatus").textContent=t("exportSubmitted");
}

function enableTouchDragScroll() {
  const interactiveSelector = "button, input, select, textarea, option";
  const threshold = 6;
  let drag = null;
  let suppressClick = false;

  const isElement = (target) => target && target.nodeType === 1;
  const isInteractive = (target) => isElement(target) && Boolean(target.closest(interactiveSelector));
  const pageScroller = () => document.scrollingElement || document.documentElement;
  const scrollTargetFor = (target) => {
    if (!isElement(target)) return pageScroller();
    const localScroller = target.closest(".event-list");
    if (localScroller && localScroller.scrollHeight > localScroller.clientHeight) {
      return localScroller;
    }
    return pageScroller();
  };

  document.addEventListener("selectstart", (event) => {
    if (!isInteractive(event.target)) event.preventDefault();
  }, true);

  document.addEventListener("dragstart", (event) => {
    if (!isInteractive(event.target)) event.preventDefault();
  }, true);

  document.addEventListener("pointerdown", (event) => {
    if (event.button !== undefined && event.button !== 0) return;
    if (event.isPrimary === false) return;
    if (isInteractive(event.target)) return;
    drag = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
      moved: false,
      scroller: scrollTargetFor(event.target),
    };
  }, { passive: true });

  window.addEventListener("pointermove", (event) => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    const totalX = event.clientX - drag.startX;
    const totalY = event.clientY - drag.startY;
    if (!drag.moved && Math.hypot(totalX, totalY) < threshold) return;
    const deltaX = drag.lastX - event.clientX;
    const deltaY = drag.lastY - event.clientY;
    drag.moved = true;
    suppressClick = true;
    document.body.classList.add("drag-scrolling");
    if (drag.scroller === pageScroller()) {
      window.scrollBy({ top: deltaY, left: 0, behavior: "auto" });
    } else {
      drag.scroller.scrollTop += deltaY;
      drag.scroller.scrollLeft += deltaX;
    }
    drag.lastX = event.clientX;
    drag.lastY = event.clientY;
    event.preventDefault();
  }, { passive: false });

  const finishDrag = () => {
    const moved = Boolean(drag?.moved);
    drag = null;
    document.body.classList.remove("drag-scrolling");
    if (moved) {
      window.setTimeout(() => { suppressClick = false; }, 250);
    } else {
      suppressClick = false;
    }
  };

  window.addEventListener("pointerup", finishDrag, { passive: true });
  window.addEventListener("pointercancel", finishDrag, { passive: true });

  document.addEventListener("click", (event) => {
    if (!suppressClick) return;
    event.preventDefault();
    event.stopPropagation();
    suppressClick = false;
  }, true);
}
function bindAction(id, handler) {
  const element = $(id);
  element.addEventListener("click", async () => {
    await withBusy(element, async () => {
      try {
        await handler(element);
      } catch (error) {
        showError(error);
      }
    });
  });
}

function enableTouchFeedback() {
  const feedbackTarget = "button, .button-link, input, select, textarea, .photo-select, .segmented";
  document.addEventListener("pointerdown", (event) => {
    if (event.button !== undefined && event.button !== 0) return;
    if (event.isPrimary === false) return;
    const dot = document.createElement("span");
    dot.className = "touch-dot";
    dot.style.left = `${event.clientX}px`;
    dot.style.top = `${event.clientY}px`;
    document.body.appendChild(dot);
    window.setTimeout(() => dot.remove(), 520);

    const target = event.target?.closest ? event.target.closest(feedbackTarget) : null;
    if (target) {
      target.classList.add("touch-hit");
      window.setTimeout(() => target.classList.remove("touch-hit"), 180);
    }
  }, { capture: true, passive: true });
}

function enableWakeTouchGuard() {
  let lastInteractionAt = Date.now();
  let suppressUntil = 0;
  let noticeTimer = null;

  const blockEvent = (event) => {
    if (event.cancelable) event.preventDefault();
    event.stopImmediatePropagation();
    event.stopPropagation();
  };

  const showNotice = () => {
    const notice = $("screenWakeNotice");
    notice.textContent = t("screenWakeNotice");
    notice.classList.remove("hidden");
    window.clearTimeout(noticeTimer);
    noticeTimer = window.setTimeout(() => notice.classList.add("hidden"), 1800);
  };

  document.addEventListener("pointerdown", (event) => {
    const now = Date.now();
    const timeoutSeconds = Number(state.screenIdleTimeoutSeconds || 0);
    if (now < suppressUntil) {
      blockEvent(event);
      return;
    }
    const shouldWakeOnly = timeoutSeconds > 0
      && now - lastInteractionAt >= timeoutSeconds * 1000;
    lastInteractionAt = now;
    if (shouldWakeOnly) {
      suppressUntil = now + 1500;
      showNotice();
      blockEvent(event);
    }
  }, { capture: true, passive: false });

  document.addEventListener("click", (event) => {
    if (Date.now() < suppressUntil) blockEvent(event);
  }, { capture: true, passive: false });

  document.addEventListener("keydown", () => {
    lastInteractionAt = Date.now();
  }, true);
}

function wireSecondaryDialog(openButtonIds, dialogId, onOpen) {
  const openButtons = (Array.isArray(openButtonIds) ? openButtonIds : [openButtonIds])
    .map((id) => $(id))
    .filter(Boolean);
  const dialog = $(dialogId);
  let opener = null;

  openButtons.forEach((openButton) => {
    openButton.addEventListener("click", async () => {
      try {
        opener = document.activeElement;
        if (onOpen) await onOpen();
        if (!dialog.open) dialog.showModal();
      } catch (error) {
        showError(error);
      }
    });
  });

  dialog.querySelectorAll("[data-dialog-close]").forEach((button) => {
    button.addEventListener("click", () => dialog.close());
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", () => {
    if (opener?.focus) opener.focus();
  });
}

function wireHistoryChartInteractions(canvasId, chartName) {
  const canvas = $(canvasId);
  if (!canvas) return;
  let press = null;
  const pointerY = (event) => event.clientY - canvas.closest(".history-chart-stage").getBoundingClientRect().top;

  canvas.addEventListener("pointermove", (event) => {
    if (press && event.pointerId === press.pointerId) {
      press.moved = press.moved || Math.hypot(event.clientX - press.x, event.clientY - press.y) > 8;
    }
    if (event.pointerType !== "mouse" || state.history.pinned) return;
    const index = nearestHistoryPoint(canvas, event.clientX);
    if (index === null) {
      if (state.history.activeChart === chartName) clearActiveHistoryPoint();
      return;
    }
    if (state.history.activeIndex === index && state.history.activeChart === chartName) {
      state.history.pointerY = pointerY(event);
      renderHistoryTooltip();
      return;
    }
    setActiveHistoryPoint(index, chartName, pointerY(event), false);
  });

  canvas.addEventListener("pointerleave", () => {
    if (!state.history.pinned && state.history.activeChart === chartName) clearActiveHistoryPoint();
  });
  canvas.addEventListener("pointerdown", (event) => {
    press = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, moved: false };
  });
  canvas.addEventListener("pointercancel", () => { press = null; });
  canvas.addEventListener("pointerup", (event) => {
    if (!press || press.pointerId !== event.pointerId || press.moved) {
      press = null;
      return;
    }
    press = null;
    const index = nearestHistoryPoint(canvas, event.clientX, event.clientY, event.pointerType === "touch" ? 20 : 12);
    if (index === null) { clearActiveHistoryPoint(); return; }
    locateFromChart(index, chartName, pointerY(event));
  });

  canvas.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End", "Enter", "Escape"].includes(event.key)) return;
    event.preventDefault();
    const records = historyRecords();
    if (!records.length) return;
    if (event.key === "Escape") {
      clearActiveHistoryPoint();
      return;
    }
    if (event.key === "Enter") {
      locateFromChart(Number.isInteger(state.history.activeIndex) ? state.history.activeIndex : 0,chartName);
      return;
    }
    let index = Number.isInteger(state.history.activeIndex) ? state.history.activeIndex : 0;
    if (event.key === "ArrowLeft") index -= 1;
    if (event.key === "ArrowRight") index += 1;
    if (event.key === "Home") index = 0;
    if (event.key === "End") index = records.length - 1;
    const nextIndex = Math.max(0, Math.min(records.length - 1, index));
    state.history.locatedRecord = records[nextIndex];
    setActiveHistoryPoint(nextIndex, chartName, null, true);
    highlightLocatedRow();
  });
  canvas.addEventListener("blur", () => {
    if (!state.history.pinned && state.history.activeChart === chartName) clearActiveHistoryPoint();
  });
}

function wire() {
  bindAction("refreshDiagnosticsBtn", async()=>{ await Promise.all([loadStatus(),loadLatestScreenshot(),loadDiagnosticEvents()]); });
  document.addEventListener("click", event => {
    if (!state.history.pinned || event.defaultPrevented) return;
    // Controls, records and chart points handle their own interactions.
    if (event.target.closest('button,a,input,select,textarea,label,summary,dialog,[role="button"],[data-record-row],canvas,.history-tooltip')) return;
    clearActiveHistoryPoint();
  });
  wireHistoryChartInteractions("environmentHistoryChart", "environment");
  wireHistoryChartInteractions("colonyHistoryChart", "colony");
  wireSecondaryDialog("settingsDialogOpen", "settingsDialog", loadConfig);
  wireSecondaryDialog(["diagnosticsDialogOpen", "diagnosticsAlertOpen"], "diagnosticsDialog", async () => {
    await Promise.all([loadStatus(), loadLatestScreenshot(), loadDiagnosticEvents()]);
  });
  $("dismissTopAlert").addEventListener("click", () => {
    const current = currentStatusIssues(state.status);
    dismissedIssues = current.map(issue => issue.key);
    const time = toDateTimeLocal(new Date());
    dismissedIssueHistory = [...current.map(issue => ({...issue, time})), ...dismissedIssueHistory].slice(0, 50);
    try { localStorage.setItem("petritrace.dismissedIssueHistory", JSON.stringify(dismissedIssueHistory)); } catch (_) {}
    renderDiagnosticEvents(state.diagnosticEvents || []);
    saveDismissedIssues();
    renderTopOverview(state.status);
  });
  $("topStorageViewToggle").addEventListener("click", () => {
    setStorageViewMenu($("topStorageViewMenu").hidden);
  });
  document.querySelectorAll("[data-storage-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.storageView = button.dataset.storageView;
      setStorageViewMenu(false);
      if (state.status) renderTopOverview(state.status);
      $("topStorageViewToggle").focus();
    });
  });
  document.addEventListener("click", (event) => {
    if (!$("topStorageOverview").contains(event.target)) setStorageViewMenu(false);
  });
  $("interval").addEventListener("input", () => { intervalDirty = true; });
  $("interval").addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      try { await withBusy($("applyIntervalBtn"), applyInterval); } catch (error) { showError(error); }
    }
  });
  bindAction("applyIntervalBtn", applyInterval);
  bindAction("startBtn", async () => {
    const interval = currentInterval();
    mergeStatusPatch({ running: true, last_error: null, interval_seconds: interval });
    await post("/api/start", { interval_seconds: interval });
    intervalDirty = false;
    await refreshAll();
  });
  bindAction("stopBtn", async () => {
    mergeStatusPatch({ running: false });
    await post("/api/stop");
    await refreshAll();
  });
  bindAction("captureBtn", async () => {
    mergeStatusPatch({ is_capturing: true, last_error: null });
    try {
      await post("/api/capture-now");
    } finally {
      mergeStatusPatch({ is_capturing: false });
    }
    await refreshAll();
  });
  bindAction("lightOffBtn", async () => {
    mergeNestedStatusPatch("light", { mode: "off", effective_on: false, last_error: null });
    await post("/api/light", { light_mode: "off" });
    await loadStatus();
  });
  bindAction("lightOnBtn", async () => {
    mergeNestedStatusPatch("light", { mode: "on", effective_on: true, last_error: null });
    await post("/api/light", { light_mode: "on" });
    await loadStatus();
  });
  bindAction("historyLoadBtn", loadHistory);
  document.querySelectorAll("[data-history-mode]").forEach((button) => {
    button.addEventListener("click", async () => {
      try { await setHistoryMode(button.dataset.historyMode); } catch (error) { showError(error); }
    });
  });
  document.querySelectorAll("[data-colony-backend]").forEach((button) => {
    button.addEventListener("click", () => {
      state.colonyBackend = button.dataset.colonyBackend === "mcount" ? "mcount" : "opencfu";
      localStorage.setItem("piCameraColonyBackend", state.colonyBackend);
      renderPhotos();
      renderHistory();
    });
  });
  $("globalExportBtn").addEventListener("click",()=>openExport());
  $("historyExportBtn").addEventListener("click",()=>openExport());
  bindAction("historyPrevPage",()=>loadRecordPage(state.history.page-1));
  bindAction("historyNextPage",()=>loadRecordPage(state.history.page+1));
  bindAction("refreshBtn", async () => { await refreshAll(); });
  $("captureScreenBtn").addEventListener("click", async () => { await captureScreen(); });
  bindAction("reloadPhotosBtn", async () => loadRecordPage(state.history.page));
  document.querySelector(".records-header").addEventListener("click", event => { if(event.target.closest("button")) event.preventDefault(); });
  $("selectAllBtn").addEventListener("click", () => { historyTablePage(historyRecords()).rows.forEach(record => state.selected.add(record.filename)); renderPhotos(); });
  $("clearSelectionBtn").addEventListener("click", () => { state.selected.clear(); renderPhotos(); });
  bindAction("bulkDeleteBtn", bulkDeleteSelected);
  bindAction("bulkDownloadBtn", bulkDownloadSelected);
  $("photoViewerClose").addEventListener("click", closePhotoViewer);
  $("photoViewer").addEventListener("cancel",e=>{e.preventDefault();closePhotoViewer();});
  $("photoViewerPrev").addEventListener("click",()=>navigatePhoto(-1));
  $("photoViewerNext").addEventListener("click",()=>navigatePhoto(1));
  $("photoViewerZoom").addEventListener("click",()=>$("photoViewerImage").classList.toggle("zoomed"));
  $("photoViewerExport").addEventListener("click",()=>openExport("selected",[state.viewerFilename]));
  $("exportCloseBtn").addEventListener("click",()=>$("exportDialog").close());
  $("exportOptionsForm").addEventListener("change",()=>{rememberExportParts();updateExportPreview();});
  $("exportOptionsForm").addEventListener("submit",startExport);
  $("exportAllParts").addEventListener("change",()=>{document.querySelectorAll('[name="exportPart"]').forEach(e=>{if(!e.disabled)e.checked=$("exportAllParts").checked;});});
  $("exportDownloadFrame").addEventListener("load",()=>{try {const text=$("exportDownloadFrame").contentDocument.body.textContent;if(text.trim().startsWith("{"))$("exportStatus").textContent=JSON.parse(text).error || text;}catch(error){}});
  document.addEventListener("keydown",event=>{
    if(!$("photoViewer").open || $("exportDialog").open)return;
    if(event.key==="ArrowLeft" || event.key==="ArrowRight"){event.preventDefault();navigatePhoto(event.key==="ArrowLeft"?-1:1);}
  });
  $("photoViewer").addEventListener("click", (event) => { if (event.target === $("photoViewer")) closePhotoViewer(); });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || $("exportDialog").open) return;
    if (!$("topStorageViewMenu").hidden) {
      setStorageViewMenu(false);
      $("topStorageViewToggle").focus();
    }
    closePhotoViewer();
    if (state.history.activeIndex !== null) clearActiveHistoryPoint();
  });
  $("languageSelect").addEventListener("change", async () => {
    const language = $("languageSelect").value;
    applyLanguage(language);
    try { await saveConfig({ ui_language: language }); } catch (error) { showError(error); }
  });
  bindAction("externalSnapshotBtn", async () => {
    await post("/api/external-storage/snapshot");
    $("externalStorageHint").textContent = t("externalSnapshotQueued");
    window.setTimeout(loadStatus, 500);
  });
  bindAction("externalEjectBtn", async () => {
    await post("/api/external-storage/eject");
    $("externalStorageHint").textContent = t("externalEjected");
    await loadStatus();
  });
  bindAction("saveSettingsBtn", async () => {
    await saveConfig({
      ui_language: $("languageSelect").value,
      stop_pi_service_on_launcher_exit: $("stopPiOnLauncherExit").checked,
      light_pre_seconds: numericInput("lightPreSeconds", 1),
      light_post_seconds: numericInput("lightPostSeconds", 1),
      light_brightness: numericInput("lightBrightness", 0.35),
      screen_idle_timeout_seconds: Math.max(0, Math.round(numericInput("screenIdleTimeoutSeconds", 60))),
      storage_policy: $("storagePolicy").value,
      external_device_uuid: $("externalDeviceSelect").value,
      local_reserve_mb: Math.max(128, Math.round(numericInput("localReserveMb", 5120))),
    });
    await loadStatus();
  });
}
let lastPageInteraction = Date.now();
let pageUpdatePending = false;
let versionCheckBusy = false;
["pointerdown", "keydown", "input", "wheel"].forEach(name => document.addEventListener(name, () => { lastPageInteraction = Date.now(); }, {passive: true}));
async function checkPageVersion() {
  if (versionCheckBusy) return;
  versionCheckBusy = true;
  try {
    const response = await fetch("/api/ui-version", {cache: "no-store"});
    if (!response.ok) return;
    const version = await response.json();
    if (!version.revision || version.revision === document.documentElement.dataset.uiVersion) return;
    pageUpdatePending = true;
    const button = $("reloadPageBtn");
    button.classList.add("update-ready");
    button.dataset.i18nTitle = "updateReady";
    button.dataset.i18nAriaLabel = "updateReady";
    button.title = t("updateReady");
    button.setAttribute("aria-label", t("updateReady"));
    // Remote browsers keep their current work; an idle local kiosk loads the update.
    if (isKioskDisplay() && Date.now() - lastPageInteraction > 60000 && !document.querySelector("dialog[open]") && !document.activeElement?.matches("input,textarea,select")) location.reload();
  } catch (_) {
    // A deployment restart or disconnected network is retried on the next poll.
  } finally { versionCheckBusy = false; }
}

async function init() {
  state.history.mode = "day";
  state.colonyBackend = localStorage.getItem("piCameraColonyBackend") === "mcount" ? "mcount" : "opencfu";
  state.displayMode = detectDisplayMode();
  applyDisplayMode();
  applyEntryContext();
  if (isKioskDisplay()) {
    enableWakeTouchGuard();
    enableTouchFeedback();
    enableTouchDragScroll();
  }
  wire();
  $("reloadPageBtn").addEventListener("click", () => location.reload());
  setInterval(checkPageVersion, 15000);
  checkPageVersion();
  restoreExportParts();
  syncBulkControls();
  await loadConfig();
  await refreshAll();
  await loadLatestScreenshot();
  setInterval(loadStatus, 5000);

  setInterval(() => { if (!$("photoViewer").open && !$("exportDialog").open) loadHistory().catch(showError); }, 30000);
}

init().catch((err) => {
  $("summary").hidden = false;
  $("summary").textContent = err.message;
});
