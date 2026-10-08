from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from camera_backends import CameraBackend
from hardware_status import current_hardware_status
from history_store import record_event, record_sensor_sample
from light_controller import LightController
from network_status import current_network_status
from storage import check_storage, photo_dir


def timestamp_name() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S.jpg")


class CaptureScheduler:
    def __init__(
        self,
        backend: CameraBackend,
        config: dict[str, Any],
        on_capture: Callable[[Path, dict[str, Any]], object] | None = None,
        storage_target: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.backend = backend
        self.config = config
        self.on_capture = on_capture
        self.storage_target = storage_target
        self.light = LightController(config)
        self.state_lock = threading.Lock()
        self.capture_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.state: dict[str, Any] = {
            "running": False,
            "is_capturing": False,
            "capture_count": 0,
            "last_photo": None,
            "last_error": None,
            "last_capture_started_at": None,
            "last_capture_finished_at": None,
            "started_at": None,
            "stopped_at": None,
        }

    def update_config(self, config: dict[str, Any]) -> None:
        self.config = config
        self.light.update_config(config)
        self.wake_event.set()

    def start(self) -> dict[str, Any]:
        if self.thread and self.thread.is_alive():
            with self.state_lock:
                self.state["running"] = True
            self.wake_event.set()
            return self.status()
        self.stop_event.clear()
        self.wake_event.clear()
        self.thread = threading.Thread(target=self._loop, name="capture-scheduler", daemon=True)
        with self.state_lock:
            self.state["running"] = True
            self.state["started_at"] = datetime.now().isoformat(timespec="seconds")
            self.state["stopped_at"] = None
        self.thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        self.stop_event.set()
        self.wake_event.set()
        with self.state_lock:
            self.state["running"] = False
            self.state["stopped_at"] = datetime.now().isoformat(timespec="seconds")
        return self.status()

    def forget_photo(self, filename: str) -> None:
        with self.state_lock:
            if self.state.get("last_photo") == filename:
                self.state["last_photo"] = None

    def _loop(self) -> None:
        next_capture_at = time.monotonic()
        while not self.stop_event.is_set():
            wait_for = max(0.0, next_capture_at - time.monotonic())
            if self.wake_event.wait(timeout=wait_for):
                self.wake_event.clear()
                next_capture_at = time.monotonic() + int(self.config["interval_seconds"])
                continue
            try:
                self.capture_now(reason="scheduled")
            except Exception as exc:  # noqa: BLE001 - keep scheduler alive
                with self.state_lock:
                    self.state["last_error"] = str(exc)
                    self.state["is_capturing"] = False
            interval = int(self.config["interval_seconds"])
            next_capture_at += interval
            if next_capture_at < time.monotonic():
                next_capture_at = time.monotonic() + interval
        with self.state_lock:
            self.state["running"] = False
            self.state["is_capturing"] = False

    def capture_now(self, reason: str = "manual") -> dict[str, Any]:
        if not self.capture_lock.acquire(blocking=False):
            raise RuntimeError("Camera is already capturing")
        try:
            if self.storage_target is None:
                storage = check_storage(self.config)
                target = {
                    "ready": bool(storage.get("ready")), "directory": str(photo_dir(self.config)),
                    "location": "local", "reason": "local",
                    "error": storage.get("error"),
                }
            else:
                target = self.storage_target()
            if not target.get("ready") or not target.get("directory"):
                raise RuntimeError(target.get("error") or "Storage is not ready")
            directory = Path(str(target["directory"]))
            directory.mkdir(parents=True, exist_ok=True)
            output = directory / timestamp_name()
            suffix = 1
            while output.exists():
                output = directory / timestamp_name().replace(".jpg", f"_{suffix:03d}.jpg")
                suffix += 1
            tmp = output.with_suffix(".tmp.jpg")
            with self.state_lock:
                self.state["is_capturing"] = True
                self.state["last_capture_started_at"] = datetime.now().isoformat(timespec="seconds")
                self.state["last_error"] = None
            with self.light.capture_window() as light_meta:
                meta = self.backend.capture(tmp, int(self.config["capture_timeout_ms"]))
            tmp.replace(output)
            result = {
                "ok": True, "reason": reason, "filename": output.name,
                "size": output.stat().st_size, "light": light_meta,
                "storage_location": target.get("location"),
                "storage_route_reason": target.get("reason"),
                **meta,
            }
            try:
                record_event(self.config, "photo", result)
            except Exception:
                pass
            try:
                record_sensor_sample(
                    self.config,
                    current_hardware_status(self.config),
                    photo_filename=output.name,
                )
            except Exception:
                pass
            if self.on_capture is not None:
                try:
                    self.on_capture(output, result)
                except Exception:
                    pass
            with self.state_lock:
                self.state["is_capturing"] = False
                self.state["last_capture_finished_at"] = datetime.now().isoformat(timespec="seconds")
                self.state["last_photo"] = output.name
                self.state["last_error"] = None
                self.state["capture_count"] = int(self.state.get("capture_count", 0)) + 1
            return result
        except Exception as exc:
            with self.state_lock:
                self.state["is_capturing"] = False
                self.state["last_error"] = str(exc)
            try:
                record_event(self.config, "capture_error", {"ok": False, "reason": reason, "message": str(exc)})
            except Exception:
                pass
            raise
        finally:
            self.capture_lock.release()

    def status(self, include_slow: bool = False) -> dict[str, Any]:
        with self.state_lock:
            state = dict(self.state)
        state["interval_seconds"] = int(self.config["interval_seconds"])
        state["backend"] = self.backend.name
        state["storage"] = check_storage(self.config)
        if self.storage_target is not None:
            try:
                state["capture_storage"] = self.storage_target()
            except Exception as exc:  # noqa: BLE001 - surfaced in diagnostics
                state["capture_storage"] = {"ready": False, "error": str(exc)}
        try:
            state["camera"] = self.backend.healthcheck()
        except Exception as exc:  # noqa: BLE001 - status endpoint should not fail hard
            state["camera"] = {"ready": False, "backend": self.backend.name, "error": str(exc)}
        state["light"] = self.light.status()
        if include_slow:
            state["network"] = current_network_status()
            state["hardware"] = current_hardware_status(self.config)
        return state
