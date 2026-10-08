from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from history_store import export_photo_history_csv, photo_history_by_filename
from storage import ALLOWED_EXTENSIONS, check_storage, photo_dir, photo_file_summary


SUPPORTED_FILESYSTEMS = {"ntfs", "ntfs3", "exfat", "vfat", "fat", "fat32", "ext4"}
ARCHIVE_VERSION = 1
_MIB = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def atomic_copy_verified(source: Path, destination: Path) -> tuple[str, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
    source_digest = hashlib.sha256()
    with source.open("rb") as reader, temporary.open("wb") as writer:
        while block := reader.read(1024 * 1024):
            source_digest.update(block)
            writer.write(block)
        writer.flush()
        os.fsync(writer.fileno())
    expected = source_digest.hexdigest()
    actual = sha256_file(temporary)
    if actual != expected:
        temporary.unlink(missing_ok=True)
        raise IOError(f"SHA-256 verification failed for {source.name}")
    temporary.replace(destination)
    return expected, destination.stat().st_size


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": ARCHIVE_VERSION, "items": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {"version": ARCHIVE_VERSION, "items": {}}
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), dict):
        return {"version": ARCHIVE_VERSION, "items": {}}
    return payload


def _device_metadata(archive_root: Path) -> dict[str, Any]:
    path = archive_root / "device.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(payload, dict) and payload.get("archive_id"):
                return payload
        except (OSError, json.JSONDecodeError):
            pass
    payload = {
        "version": ARCHIVE_VERSION,
        "archive_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "application": "Pi Camera Control",
    }
    _atomic_json(path, payload)
    return payload


def _snapshot_database_bytes(config: dict[str, Any]) -> bytes:
    source_path = Path(str(config["history_db_path"])).expanduser()
    if not source_path.exists():
        return b""
    temporary = source_path.with_name(f".{source_path.name}.{uuid.uuid4().hex}.snapshot")
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(temporary)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    try:
        return temporary.read_bytes()
    finally:
        temporary.unlink(missing_ok=True)


def _source_photos(config: dict[str, Any], additional_dirs: list[Path] | None = None) -> list[Path]:
    directories = [photo_dir(config), *(additional_dirs or [])]
    sources: dict[str, Path] = {}
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS:
                sources.setdefault(path.name, path)
    return sorted(sources.values(), key=lambda item: item.name)


