from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def screenshot_dir(config: dict) -> Path:
    raw = config.get("screenshot_dir") or "~/pi-camera-screenshots"
    return Path(os.path.expanduser(str(raw))).resolve()


def safe_screenshot_path(config: dict, filename: str) -> Path:
    root = screenshot_dir(config)
    candidate = (root / filename).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError("Invalid screenshot path")
    return candidate


def _wayland_env() -> dict[str, str]:
    env = os.environ.copy()
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    runtime_dir = env.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}"
    env["XDG_RUNTIME_DIR"] = runtime_dir
    if not env.get("WAYLAND_DISPLAY"):
        runtime = Path(runtime_dir)
        displays = sorted(
            item.name for item in runtime.glob("wayland-*")
            if not item.name.endswith(".lock")
        )
        env["WAYLAND_DISPLAY"] = displays[0] if displays else "wayland-0"
    return env


def _metadata(path: Path) -> dict:
    stat = path.stat()
    return {
        "filename": path.name,
        "path": str(path),
        "size_bytes": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def list_screenshots(config: dict, limit: int = 20) -> list[dict]:
    root = screenshot_dir(config)
    if not root.exists():
        return []
    files = sorted(root.glob("*.png"), key=lambda item: item.stat().st_mtime, reverse=True)
    return [_metadata(item) for item in files[:limit]]


def latest_screenshot(config: dict) -> dict | None:
    screenshots = list_screenshots(config, limit=1)
    return screenshots[0] if screenshots else None


def capture_display(config: dict) -> dict:
    root = screenshot_dir(config)
    root.mkdir(parents=True, exist_ok=True)
    filename = datetime.now().strftime("screen_%Y-%m-%d_%H-%M-%S.png")
    path = root / filename
    timeout = float(config.get("screenshot_timeout_seconds", 10))

    grim = shutil.which("grim")
    if not grim:
        raise RuntimeError("grim is not installed; Wayland screenshots are unavailable")

    command = [grim]
    output_name = str(config.get("screenshot_output") or "").strip()
    if output_name:
        command.extend(["-o", output_name])
    command.append(str(path))

    result = subprocess.run(
        command,
        env=_wayland_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "grim failed").strip()
        raise RuntimeError(message)
    return _metadata(path)
