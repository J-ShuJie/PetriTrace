from __future__ import annotations

import csv
import io
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from history_store import colony_result_exists, photo_timestamp_from_filename, record_colony_result, record_event


class ColonyCountError(RuntimeError):
    pass


def parse_opencfu_output(output: str) -> dict[str, Any]:
    rows = list(csv.DictReader(io.StringIO(output.strip())))
    if not rows or "IsValid" not in rows[0]:
        raise ColonyCountError("OpenCFU did not return its expected CSV output")
    valid = [row for row in rows if str(row.get("IsValid", "")).strip() == "1"]
    return {"count": len(valid), "candidate_count": len(rows)}


def _json_objects(text: str):
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            yield value


def parse_mcount_output(output: str) -> dict[str, Any]:
    payload = next((item for item in _json_objects(output) if item.get("backend") == "mcount"), None)
    if payload is None or "count" not in payload:
        raise ColonyCountError("MCount did not return its expected JSON summary")
    count = payload.get("count")
    if count is not None:
        count = int(count)
    status = str(payload.get("status") or "error").lower()
    if status not in {"ok", "warning"}:
        status = "error"
    return {
        "count": count,
        "status": status,
        "duration_seconds": float(payload.get("duration_seconds") or 0.0),
        "summary": payload,
    }


def _photo_timestamp(path: Path) -> str:
    fallback = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    return photo_timestamp_from_filename(path.name, fallback) or fallback


def _opencfu_paths(config: dict[str, Any]) -> tuple[Path, Path, dict[str, str]]:
    runtime = Path(str(config.get("opencfu_runtime_root") or "")).expanduser()
    configured_command = str(config.get("opencfu_command") or "").strip()
    executable = Path(configured_command).expanduser() if configured_command else runtime / "usr" / "bin" / "opencfu"
    data_dir = runtime / "usr" / "share" / "opencfu"
    if not executable.is_file() or not data_dir.is_dir():
        raise ColonyCountError("OpenCFU runtime is not installed")
    env = dict(os.environ)
    libraries = [runtime / "usr" / "lib" / "aarch64-linux-gnu", runtime / "usr" / "lib"]
    existing = env.get("LD_LIBRARY_PATH")
    env["LD_LIBRARY_PATH"] = os.pathsep.join([*(str(path) for path in libraries), *([existing] if existing else [])])
    gdal_data = runtime / "usr" / "share" / "gdal"
    proj_data = runtime / "usr" / "share" / "proj"
    if gdal_data.is_dir():
        env["GDAL_DATA"] = str(gdal_data)
    if proj_data.is_dir():
        env["PROJ_DATA"] = str(proj_data)
    return executable, data_dir, env


