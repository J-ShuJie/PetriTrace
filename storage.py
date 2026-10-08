from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path
from typing import Any
from werkzeug.utils import secure_filename
from PIL import Image, ImageFile, ImageOps

ImageFile.LOAD_TRUNCATED_IMAGES = True

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
THUMBNAIL_SUFFIX = ".thumb.jpg"
_MIB = 1024 * 1024
_PHOTO_SUMMARY_LOCK = threading.Lock()
_PHOTO_SUMMARY_CACHE: dict[str, tuple[int, dict[str, int | None]]] = {}


def photo_dir(config: dict[str, Any]) -> Path:
    return Path(str(config["photo_dir"])).expanduser().resolve()


def thumbnail_dir(config: dict[str, Any]) -> Path:
    return Path(str(config.get("thumbnail_dir", photo_dir(config) / ".thumbnails"))).expanduser().resolve()


def photo_file_summary(directory: Path) -> dict[str, int | None]:
    """Return a directory-mtime-cached summary of stored source photos."""
    directory_mtime_ns = directory.stat().st_mtime_ns
    cache_key = str(directory)
    with _PHOTO_SUMMARY_LOCK:
        cached = _PHOTO_SUMMARY_CACHE.get(cache_key)
        if cached and cached[0] == directory_mtime_ns:
            return dict(cached[1])

    photo_count = 0
    photo_bytes = 0
    with os.scandir(directory) as entries:
        for entry in entries:
            if not entry.is_file(follow_symlinks=False):
                continue
            if Path(entry.name).suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            try:
                photo_bytes += entry.stat(follow_symlinks=False).st_size
                photo_count += 1
            except OSError:
                # A concurrent capture/delete can briefly remove an entry after scandir.
                continue

    average_photo_bytes = photo_bytes // photo_count if photo_count else None
    summary: dict[str, int | None] = {
        "photo_count": photo_count,
        "photo_bytes": photo_bytes,
        "average_photo_bytes": average_photo_bytes,
    }
    with _PHOTO_SUMMARY_LOCK:
        _PHOTO_SUMMARY_CACHE[cache_key] = (directory_mtime_ns, dict(summary))
    return summary


def check_storage(config: dict[str, Any]) -> dict[str, Any]:
    directory = photo_dir(config)
    mount_point = directory.parent
    try:
        if config.get("require_external_mount") and not os.path.ismount(mount_point):
            return {
                "ready": False,
                "photo_dir": str(directory),
                "error": f"Required external mount is not mounted: {mount_point}",
            }
        directory.mkdir(parents=True, exist_ok=True)
        thumbnail_dir(config).mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        usage = shutil.disk_usage(directory)
        free_mb = usage.free // _MIB
        reserve_mb = int(config.get("local_reserve_mb", config.get("storage_low_space_mb", 512)))
        low_space = free_mb < reserve_mb
        photo_summary = photo_file_summary(directory)
        average_photo_bytes = photo_summary["average_photo_bytes"]
        reserved_bytes = max(0, reserve_mb) * _MIB
        usable_free_bytes = max(0, usage.free - reserved_bytes)
        estimated_remaining_photos = (
            usable_free_bytes // average_photo_bytes
            if isinstance(average_photo_bytes, int) and average_photo_bytes > 0
            else None
        )
        return {
            "ready": not low_space,
            "photo_dir": str(directory),
            "free_mb": free_mb,
            "used_mb": usage.used // _MIB,
            "total_mb": usage.total // _MIB,
            "used_percent": round((usage.used / usage.total) * 100, 1) if usage.total else 0.0,
            **photo_summary,
            "estimated_remaining_photos": estimated_remaining_photos,
            "reserve_mb": reserve_mb,
            "low_space": low_space,
            "error": "Low storage space" if low_space else None,
        }
    except Exception as exc:  # noqa: BLE001 - surfaced in UI
        return {"ready": False, "photo_dir": str(directory), "error": str(exc)}


def _photo_source_dirs(config: dict[str, Any], additional_dirs: list[Path] | None = None) -> list[Path]:
    directories = [photo_dir(config), *(additional_dirs or [])]
    unique: list[Path] = []
    seen: set[str] = set()
    for directory in directories:
        resolved = directory.expanduser().resolve()
        key = str(resolved).casefold()
        if key not in seen:
            unique.append(resolved)
            seen.add(key)
    return unique


def safe_photo_paths(
    config: dict[str, Any], filename: str, additional_dirs: list[Path] | None = None
) -> list[Path]:
    safe = secure_filename(filename)
    if Path(safe).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported photo extension")
    paths = []
    for base in _photo_source_dirs(config, additional_dirs):
        path = (base / safe).resolve()
        if base not in path.parents and path != base:
            raise ValueError("Invalid photo path")
        paths.append(path)
    return paths


def safe_photo_path(
    config: dict[str, Any], filename: str, additional_dirs: list[Path] | None = None
) -> Path:
    paths = safe_photo_paths(config, filename, additional_dirs)
    return next((path for path in paths if path.exists()), paths[0])


def _safe_thumbnail_path(config: dict[str, Any], filename: str) -> Path:
    safe = secure_filename(filename)
    directory = thumbnail_dir(config)
    path = (directory / f"{safe}{THUMBNAIL_SUFFIX}").resolve()
    if directory not in path.parents and path != directory:
        raise ValueError("Invalid thumbnail path")
    return path


def _write_thumbnail(source: Path, target: Path, max_px: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        image.save(tmp, format="JPEG", quality=78, optimize=True)
    tmp.replace(target)


def thumbnail_path(
    config: dict[str, Any], filename: str, additional_dirs: list[Path] | None = None
) -> Path:
    source = safe_photo_path(config, filename, additional_dirs)
    if not source.exists():
        raise FileNotFoundError("Photo not found")
    target = _safe_thumbnail_path(config, source.name)
    max_px = int(config.get("thumbnail_max_px", 360))
    if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
        _write_thumbnail(source, target, max_px=max_px)
    return target


def delete_thumbnail(config: dict[str, Any], filename: str) -> None:
    try:
        target = _safe_thumbnail_path(config, filename)
        target.unlink(missing_ok=True)
    except Exception:
        return


def list_photos(
    config: dict[str, Any], limit: int | None = None, additional_dirs: list[Path] | None = None
) -> list[dict[str, Any]]:
    files_by_name: dict[str, Path] = {}
    for directory in _photo_source_dirs(config, additional_dirs):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS:
                files_by_name.setdefault(path.name, path)
    files = list(files_by_name.values())
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if limit is None:
        max_items = int(config.get("max_recent_photos", 100))
    elif limit <= 0:
        max_items = len(files)
    else:
        max_items = int(limit)
    result = []
    for path in files[:max_items]:
        stat = path.stat()
        result.append({
            "filename": path.name,
            "size": stat.st_size,
            "mtime": int(stat.st_mtime),
            "storage_location": "local" if path.parent == photo_dir(config) else "external",
            "url": f"/photos/{path.name}",
            "thumbnail_url": f"/thumbs/{path.name}?v={int(stat.st_mtime)}-{stat.st_size}",
            "download_url": f"/download/{path.name}",
        })
    return result
