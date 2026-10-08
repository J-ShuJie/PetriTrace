from __future__ import annotations

import hashlib
from pathlib import Path

import mimetypes

# Windows registry MIME mappings can incorrectly call SVG image/svg.
mimetypes.add_type("image/svg+xml", ".svg")

import io
import os
import subprocess
import threading
import time
import zipfile
from research_records import capture_index, hydrate, record_page, chart_samples, export_selection, export_estimate, build_export
from datetime import datetime, timedelta
from flask import Flask, Response, jsonify, render_template, request, send_file, send_from_directory

from auth import auth_enabled, require_auth
from camera_backends import create_backend
from colony_counting import ColonyCountingWorker
from config_store import load_config, save_config
from history_store import (
    colony_results_by_filename,
    delete_capture_records,
    photo_timestamp_from_filename,
    export_photo_history_csv,
    informative_photo_filename,
    photo_history_summary,
    photo_history_by_filename,
    query_photo_history,
    query_events,
    query_sensor_samples,
)
from hardware_status import current_hardware_status
from network_status import current_network_status
from scheduler import CaptureScheduler
from display_screenshot import capture_display, latest_screenshot, safe_screenshot_path, screenshot_dir
from external_storage import ExternalStorageManager
from storage import delete_thumbnail, list_photos, photo_dir, safe_photo_path, safe_photo_paths, thumbnail_path

app = Flask(__name__)
app.secret_key = os.environ.get("PI_CAMERA_SECRET", "dev-secret-change-me")

def web_revision():
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted([root / "app.py", *root.glob("templates/**/*"), *root.glob("static/**/*")]):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


WEB_REVISION = web_revision()


@app.get("/api/ui-version")
def ui_version():
    response = jsonify(revision=WEB_REVISION)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.after_request
def fresh_html(response):
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-cache"
    return response


config = load_config()
backend = create_backend(config)
colony_worker = ColonyCountingWorker(config)
external_storage = ExternalStorageManager(config, is_source_busy=colony_worker.is_pending)


def handle_capture(path, result):
    queued = colony_worker.submit(path, result)
    external_storage.refresh()
    return queued


scheduler = CaptureScheduler(
    backend, config, on_capture=handle_capture, storage_target=external_storage.capture_target,
)
external_storage.start()

SLOW_STATUS_TTL_SECONDS = float(os.environ.get("PI_CAMERA_SLOW_STATUS_TTL_SECONDS", "5.0"))
_slow_status_lock = threading.Lock()
_slow_status_cache: dict[str, object] = {"at": 0.0, "data": {}}
_slow_status_refreshing = False


def _collect_slow_status() -> dict:
    return {
        "network": current_network_status(),
        "hardware": current_hardware_status(config),
        "slow_status": {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "stale": False,
        },
    }


def _refresh_slow_status() -> None:
    global _slow_status_refreshing
    try:
        data = _collect_slow_status()
        with _slow_status_lock:
            _slow_status_cache["at"] = time.monotonic()
            _slow_status_cache["data"] = data
    finally:
        with _slow_status_lock:
            _slow_status_refreshing = False


def refresh_slow_status_background() -> None:
    global _slow_status_refreshing
    with _slow_status_lock:
        if _slow_status_refreshing:
            return
        _slow_status_refreshing = True
    threading.Thread(target=_refresh_slow_status, name="slow-status-refresh", daemon=True).start()


def cached_slow_status() -> dict:
    now = time.monotonic()
    with _slow_status_lock:
        at = float(_slow_status_cache.get("at") or 0.0)
        cached = dict(_slow_status_cache.get("data") or {})
    if cached and now - at <= SLOW_STATUS_TTL_SECONDS:
        meta = dict(cached.get("slow_status") or {})
        meta.update({"stale": False, "age_seconds": round(now - at, 2)})
        cached["slow_status"] = meta
        return cached
    if cached:
        refresh_slow_status_background()
        meta = dict(cached.get("slow_status") or {})
        meta.update({"stale": True, "age_seconds": round(now - at, 2)})
        cached["slow_status"] = meta
        return cached
    refresh_slow_status_background()
    return {
        "network": {},
        "hardware": {"power": {}, "sensors": {"sensors": [], "delta": {"ready": False}}},
        "slow_status": {
            "updated_at": None,
            "stale": True,
            "age_seconds": None,
            "refreshing": True,
        },
    }