def create_snapshot_payload(
    config: dict[str, Any], additional_dirs: list[Path] | None = None,
    source_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Freeze the app-managed dataset at the instant the user presses the copy button."""
    sources = list(source_paths) if source_paths is not None else _source_photos(config, additional_dirs)
    names = [path.name for path in sources]
    return {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot_id": datetime.now().strftime("%Y%m%d-%H%M%S-%f"),
        "sources": sources,
        "metadata": photo_history_by_filename(config, names) if names else {},
        "history_csv": export_photo_history_csv(config, limit=0),
        "history_database": _snapshot_database_bytes(config),
    }


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _copy_payload(
    config: dict[str, Any], mount_path: Path, payload: dict[str, Any], *,
    destination_root: Path, delete_verified_local: bool,
) -> dict[str, Any]:
    started = time.monotonic()
    mount_path = mount_path.expanduser().resolve()
    if not mount_path.is_dir():
        raise FileNotFoundError(f"External mount is unavailable: {mount_path}")
    if not os.access(mount_path, os.W_OK):
        raise PermissionError(f"External mount is read-only: {mount_path}")

    archive_root = destination_root
    photos_root = archive_root / "photos"
    metadata_root = archive_root / "metadata"
    exports_root = archive_root / "exports"
    archive_root.mkdir(parents=True, exist_ok=True)
    device = _device_metadata(archive_root)
    manifest_path = archive_root / "manifest.json"
    manifest = _load_manifest(manifest_path)
    items: dict[str, Any] = dict(manifest.get("items") or {})
    sources = list(payload.get("sources") or [])
    metadata = dict(payload.get("metadata") or {})

    copied = 0
    verified: list[Path] = []
    errors: list[dict[str, str]] = []
    for source in sources:
        relative = f"photos/{source.name}"
        destination = photos_root / source.name
        stat = source.stat()
        entry = items.get(relative) if isinstance(items.get(relative), dict) else {}
        unchanged = (
            destination.exists()
            and int(entry.get("size", -1)) == stat.st_size
            and int(entry.get("source_mtime_ns", -1)) == stat.st_mtime_ns
            and bool(entry.get("sha256"))
        )
        try:
            if unchanged:
                digest = str(entry["sha256"])
            else:
                digest, _size = atomic_copy_verified(source, destination)
                copied += 1
            entry = {
                "sha256": digest,
                "size": stat.st_size,
                "source_mtime_ns": stat.st_mtime_ns,
                "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            items[relative] = entry
            _atomic_json(metadata_root / f"{source.name}.json", metadata.get(source.name, {
                "filename": source.name,
                "timestamp": None,
                "counts": {},
            }))
            verified.append(source)
        except (OSError, ValueError) as exc:
            errors.append({"filename": source.name, "error": str(exc)})

    _atomic_text(exports_root / "history.csv", str(payload.get("history_csv") or ""))
    database = payload.get("history_database")
    if isinstance(database, bytes) and database:
        _atomic_bytes(exports_root / "history.sqlite3", database)
    manifest = {
        "version": ARCHIVE_VERSION,
        "archive_id": device["archive_id"],
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": items,
    }
    _atomic_json(manifest_path, manifest)
    removed: list[str] = []
    if delete_verified_local:
        local_root = photo_dir(config)
        for source in verified:
            try:
                if source.parent.resolve() == local_root and source.exists():
                    source.unlink()
                    removed.append(source.name)
            except OSError:
                continue
    usage = shutil.disk_usage(mount_path)
    reserve_mb = max(0, int(config.get("local_reserve_mb", 5120)))
    return {
        "ok": not errors,
        "archive_id": device["archive_id"],
        "archive_root": str(archive_root),
        "photo_dir": str(photos_root),
        "copied": copied,
        "verified": len(verified),
        "pending": len(errors),
        "cleaned_local": len(removed),
        "cleaned_filenames": removed,
        "errors": errors,
        "free_mb": usage.free // _MIB,
        "total_mb": usage.total // _MIB,
        "reserve_mb": reserve_mb,
        "low_space": (usage.free // _MIB) < reserve_mb,
        "duration_seconds": round(time.monotonic() - started, 3),
        "last_operation_at": datetime.now().isoformat(timespec="seconds"),
    }


def copy_snapshot_archive(config: dict[str, Any], mount_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    root = mount_path.expanduser().resolve() / str(config.get("external_data_dir_name", "PiCameraData"))
    destination = root / "snapshots" / str(payload.get("snapshot_id") or datetime.now().strftime("%Y%m%d-%H%M%S"))
    return _copy_payload(config, mount_path, payload, destination_root=destination, delete_verified_local=False)


def migrate_local_archive(
    config: dict[str, Any], mount_path: Path, source_paths: list[Path] | None = None,
) -> dict[str, Any]:
    payload = create_snapshot_payload(config, source_paths=source_paths)
    root = mount_path.expanduser().resolve() / str(config.get("external_data_dir_name", "PiCameraData"))
    return _copy_payload(config, mount_path, payload, destination_root=root, delete_verified_local=True)


def _flatten_lsblk(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for node in nodes:
        flattened.append(node)
        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict) and not child.get("tran"):
                    child["tran"] = node.get("tran")
                flattened.extend(_flatten_lsblk([child]))
    return flattened


def devices_from_lsblk(payload: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = _flatten_lsblk(payload.get("blockdevices") or [])
    devices: list[dict[str, Any]] = []
    for node in nodes:
        if str(node.get("type") or "") not in {"disk", "part"}:
            continue
        removable = bool(node.get("rm")) or str(node.get("tran") or "").lower() == "usb"
        if not removable:
            continue
        mountpoints = [str(item) for item in (node.get("mountpoints") or []) if item]
        filesystem = str(node.get("fstype") or "").lower()
        devices.append({
            "path": str(node.get("path") or ""),
            "label": str(node.get("label") or ""),
            "uuid": str(node.get("uuid") or ""),
            "filesystem": filesystem,
            "size_bytes": int(node.get("size") or 0),
            "free_bytes": int(node["fsavail"]) if node.get("fsavail") is not None else None,
            "mount_path": mountpoints[0] if mountpoints else "",
            "read_only": bool(node.get("ro")),
            "supported": filesystem in SUPPORTED_FILESYSTEMS,
            "unformatted": not filesystem,
            "recommended_format": "ntfs" if not filesystem else None,
        })
    return devices


def discover_external_devices() -> list[dict[str, Any]]:
    if os.name == "nt":
        return []
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-b", "-o", "PATH,LABEL,UUID,FSTYPE,SIZE,FSAVAIL,MOUNTPOINTS,RM,RO,TYPE,TRAN"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            return []
        return devices_from_lsblk(json.loads(result.stdout))
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []


class ExternalStorageManager:
    def __init__(
        self, config: dict[str, Any], is_source_busy: Callable[[Path], bool] | None = None,
    ) -> None:
        self._config = config
        self._is_source_busy = is_source_busy or (lambda _path: False)
        self._lock = threading.Lock()
        self._operation_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot_request: dict[str, Any] | None = None
        self._first_seen: dict[str, int] = {}
        self._seen_counter = 0
        self._status: dict[str, Any] = {
            "state": "disconnected",
            "connected": False,
            "busy": False,
            "operation": None,
            "devices": [],
            "last_error": None,
        }

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="external-storage-router", daemon=True)
        self._thread.start()

    def update_config(self, config: dict[str, Any]) -> None:
        with self._lock:
            self._config = config
        self.refresh()

    def refresh(self) -> None:
        self._wake.set()

    def request_snapshot_copy(self) -> dict[str, Any]:
        if self._operation_lock.locked():
            raise RuntimeError("External storage is busy")
        status = self.status()
        if not status.get("connected"):
            raise RuntimeError("No mounted external storage")
        if status.get("low_space"):
            raise RuntimeError("External storage has reached the safety reserve")
        with self._lock:
            config = dict(self._config)
            if self._snapshot_request is not None:
                raise RuntimeError("A snapshot copy is already queued")
        payload = create_snapshot_payload(config, self.photo_directories())
        with self._lock:
            if self._snapshot_request is not None:
                raise RuntimeError("A snapshot copy is already queued")
            self._snapshot_request = payload
            self._status = {
                **self._status,
                "state": "copying_snapshot",
                "busy": True,
                "operation": "snapshot_copy",
                "snapshot_created_at": payload["created_at"],
                "snapshot_photo_count": len(payload["sources"]),
            }
        self._wake.set()
        return {
            "ok": True,
            "snapshot_created_at": payload["created_at"],
            "photo_count": len(payload["sources"]),
        }

    def safe_eject(self) -> dict[str, Any]:
        if self._operation_lock.locked():
            raise RuntimeError("External storage is busy")
        status = self.status()
        device = status.get("device") if isinstance(status.get("device"), dict) else {}
        device_path = str(device.get("path") or "")
        if not device_path:
            raise RuntimeError("No mounted external storage")
        result = subprocess.run(
            ["udisksctl", "unmount", "-b", device_path],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Could not unmount external storage")
        with self._lock:
            self._status = {
                "state": "disconnected", "connected": False, "busy": False,
                "operation": None, "devices": [], "last_error": None,
            }
        return {"ok": True, "message": result.stdout.strip()}

    def status(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._status))

    def photo_directories(self) -> list[Path]:
        status = self.status()
        path = status.get("photo_dir")
        return [Path(str(path))] if path and Path(str(path)).is_dir() else []

    def capture_target(self) -> dict[str, Any]:
        with self._lock:
            config = dict(self._config)
            status = dict(self._status)
        local = check_storage(config)
        policy = str(config.get("storage_policy", "local_preferred"))
        external_ready = bool(status.get("connected")) and not bool(status.get("low_space"))
        external_dir = status.get("photo_dir")

        if policy == "external_preferred":
            if external_ready and external_dir:
                return {"ready": True, "location": "external", "directory": str(external_dir), "reason": "external_preferred"}
            if local.get("ready"):
                reason = "external_low_space" if status.get("connected") and status.get("low_space") else "external_unavailable"
                return {"ready": True, "location": "local", "directory": str(photo_dir(config)), "reason": reason}
            return {"ready": False, "location": None, "directory": None, "reason": "no_storage_available", "error": "Neither external storage nor local fallback has safe capacity"}

        if local.get("ready"):
            return {"ready": True, "location": "local", "directory": str(photo_dir(config)), "reason": "local_preferred"}
        if external_ready and external_dir:
            return {"ready": True, "location": "external", "directory": str(external_dir), "reason": "local_low_space"}
        return {"ready": False, "location": None, "directory": None, "reason": "local_low_space_no_external", "error": "Local storage reached its safety reserve and no writable external storage is available"}

    def _select_device(self, devices: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any] | None:
        selected_uuid = str(config.get("external_device_uuid") or "")
        mounted = [device for device in devices if device.get("supported") and device.get("mount_path") and not device.get("read_only")]
        for device in mounted:
            identity = str(device.get("uuid") or device.get("path") or device.get("mount_path"))
            if identity not in self._first_seen:
                self._seen_counter += 1
                self._first_seen[identity] = self._seen_counter
        if selected_uuid:
            return next((device for device in mounted if device.get("uuid") == selected_uuid), None)
        return min(
            mounted,
            key=lambda item: self._first_seen.get(str(item.get("uuid") or item.get("path") or item.get("mount_path")), 0),
            default=None,
        )

    def _cycle(self) -> None:
        with self._lock:
            config = dict(self._config)
        devices = discover_external_devices()
        device = self._select_device(devices, config)
        if not device:
            unformatted = [item for item in devices if item.get("unformatted")]
            with self._lock:
                self._status = {
                    "state": "unformatted" if unformatted else "disconnected",
                    "connected": False,
                    "busy": False,
                    "operation": None,
                    "devices": devices,
                    "recommended_format": "ntfs" if unformatted else None,
                    "last_error": None,
                }
            return
        reserve_mb = max(0, int(config.get("local_reserve_mb", 5120)))
        free_bytes = device.get("free_bytes")
        free_mb = int(free_bytes) // _MIB if free_bytes is not None else None
        total_mb = int(device.get("size_bytes") or 0) // _MIB
        external_photo_dir = (
            Path(str(device["mount_path"]))
            / str(config.get("external_data_dir_name", "PiCameraData"))
            / "photos"
        )
        external_photos = (
            photo_file_summary(external_photo_dir)
            if external_photo_dir.is_dir()
            else {"photo_count": 0, "photo_bytes": 0, "average_photo_bytes": None}
        )
        local_directory = photo_dir(config) if config.get("photo_dir") else None
        local_average = (
            photo_file_summary(local_directory).get("average_photo_bytes")
            if local_directory is not None and local_directory.is_dir()
            else None
        )
        estimate_average = external_photos.get("average_photo_bytes") or local_average
        usable_free_bytes = (
            max(0, (free_mb - reserve_mb) * _MIB)
            if free_mb is not None
            else None
        )
        estimated_remaining = (
            usable_free_bytes // int(estimate_average)
            if usable_free_bytes is not None and isinstance(estimate_average, int) and estimate_average > 0
            else None
        )
        used_mb = max(0, total_mb - free_mb) if free_mb is not None else None
        base = {
            "state": "connected", "connected": True, "busy": False,
            "operation": None, "device": device, "devices": devices, "last_error": None,
            "free_mb": free_mb, "used_mb": used_mb, "total_mb": total_mb,
            "used_percent": round((used_mb / total_mb) * 100, 1) if total_mb and used_mb is not None else 0.0,
            "reserve_mb": reserve_mb,
            "low_space": free_mb is not None and free_mb < reserve_mb,
            "photo_dir": str(external_photo_dir),
            **external_photos,
            "estimated_remaining_photos": estimated_remaining,
        }
        with self._lock:
            snapshot_request = self._snapshot_request
        if snapshot_request is not None and not base["low_space"]:
            self._run_snapshot_copy(config, device, base, snapshot_request)
            return

        if str(config.get("storage_policy", "local_preferred")) != "external_preferred" or base["low_space"]:
            with self._lock:
                self._status = base
            return

        local_sources = [path for path in _source_photos(config) if not self._is_source_busy(path)]
        if not local_sources:
            with self._lock:
                self._status = {**base, "state": "ready"}
            return
        with self._operation_lock:
            with self._lock:
                self._status = {**base, "state": "migrating", "busy": True, "operation": "fallback_migration"}
            try:
                result = migrate_local_archive(
                    config, Path(str(device["mount_path"])), source_paths=local_sources,
                )
                with self._lock:
                    self._status = {**base, **result, "state": "ready" if result["ok"] else "error", "busy": False, "operation": None}
            except Exception as exc:  # noqa: BLE001 - reported in status and retried later
                with self._lock:
                    self._status = {**base, "state": "error", "busy": False, "operation": None, "last_error": str(exc)}

    def _run_snapshot_copy(
        self, config: dict[str, Any], device: dict[str, Any], base: dict[str, Any], payload: dict[str, Any]
    ) -> None:
        with self._operation_lock:
            with self._lock:
                self._status = {**base, "state": "copying_snapshot", "busy": True, "operation": "snapshot_copy"}
            try:
                result = copy_snapshot_archive(config, Path(str(device["mount_path"])), payload)
                with self._lock:
                    self._snapshot_request = None
                    self._status = {
                        **base, **result, "state": "ready" if result["ok"] else "error",
                        "busy": False, "operation": None,
                    }
            except Exception as exc:  # noqa: BLE001 - surfaced and may be retried manually
                with self._lock:
                    self._snapshot_request = None
                    self._status = {**base, "state": "error", "busy": False, "operation": None, "last_error": str(exc)}

    def _run(self) -> None:
        while not self._stop.is_set():
            self._cycle()
            self._wake.wait(5)
            self._wake.clear()
