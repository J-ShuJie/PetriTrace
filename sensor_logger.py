from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any

from hardware_status import current_hardware_status
from history_store import record_sensor_sample


class SensorLogger:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.state_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.state: dict[str, Any] = {
            "running": False,
            "sample_count": 0,
            "last_sample_at": None,
            "last_error": None,
            "started_at": None,
            "stopped_at": None,
        }

    def update_config(self, config: dict[str, Any]) -> None:
        self.config = config
        self.wake_event.set()

    def start(self) -> dict[str, Any]:
        if self.thread and self.thread.is_alive():
            with self.state_lock:
                self.state["running"] = True
            self.wake_event.set()
            return self.status()
        self.stop_event.clear()
        self.wake_event.clear()
        self.thread = threading.Thread(target=self._loop, name="sensor-logger", daemon=True)
        with self.state_lock:
            self.state["running"] = True
            self.state["started_at"] = datetime.now().isoformat(timespec="seconds")
            self.state["stopped_at"] = None
            self.state["last_error"] = None
        self.thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        self.stop_event.set()
        self.wake_event.set()
        with self.state_lock:
            self.state["running"] = False
            self.state["stopped_at"] = datetime.now().isoformat(timespec="seconds")
        return self.status()

    def _loop(self) -> None:
        next_sample_at = time.monotonic()
        while not self.stop_event.is_set():
            wait_for = max(0.0, next_sample_at - time.monotonic())
            if self.wake_event.wait(timeout=wait_for):
                self.wake_event.clear()
                next_sample_at = time.monotonic() + self.interval_seconds()
                continue
            try:
                self.sample_once()
            except Exception as exc:  # noqa: BLE001 - keep logger alive
                with self.state_lock:
                    self.state["last_error"] = str(exc)
            interval = self.interval_seconds()
            next_sample_at += interval
            if next_sample_at < time.monotonic():
                next_sample_at = time.monotonic() + interval
        with self.state_lock:
            self.state["running"] = False

    def interval_seconds(self) -> int:
        return max(1, int(self.config.get("sensor_log_interval_seconds", 10)))

    def sample_once(self) -> dict[str, Any]:
        hardware = current_hardware_status(self.config)
        row = record_sensor_sample(self.config, hardware)
        with self.state_lock:
            self.state["sample_count"] = int(self.state.get("sample_count", 0)) + 1
            self.state["last_sample_at"] = row["timestamp"]
            self.state["last_error"] = None
        return row

    def status(self) -> dict[str, Any]:
        with self.state_lock:
            state = dict(self.state)
        state["interval_seconds"] = self.interval_seconds()
        return state