# Warm slow hardware/network fields without blocking the first page load.
refresh_slow_status_background()


def request_bool(value) -> bool:
    return str(value).lower() in {"1", "true", "yes", "on"}


def request_filenames() -> list[str]:
    data = request.get_json(silent=True) or request.form.to_dict()
    filenames = data.get("filenames", [])
    if isinstance(filenames, str):
        filenames = [filenames]
    return [str(name) for name in filenames if str(name).strip()]


def request_range_defaults() -> tuple[str | None, str | None, int]:
    start = str(request.args.get("start") or "").strip() or None
    end = str(request.args.get("end") or "").strip() or None
    raw_limit = str(request.args.get("limit", 500)).strip().lower()
    limit = 0 if raw_limit == "all" else int(raw_limit)
    if not start and not end and str(request.args.get("mode") or "").strip().lower() != "all":
        start = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    return start, end, limit


def reload_runtime(new_config: dict) -> None:
    global config, backend, scheduler
    old_backend_name = backend.name
    config = new_config
    colony_worker.update_config(config)
    external_storage.update_config(config)
    next_backend = create_backend(config)
    if next_backend.name != old_backend_name:
        was_running = scheduler.status().get("running", False)
        scheduler.stop()
        backend = next_backend
        scheduler = CaptureScheduler(
            backend, config, on_capture=handle_capture, storage_target=external_storage.capture_target,
        )
        if was_running:
            scheduler.start()
    else:
        scheduler.update_config(config)


