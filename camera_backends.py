from __future__ import annotations

import base64
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    "2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/ASP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Aqf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IX//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QH//Z"
)


class CameraBackend:
    name = "base"

    def healthcheck(self) -> dict[str, Any]:
        raise NotImplementedError

    def capture(self, output_path: Path, timeout_ms: int) -> dict[str, Any]:
        raise NotImplementedError


class MockCameraBackend(CameraBackend):
    name = "mock"

    def healthcheck(self) -> dict[str, Any]:
        return {"ready": True, "backend": self.name, "message": "Mock camera ready"}

    def capture(self, output_path: Path, timeout_ms: int) -> dict[str, Any]:  # noqa: ARG002
        started = time.monotonic()
        output_path.write_bytes(TINY_JPEG)
        return {
            "backend": self.name,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "captured_at": datetime.now().isoformat(timespec="seconds"),
        }


class RpicamStillBackend(CameraBackend):
    name = "rpicam-still"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.autofocus_mode = str(config.get("autofocus_mode", "auto"))
        self.autofocus_range = str(config.get("autofocus_range", "full"))
        self.autofocus_window = str(config.get("autofocus_window", "0.25,0.25,0.5,0.5"))
        self.autofocus_on_capture = bool(config.get("autofocus_on_capture", True))
        self.autofocus_min_preview_ms = max(1000, int(config.get("autofocus_min_preview_ms", 3000)))

    def healthcheck(self) -> dict[str, Any]:
        proc = subprocess.run(
            ["rpicam-hello", "--list-cameras"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        return {
            "ready": proc.returncode == 0 and "Available cameras" in proc.stdout,
            "backend": self.name,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "returncode": proc.returncode,
        }

    def capture(self, output_path: Path, timeout_ms: int) -> dict[str, Any]:
        started = time.monotonic()
        preview_timeout_ms = max(timeout_ms, self.autofocus_min_preview_ms)
        command = [
            "rpicam-still",
            "-n",
            "--zsl",
            "--metadata", "-",
            "--metadata-format", "json",
            "--timeout",
            str(preview_timeout_ms),
            "--autofocus-mode",
            self.autofocus_mode,
            "--autofocus-range",
            self.autofocus_range,
            "--autofocus-window",
            self.autofocus_window,
        ]
        if self.autofocus_on_capture:
            command.append("--autofocus-on-capture")
        command.extend(["-o", str(output_path)])
        recovery_errors = []
        for attempt in range(2):
            proc = subprocess.run(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=max(20, preview_timeout_ms / 1000 + 20),
            )
            error = proc.stderr or proc.stdout or ""
            startup_pipe_failure = (
                proc.returncode != 0
                and "Failed to start streaming: Broken pipe" in error
                and "failed to start camera" in error
            )
            if attempt == 0 and startup_pipe_failure:
                # subprocess.run has waited for the failed process to exit and
                # release its camera handles. Retry this capture once, keeping
                # the original diagnostic in the successful capture metadata.
                recovery_errors.append(error.strip())
                output_path.unlink(missing_ok=True)
                time.sleep(1)
                continue
            break
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "rpicam-still failed").strip())
        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise RuntimeError("camera produced an empty file")
        try:
            metadata = json.loads(proc.stdout or "{}")
        except (ValueError, TypeError):
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            "backend": self.name,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "camera_metadata": metadata,
            "recovery_errors": recovery_errors,
            "autofocus": {
                "mode": self.autofocus_mode,
                "range": self.autofocus_range,
                "window": self.autofocus_window,
                "on_capture": self.autofocus_on_capture,
                "preview_ms": preview_timeout_ms,
            },
            "stderr": proc.stderr.strip(),
        }


def create_backend(config: dict[str, Any]) -> CameraBackend:
    if config.get("mock_camera"):
        return MockCameraBackend()
    return RpicamStillBackend(config)