def run_opencfu(path: Path, config: dict[str, Any]) -> dict[str, Any]:
    executable, data_dir, env = _opencfu_paths(config)
    timeout = max(5, int(config.get("colony_count_timeout_seconds", 180)))
    max_dimension = max(640, int(config.get("opencfu_max_dimension", 1280)))
    runtime_dir = Path(str(config.get("colony_runtime_dir") or Path(__file__).resolve().parent / "data" / "colony-runtime"))
    runtime_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    dimensions = list(dict.fromkeys([max_dimension, min(max_dimension, 1024), min(max_dimension, 800)]))
    parsed: dict[str, Any] | None = None
    used_dimension = max_dimension
    last_failure = "OpenCFU failed"
    with tempfile.TemporaryDirectory(prefix="opencfu-", dir=runtime_dir) as prepared_dir:
        prepared = Path(prepared_dir) / f"{path.stem}.jpg"
        for dimension in dimensions:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((dimension, dimension), Image.Resampling.LANCZOS)
                image.save(prepared, format="JPEG", quality=95, optimize=True)
            completed = subprocess.run(
                [str(executable), "-i", str(prepared), "-a", "-m", "auto"],
                cwd=data_dir,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            if completed.returncode != 0:
                message = completed.stderr.strip().splitlines()[-1:] or [f"exit code {completed.returncode}"]
                last_failure = f"OpenCFU failed at {dimension}px: {message[0]}"
                continue
            try:
                parsed = parse_opencfu_output(completed.stdout)
                used_dimension = dimension
                break
            except ColonyCountError as exc:
                last_failure = f"OpenCFU failed at {dimension}px: {exc}"
    if parsed is None:
        raise ColonyCountError(last_failure)
    suspect_count = max(1, int(config.get("opencfu_suspect_count", 600)))
    flags = ["suspect_high_count"] if parsed["count"] > suspect_count else []
    return {
        "backend": "opencfu",
        "status": "warning" if flags else "ok",
        "count": parsed["count"],
        "duration_seconds": round(time.monotonic() - started, 3),
        "details": {
            "candidate_count": parsed["candidate_count"],
            "flags": flags,
            "input_max_dimension": used_dimension,
            "fallback_used": used_dimension != max_dimension,
        },
    }


def _mcount_paths(config: dict[str, Any]) -> tuple[Path, Path]:
    configured_python = str(config.get("mcount_python") or "").strip()
    python = Path(configured_python).expanduser() if configured_python else Path.home() / ".local/opt/pi-camera-colony/mcount/bin/python"
    configured_script = str(config.get("mcount_script") or "").strip()
    script = Path(configured_script).expanduser() if configured_script else Path(__file__).resolve().parent / "tools" / "mcount_cli.py"
    if not python.is_file() or not script.is_file():
        raise ColonyCountError("MCount runtime is not installed")
    return python, script


def run_mcount(path: Path, config: dict[str, Any]) -> dict[str, Any]:
    python, script = _mcount_paths(config)
    timeout = max(5, min(
        int(config.get("colony_count_timeout_seconds", 180)),
        int(config.get("mcount_timeout_seconds", 30)),
    ))
    max_dimension = max(320, int(config.get("mcount_max_dimension", 400)))
    runtime_dir = Path(str(config.get("colony_runtime_dir") or Path(__file__).resolve().parent / "data" / "colony-runtime"))
    runtime_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="mcount-", dir=runtime_dir) as prepared_dir:
        prepared = Path(prepared_dir) / f"{path.stem}.png"
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            image.save(prepared, format="PNG", optimize=True)
        try:
            completed = subprocess.run(
                [
                    str(python), str(script), "--input", str(prepared),
                    "--lambda", str(config.get("mcount_lambda", 30.0)),
                    "--d", str(config.get("mcount_d", 0.5)),
                ],
                cwd=script.parent,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ColonyCountError(f"MCount exceeded its {timeout}-second resource limit") from exc
    if completed.returncode != 0:
        message = completed.stderr.strip().splitlines()[-1:] or [f"exit code {completed.returncode}"]
        raise ColonyCountError(f"MCount failed: {message[0]}")
    parsed = parse_mcount_output(completed.stdout)
    return {
        "backend": "mcount",
        "status": parsed["status"],
        "count": parsed["count"],
        "duration_seconds": round(time.monotonic() - started, 3),
        "details": {
            "summary": parsed["summary"],
            "input_max_dimension": max_dimension,
            "source": "hyu-kim/mcount",
        },
    }


BACKEND_RUNNERS = {"opencfu": run_opencfu, "mcount": run_mcount}


class ColonyCountingWorker:
    def __init__(self, config: dict[str, Any]) -> None:
        self._config = dict(config)
        self._queue: queue.Queue[tuple[Path, bool]] = queue.Queue()
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._last_error: str | None = None
        self._last_error_id: str | None = None

    def update_config(self, config: dict[str, Any]) -> None:
        with self._lock:
            self._config = dict(config)

    def _ensure_started(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="colony-counting", daemon=True)
        self._thread.start()

    def submit(self, path: Path, _capture_result: dict[str, Any] | None = None, force: bool = False) -> bool:
        path = Path(path).resolve()
        with self._lock:
            config = dict(self._config)
            if not config.get("colony_count_enabled", True) or str(path) in self._pending:
                return False
            self._pending.add(str(path))
            self._ensure_started()
        self._queue.put((path, force))
        return True

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": bool(self._thread and self._thread.is_alive()),
                "pending": len(self._pending),
                "last_error": self._last_error,
                "last_error_id": self._last_error_id,
            }

    def is_pending(self, path: Path) -> bool:
        """Return whether a photo is queued or currently being analysed."""
        resolved = str(Path(path).resolve())
        with self._lock:
            return resolved in self._pending

    def _run(self) -> None:
        while True:
            path, force = self._queue.get()
            try:
                self._analyze(path, force=force)
            finally:
                with self._lock:
                    self._pending.discard(str(path))
                self._queue.task_done()

    def _analyze(self, path: Path, force: bool) -> None:
        with self._lock:
            config = dict(self._config)
        if not path.is_file():
            return
        timestamp = _photo_timestamp(path)
        backends = config.get("colony_count_backends") or ["opencfu", "mcount"]
        last_error: str | None = None
        for backend in backends:
            backend = str(backend).strip().lower()
            runner = BACKEND_RUNNERS.get(backend)
            if runner is None or (not force and colony_result_exists(config, path.name, backend)):
                continue
            try:
                result = runner(path, config)
                record_colony_result(
                    config,
                    filename=path.name,
                    photo_timestamp=timestamp,
                    backend=backend,
                    status=str(result["status"]),
                    count=result.get("count"),
                    duration_seconds=result.get("duration_seconds"),
                    details=result.get("details") or {},
                )
            except Exception as exc:  # noqa: BLE001 - one backend must not block the other
                last_error = f"{backend}: {exc}"
                event = record_event(config, "analysis_error", {"ok": False, "filename": path.name, "message": last_error})
                with self._lock:
                    self._last_error_id = str(event["id"])
                record_colony_result(
                    config,
                    filename=path.name,
                    photo_timestamp=timestamp,
                    backend=backend,
                    status="error",
                    count=None,
                    duration_seconds=None,
                    details={"error": str(exc)},
                )
        with self._lock:
            self._last_error = last_error