def restart_screen_idle_service() -> None:
    if os.name == "nt":
        return
    try:
        result = subprocess.run(
            ["systemctl", "--user", "restart", "pi-camera-screen-idle.service"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if result.returncode != 0:
            app.logger.warning("Could not restart screen idle service: %s", result.stderr.strip())
    except (OSError, subprocess.SubprocessError) as exc:
        app.logger.warning("Could not restart screen idle service: %s", exc)


def full_status() -> dict:
    state = scheduler.status()
    state.update(cached_slow_status())
    state["colony_counting"] = colony_worker.status()
    state["screen_idle"] = {
        "timeout_seconds": int(config.get("screen_idle_timeout_seconds", 60))
    }
    state["external_storage"] = external_storage.status()
    return state


@app.get("/")
@require_auth
def index():
    return render_template("index.html", auth_enabled=auth_enabled(), web_revision=WEB_REVISION)


@app.get("/api/status")
@require_auth
def api_status():
    return jsonify(full_status())


@app.get("/api/config")
@require_auth
def api_get_config():
    return jsonify(config)


@app.post("/api/config")
@require_auth
def api_set_config():
    data = request.get_json(silent=True) or request.form.to_dict()
    updated = dict(config)
    old_screen_idle_timeout = int(config.get("screen_idle_timeout_seconds", 60))
    if "interval_seconds" in data:
        updated["interval_seconds"] = int(data["interval_seconds"])
    if "mock_camera" in data:
        updated["mock_camera"] = request_bool(data["mock_camera"])
    if "stop_pi_service_on_launcher_exit" in data:
        updated["stop_pi_service_on_launcher_exit"] = request_bool(data["stop_pi_service_on_launcher_exit"])
    if "ui_language" in data:
        updated["ui_language"] = str(data["ui_language"]).strip()
    if "photo_dir" in data and str(data["photo_dir"]).strip():
        updated["photo_dir"] = str(data["photo_dir"]).strip()
    for key in (
        "light_mode",
        "light_pre_seconds",
        "light_post_seconds",
        "light_brightness",
        "light_color",
        "sensor_temp_delta_c_warn",
        "sensor_temp_delta_percent_warn",
        "sensor_humidity_delta_warn",
        "sensor_humidity_delta_percent_warn",
        "pico_enabled",
        "pico_serial_port",
        "pico_baud",
        "pico_timeout_seconds",
        "pico_open_delay_seconds",
        "history_db_path",
        "screen_idle_timeout_seconds",
        "colony_count_enabled",
        "colony_count_backends",
        "colony_count_timeout_seconds",
        "colony_runtime_dir",
        "opencfu_runtime_root",
        "opencfu_command",
        "opencfu_max_dimension",
        "opencfu_suspect_count",
        "mcount_python",
        "mcount_script",
        "mcount_max_dimension",
        "mcount_timeout_seconds",
        "mcount_lambda",
        "mcount_d",
        "storage_policy",
        "local_reserve_mb",
        "external_device_uuid",
        "external_data_dir_name",
    ):
        if key in data:
            updated[key] = data[key]
    clean = save_config(updated)
    reload_runtime(clean)
    if int(clean.get("screen_idle_timeout_seconds", 60)) != old_screen_idle_timeout:
        restart_screen_idle_service()
    return jsonify(clean)


@app.post("/api/external-storage/snapshot")
@require_auth
def api_external_storage_snapshot():
    try:
        return jsonify(external_storage.request_snapshot_copy())
    except Exception as exc:  # noqa: BLE001 - surfaced to UI
        return jsonify({"ok": False, "error": str(exc)}), 409


@app.post("/api/external-storage/eject")
@require_auth
def api_external_storage_eject():
    try:
        return jsonify(external_storage.safe_eject())
    except Exception as exc:  # noqa: BLE001 - surfaced to UI
        return jsonify({"ok": False, "error": str(exc)}), 409


@app.post("/api/start")
@require_auth
def api_start():
    data = request.get_json(silent=True) or request.form.to_dict()
    if "interval_seconds" in data:
        updated = dict(config)
        updated["interval_seconds"] = int(data["interval_seconds"])
        clean = save_config(updated)
        reload_runtime(clean)
    return jsonify(scheduler.start())


@app.post("/api/stop")
@require_auth
def api_stop():
    return jsonify(scheduler.stop())


@app.post("/api/light")
@require_auth
def api_light():
    data = request.get_json(silent=True) or request.form.to_dict()
    updated = dict(config)
    updated["light_mode"] = str(data.get("light_mode", config.get("light_mode", "off"))).strip().lower()
    clean = save_config(updated)
    reload_runtime(clean)
    return jsonify(scheduler.status().get("light", {}))


@app.get("/api/history/sensors")
@require_auth
def api_history_sensors():
    start, end, limit = request_range_defaults()
    return jsonify(
        {
            "samples": query_sensor_samples(config, start=start, end=end, limit=limit, photo_only=True),
            "start": start,
            "end": end,
        }
    )


@app.get("/api/history/events")
@require_auth
def api_history_events():
    start, end, limit = request_range_defaults()
    return jsonify({"events": query_events(config, start=start, end=end, limit=limit), "start": start, "end": end})


@app.get("/api/history")
@require_auth
def api_history():
    mode = str(request.args.get("mode") or "auto").strip().lower()
    if mode not in {"auto", "all", "custom"}:
        mode = "auto"
    start = str(request.args.get("start") or "").strip() or None
    end = str(request.args.get("end") or "").strip() or None
    raw_limit = str(request.args.get("limit") or "300").strip().lower()
    if mode == "auto":
        start = None
        end = None
        try:
            limit = min(1000, max(40, int(raw_limit)))
        except ValueError:
            limit = 300
        newest = True
    else:
        if raw_limit == "all":
            limit = 0
        else:
            try:
                limit = max(1, int(raw_limit))
            except ValueError:
                limit = 500
        newest = False
        if mode == "all":
            start = None
            end = None
    records = {row["filename"]: row for row in query_photo_history(config, start=start, end=end, limit=0)}
    photos = list_photos(config, limit=0, additional_dirs=external_storage.photo_directories())
    for photo in photos:
        name = photo["filename"]
        stamp = photo_timestamp_from_filename(name, datetime.fromtimestamp(photo["mtime"]).isoformat(timespec="seconds"))
        if (start and stamp < start) or (end and stamp > end):
            continue
        record = records.setdefault(name, {"filename": name, "timestamp": stamp, "counts": {}})
        record["photo"] = photo
    ordered = sorted(records.values(), key=lambda row: (row["timestamp"], row["filename"]))
    summary = {"total": len(ordered), "start": ordered[0]["timestamp"] if ordered else None,
               "end": ordered[-1]["timestamp"] if ordered else None}
    if limit > 0:
        ordered = ordered[-limit:] if newest else ordered[:limit]
    return jsonify({"records": ordered, "start": start, "end": end, "mode": mode, "summary": summary})


def research_range():
    if request.args.get("mode") == "all": return None, None
    return request.args.get("start") or None, request.args.get("end") or None


@app.get("/api/records")
@require_auth
def api_records():
    start, end = research_range()
    index = capture_index(config, external_storage.photo_directories(), start, end)
    return jsonify(record_page(config, index, request.args.get("page", 1), request.args.get("page_size", 25), focus=request.args.get("focus")))


@app.get("/api/charts")
@require_auth
def api_charts():
    start, end = research_range()
    index = capture_index(config, external_storage.photo_directories(), start, end)
    records = chart_samples(config, index)
    focused = [row for row in index if row["filename"] == request.args.get("focus")]
    focus_record = hydrate(config, focused)[0] if focused else None
    return jsonify({"records": records, "summary": {"total": len(index)}, "sampled": len(records) < len(index), "focus_record": focus_record})


@app.post("/api/export/preview")
@require_auth
def api_export_preview():
    try:
        index, parts, start, end = export_selection(config, external_storage.photo_directories(), request.get_json() or {})
        return jsonify(export_estimate(config, index, parts, start, end))
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


_export_lock = threading.Lock()

@app.post("/api/export")
@require_auth
def api_export():
    if not _export_lock.acquire(blocking=False):
        return jsonify({"error": "An export is already being prepared. Please retry when it finishes."}), 409
    try:
        import json
        data = request.get_json(silent=True) or json.loads(request.form.get("payload", "{}"))
        temporary, path, mimetype = build_export(config, external_storage.photo_directories(), data)
    except (ValueError, TypeError, OSError) as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        _export_lock.release()
    def stream():
        try:
            with path.open("rb") as source:
                while block := source.read(256 * 1024): yield block
        finally: temporary.cleanup()
    response = Response(stream(), mimetype=mimetype, headers={"Content-Disposition": f'attachment; filename="{path.name}"', "Content-Length": str(path.stat().st_size)})
    response.call_on_close(temporary.cleanup)
    return response


@app.get("/api/history/export.csv")
@require_auth
def api_history_export_csv():
    if str(request.args.get("mode") or "").strip().lower() == "all":
        start, end, limit = None, None, 0
    else:
        start, end, limit = request_range_defaults()
    csv_text = export_photo_history_csv(config, start=start, end=end, limit=limit)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        csv_text,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=pi-camera-photo-history-{stamp}.csv"},
    )


@app.post("/api/capture-now")
@require_auth
def api_capture_now():
    try:
        return jsonify(scheduler.capture_now(reason="manual"))
    except Exception as exc:  # noqa: BLE001 - surfaced to UI
        return jsonify({"ok": False, "error": str(exc)}), 409


@app.get("/api/photos")
@require_auth
def api_photos():
    raw_limit = str(request.args.get("limit", config.get("photo_page_size", 8))).strip().lower()
    if raw_limit == "all":
        limit = 0
    else:
        try:
            limit = max(1, int(raw_limit))
        except ValueError:
            limit = int(config.get("photo_page_size", 8))
    photos = list_photos(config, limit=limit, additional_dirs=external_storage.photo_directories())
    counts = colony_results_by_filename(config, [photo["filename"] for photo in photos])
    for photo in photos:
        photo["colony_counts"] = counts.get(photo["filename"], {})
    return jsonify(photos)


@app.post("/api/colony-counts/backfill")
@require_auth
def api_colony_counts_backfill():
    data = request.get_json(silent=True) or request.form.to_dict()
    force = request_bool(data.get("force", False))
    queued = 0
    external_dirs = external_storage.photo_directories()
    for photo in list_photos(config, limit=0, additional_dirs=external_dirs):
        if colony_worker.submit(safe_photo_path(config, photo["filename"], external_dirs), force=force):
            queued += 1
    return jsonify({"ok": True, "queued": queued, "status": colony_worker.status()})


@app.delete("/api/photos/<path:filename>")
@require_auth
def api_delete_photo(filename: str):
    try:
        paths = [path for path in safe_photo_paths(config, filename, external_storage.photo_directories()) if path.exists()]
        for path in paths:
            path.unlink()
        delete_thumbnail(config, filename)
        delete_capture_records(config, [filename])
        scheduler.forget_photo(filename)
        return jsonify({"ok": True, "filename": filename})
    except Exception as exc:  # noqa: BLE001 - surfaced to UI
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/photos/bulk-delete")
@require_auth
def api_bulk_delete_photos():
    deleted = []
    missing = []
    errors = []
    for filename in request_filenames():
        try:
            paths = [path for path in safe_photo_paths(config, filename, external_storage.photo_directories()) if path.exists()]
            if not paths:
                missing.append(filename)
            for path in paths:
                path.unlink()
            delete_thumbnail(config, filename)
            scheduler.forget_photo(filename)
            deleted.append(filename)
        except Exception as exc:  # noqa: BLE001 - surfaced to UI
            errors.append({"filename": filename, "error": str(exc)})
    delete_capture_records(config, deleted)
    return jsonify({"ok": not errors, "deleted": deleted, "missing": missing, "errors": errors})


@app.post("/api/photos/bulk-download")
@require_auth
def api_bulk_download_photos():
    archive = io.BytesIO()
    added = []
    filenames = request_filenames()
    metadata = photo_history_by_filename(config, filenames)
    used_names: set[str] = set()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        external_dirs = external_storage.photo_directories()
        for filename in filenames:
            path = safe_photo_path(config, filename, external_dirs)
            if path.exists():
                archive_name = informative_photo_filename(path.name, metadata.get(path.name))
                candidate = archive_name
                sequence = 2
                while candidate.casefold() in used_names:
                    name_path = os.path.splitext(archive_name)
                    candidate = f"{name_path[0]}-{sequence}{name_path[1]}"
                    sequence += 1
                used_names.add(candidate.casefold())
                zf.write(path, arcname=candidate)
                added.append(candidate)
    if not added:
        return jsonify({"ok": False, "error": "No selected photos found"}), 404
    archive.seek(0)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        archive,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"pi-camera-photos-{stamp}.zip",
    )


