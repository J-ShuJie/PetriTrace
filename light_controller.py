from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from pico_bridge import PicoBridge

VALID_LIGHT_MODES = {"off", "on"}


class LightController:
    """State holder for the LED strip.

    The UI only exposes off/on. When the mode is off, capture uses a temporary
    light window so dark enclosure photos still have illumination.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.bridge = PicoBridge(config)
        self.mode = self._clean_mode(config.get("light_mode", "off"))
        self.effective_on = self.mode == "on"
        self.last_changed_at: str | None = None
        self.last_error: str | None = None
        self.backend = "pico" if self.bridge.available() else "mock"
        self._apply_output(self.effective_on)

    @staticmethod
    def _clean_mode(mode: object) -> str:
        value = str(mode or "off").strip().lower()
        return value if value in VALID_LIGHT_MODES else "off"

    def update_config(self, config: dict[str, Any]) -> None:
        self.config = config
        self.bridge = PicoBridge(config)
        self.set_mode(config.get("light_mode", self.mode))

    def set_mode(self, mode: object) -> dict[str, Any]:
        clean = self._clean_mode(mode)
        self.mode = clean
        self._apply_output(clean == "on")
        return self.status()

    def _apply_output(self, on: bool) -> None:
        self.effective_on = on
        self.last_changed_at = datetime.now().isoformat(timespec="seconds")
        self.last_error = None
        self.backend = "mock"

        if not self.bridge.available():
            return

        self.backend = "pico"
        try:
            response = self.bridge.set_light(
                on,
                float(self.config.get("light_brightness", 0.35)),
                str(self.config.get("light_color", "#ffffff")),
            )
            light = response.get("light") if isinstance(response, dict) else None
            if isinstance(light, dict):
                self.effective_on = bool(light.get("effective_on", on))
        except Exception as exc:  # noqa: BLE001 - surfaced in UI status
            self.backend = "pico-error"
            self.last_error = str(exc)

    @contextmanager
    def capture_window(self) -> Iterator[dict[str, Any]]:
        meta = {"mode": self.mode, "temporary_light": False}
        if self.mode == "on":
            yield meta
            return

        pre_seconds = max(0.0, float(self.config.get("light_pre_seconds", 1.0)))
        post_seconds = max(0.0, float(self.config.get("light_post_seconds", 1.0)))
        self._apply_output(True)
        meta.update({"temporary_light": True, "pre_seconds": pre_seconds, "post_seconds": post_seconds})
        if pre_seconds:
            time.sleep(pre_seconds)
        try:
            yield meta
            if post_seconds:
                time.sleep(post_seconds)
        finally:
            self._apply_output(False)

    def status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "effective_on": self.effective_on,
            "backend": self.backend,
            "last_changed_at": self.last_changed_at,
            "last_error": self.last_error,
            "pre_seconds": float(self.config.get("light_pre_seconds", 1.0)),
            "post_seconds": float(self.config.get("light_post_seconds", 1.0)),
            "brightness": float(self.config.get("light_brightness", 0.35)),
            "color": self.config.get("light_color", "#ffffff"),
        }