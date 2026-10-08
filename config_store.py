from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "interval_seconds": 60,
    "min_interval_seconds": 5,
    "photo_dir": str(BASE_DIR / "photos"),
    "ui_language": "en",
    "stop_pi_service_on_launcher_exit": False,
    "screen_idle_timeout_seconds": 60,
    "mock_camera": False,
    "require_external_mount": False,
    "max_recent_photos": 100,
    "photo_page_size": 8,
    "thumbnail_dir": str(BASE_DIR / "data" / "thumbnails"),
    "thumbnail_max_px": 360,
    "storage_low_space_mb": 512,
    "storage_policy": "local_preferred",
    "local_reserve_mb": 5120,
    "external_device_uuid": "",
    "external_data_dir_name": "PiCameraData",
    "capture_timeout_ms": 1000,
    "autofocus_mode": "auto",
    "autofocus_range": "full",
    "autofocus_window": "0.25,0.25,0.5,0.5",
    "autofocus_on_capture": True,
    "autofocus_min_preview_ms": 3000,
    "light_mode": "off",
    "light_pre_seconds": 1.0,
    "light_post_seconds": 1.0,
    "light_brightness": 0.35,
    "light_color": "#ffffff",
    "sensor_temp_delta_c_warn": 5.0,
    "sensor_temp_delta_percent_warn": 30.0,
    "sensor_humidity_delta_warn": 20.0,
    "sensor_humidity_delta_percent_warn": 30.0,
    "pico_enabled": True,
    "pico_serial_port": "",
    "pico_baud": 115200,
    "pico_timeout_seconds": 2.0,
    "pico_open_delay_seconds": 0.05,
    "history_db_path": str(BASE_DIR / "data" / "history.sqlite3"),
    "colony_count_enabled": True,
    "colony_count_backends": ["opencfu", "mcount"],
    "colony_count_timeout_seconds": 180,
    "colony_runtime_dir": str(BASE_DIR / "data" / "colony-runtime"),
    "opencfu_runtime_root": "",
    "opencfu_command": "",
    "opencfu_max_dimension": 1280,
    "opencfu_suspect_count": 600,
    "mcount_python": "",
    "mcount_script": "",
    "mcount_max_dimension": 400,
    "mcount_timeout_seconds": 30,
    "mcount_lambda": 30.0,
    "mcount_d": 0.5,
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_config(config: dict[str, Any]) -> dict[str, Any]:
    result = dict(DEFAULT_CONFIG)
    result.update(config)
    result["interval_seconds"] = max(int(result["min_interval_seconds"]), int(result["interval_seconds"]))
    result["min_interval_seconds"] = max(1, int(result["min_interval_seconds"]))
    result["max_recent_photos"] = max(1, int(result["max_recent_photos"]))
    result["photo_page_size"] = min(100, max(1, int(result["photo_page_size"])))
    result["thumbnail_max_px"] = min(1200, max(120, int(result["thumbnail_max_px"])))
    result["storage_low_space_mb"] = max(0, int(result["storage_low_space_mb"]))
    if result.get("storage_policy") == "local_only":
        result["storage_policy"] = "local_preferred"
    if result.get("storage_policy") not in {"local_preferred", "external_preferred"}:
        result["storage_policy"] = "local_preferred"
    result["local_reserve_mb"] = max(512, int(result["local_reserve_mb"]))
    result["external_device_uuid"] = str(result.get("external_device_uuid") or "")
    data_dir_name = Path(str(result.get("external_data_dir_name") or "PiCameraData")).name
    result["external_data_dir_name"] = data_dir_name or "PiCameraData"
    for deprecated_key in (
        "external_auto_sync", "external_sync_interval_seconds", "local_cleanup_policy", "local_cleanup_days",
    ):
        result.pop(deprecated_key, None)
    result["capture_timeout_ms"] = max(100, int(result["capture_timeout_ms"]))
    result["screen_idle_timeout_seconds"] = min(
        86400, max(0, int(result["screen_idle_timeout_seconds"]))
    )
    if result.get("autofocus_mode") not in {"manual", "auto", "continuous"}:
        result["autofocus_mode"] = "auto"
    if result.get("autofocus_range") not in {"normal", "macro", "full"}:
        result["autofocus_range"] = "full"
    try:
        focus_window = [float(value.strip()) for value in str(result["autofocus_window"]).split(",")]
        if len(focus_window) != 4:
            raise ValueError
        x, y, width, height = focus_window
        if not (0 <= x < 1 and 0 <= y < 1 and 0 < width <= 1 and 0 < height <= 1):
            raise ValueError
        if x + width > 1 or y + height > 1:
            raise ValueError
        result["autofocus_window"] = ",".join(f"{value:g}" for value in focus_window)
    except (TypeError, ValueError):
        result["autofocus_window"] = "0.25,0.25,0.5,0.5"
    result["autofocus_on_capture"] = bool(result["autofocus_on_capture"])
    result["autofocus_min_preview_ms"] = max(1000, int(result["autofocus_min_preview_ms"]))
    if result.get("light_mode") not in {"off", "on"}:
        result["light_mode"] = "off"
    result["light_pre_seconds"] = max(0.0, float(result["light_pre_seconds"]))
    result["light_post_seconds"] = max(0.0, float(result["light_post_seconds"]))
    result["light_brightness"] = min(1.0, max(0.0, float(result["light_brightness"])))
    if not str(result.get("light_color", "")).startswith("#"):
        result["light_color"] = "#ffffff"
    result["sensor_temp_delta_c_warn"] = max(0.0, float(result["sensor_temp_delta_c_warn"]))
    result["sensor_temp_delta_percent_warn"] = max(0.0, float(result["sensor_temp_delta_percent_warn"]))
    result["sensor_humidity_delta_warn"] = max(0.0, float(result["sensor_humidity_delta_warn"]))
    result["sensor_humidity_delta_percent_warn"] = max(0.0, float(result["sensor_humidity_delta_percent_warn"]))
    result["pico_enabled"] = bool(result["pico_enabled"])
    result["pico_serial_port"] = str(result.get("pico_serial_port") or "")
    result["pico_baud"] = max(1200, int(result["pico_baud"]))
    result["pico_timeout_seconds"] = max(0.2, float(result["pico_timeout_seconds"]))
    result["pico_open_delay_seconds"] = max(0.0, float(result["pico_open_delay_seconds"]))
    result.pop("pico_led_count", None)  # Legacy count no longer limits strip coverage.
    result.pop("sensor_log_interval_seconds", None)
    result.pop("sensor_log_autostart", None)
    result["history_db_path"] = str(Path(str(result["history_db_path"])).expanduser())
    result["colony_count_enabled"] = bool(result["colony_count_enabled"])
    raw_backends = result.get("colony_count_backends")
    if not isinstance(raw_backends, list):
        raw_backends = [part.strip() for part in str(raw_backends or "").split(",")]
    normalized_backends = [str(item).strip().lower() for item in raw_backends]
    result["colony_count_backends"] = [
        backend for backend in normalized_backends if backend in {"opencfu", "mcount"}
    ]
    if "blenny" in normalized_backends and "mcount" not in result["colony_count_backends"]:
        result["colony_count_backends"].append("mcount")
    result["colony_count_backends"] = list(dict.fromkeys(result["colony_count_backends"])) or ["opencfu", "mcount"]
    result["colony_count_timeout_seconds"] = max(10, int(result["colony_count_timeout_seconds"]))
    result["colony_runtime_dir"] = str(Path(str(result["colony_runtime_dir"])).expanduser())
    result["opencfu_runtime_root"] = str(Path(str(result.get("opencfu_runtime_root") or "")).expanduser()) if result.get("opencfu_runtime_root") else ""
    result["opencfu_command"] = str(Path(str(result.get("opencfu_command") or "")).expanduser()) if result.get("opencfu_command") else ""
    result["opencfu_max_dimension"] = max(640, int(result["opencfu_max_dimension"]))
    result["opencfu_suspect_count"] = max(1, int(result["opencfu_suspect_count"]))
    result["mcount_python"] = str(Path(str(result.get("mcount_python") or "")).expanduser()) if result.get("mcount_python") else ""
    result["mcount_script"] = str(Path(str(result.get("mcount_script") or "")).expanduser()) if result.get("mcount_script") else ""
    result["mcount_max_dimension"] = max(320, int(result["mcount_max_dimension"]))
    result["mcount_timeout_seconds"] = max(5, int(result["mcount_timeout_seconds"]))
    result["mcount_lambda"] = max(0.0, float(result["mcount_lambda"]))
    result["mcount_d"] = max(0.0, float(result["mcount_d"]))
    result.pop("blenny_python", None)
    result.pop("blenny_root", None)
    result.pop("blenny_pipeline", None)
    if result.get("ui_language") not in {"zh", "en", "de"}:
        result["ui_language"] = "en"
    result["stop_pi_service_on_launcher_exit"] = bool(result["stop_pi_service_on_launcher_exit"])
    result["mock_camera"] = bool(result["mock_camera"])
    result["require_external_mount"] = bool(result["require_external_mount"])
    result["photo_dir"] = str(Path(str(result["photo_dir"])).expanduser())
    result["thumbnail_dir"] = str(Path(str(result["thumbnail_dir"])).expanduser())
    return result


def load_config() -> dict[str, Any]:
    data: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))

    config = _coerce_config(data)

    if os.environ.get("PHOTO_DIR"):
        config["photo_dir"] = str(Path(os.environ["PHOTO_DIR"]).expanduser())
    config["mock_camera"] = _env_bool("MOCK_CAMERA", config["mock_camera"])
    config["require_external_mount"] = _env_bool("REQUIRE_EXTERNAL_MOUNT", config["require_external_mount"])
    if os.environ.get("CAPTURE_INTERVAL"):
        config["interval_seconds"] = max(config["min_interval_seconds"], int(os.environ["CAPTURE_INTERVAL"]))
    return _coerce_config(config)


def save_config(config: dict[str, Any]) -> dict[str, Any]:
    clean = _coerce_config(config)
    target = CONFIG_PATH.resolve()
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)
    return clean