@app.get("/photos/<path:filename>")
@require_auth
def view_photo(filename: str):
    path = safe_photo_path(config, filename, external_storage.photo_directories())
    if not path.exists():
        return jsonify({"ok": False, "error": "Photo not found"}), 404
    return send_file(path)


@app.get("/thumbs/<path:filename>")
@require_auth
def view_thumbnail(filename: str):
    path = thumbnail_path(config, filename, external_storage.photo_directories())
    return send_file(path, mimetype="image/jpeg", max_age=86400)


@app.get("/download/<path:filename>")
@require_auth
def download_photo(filename: str):
    path = safe_photo_path(config, filename, external_storage.photo_directories())
    metadata = photo_history_by_filename(config, [filename]).get(filename)
    return send_file(
        path,
        as_attachment=True,
        download_name=informative_photo_filename(filename, metadata),
    )



def screenshot_payload(item: dict | None) -> dict | None:
    if not item:
        return None
    payload = dict(item)
    payload["url"] = f"/screenshots/{payload['filename']}"
    payload["download_url"] = f"/download/screenshot/{payload['filename']}"
    return payload


@app.post("/api/display-screenshot")
@require_auth
def api_display_screenshot():
    try:
        return jsonify({"ok": True, "screenshot": screenshot_payload(capture_display(config))})
    except Exception as exc:  # noqa: BLE001 - surfaced to UI
        return jsonify({"ok": False, "error": str(exc)}), 409


@app.get("/api/display-screenshot/latest")
@require_auth
def api_latest_display_screenshot():
    shot = screenshot_payload(latest_screenshot(config))
    if not shot:
        return jsonify({"ok": False, "error": "No display screenshot yet"}), 404
    return jsonify({"ok": True, "screenshot": shot})


@app.get("/screenshots/<path:filename>")
@require_auth
def view_screenshot(filename: str):
    safe_screenshot_path(config, filename)
    return send_from_directory(screenshot_dir(config), filename)


@app.get("/download/screenshot/<path:filename>")
@require_auth
def download_screenshot(filename: str):
    safe_screenshot_path(config, filename)
    return send_from_directory(screenshot_dir(config), filename, as_attachment=True)

@app.get("/health")
def health():
    return {"ok": True, "backend": backend.name}


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug, threaded=True)
