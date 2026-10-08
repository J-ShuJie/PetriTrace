from __future__ import annotations

import glob
import json
import os
import threading
import time
from typing import Any

try:
    import serial  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional on non-Pi development hosts
    serial = None

try:
    import select
    import termios
except Exception:  # pragma: no cover - Windows/mock development hosts
    select = None
    termios = None

DEFAULT_PORT_CANDIDATES = [
    "/dev/ttyACM0",
]

_SERIAL_LOCK = threading.Lock()

BAUD_CONSTANTS = {
    9600: "B9600",
    19200: "B19200",
    38400: "B38400",
    57600: "B57600",
    115200: "B115200",
}


class PicoProtocolError(RuntimeError):
    pass


def _candidate_ports(config: dict[str, Any]) -> list[str]:
    configured = str(config.get("pico_serial_port") or "").strip()
    ports: list[str] = []
    if configured:
        ports.append(configured)
    ports.extend(DEFAULT_PORT_CANDIDATES)
    ports.extend(sorted(glob.glob("/dev/serial/by-id/*MicroPython*")))
    ports.extend(sorted(glob.glob("/dev/ttyACM*")))
    result: list[str] = []
    for port in ports:
        if port and port not in result:
            result.append(port)
    return result


def discover_pico_port(config: dict[str, Any]) -> str | None:
    for port in _candidate_ports(config):
        if os.path.exists(port):
            return port
    return None


def _serial_runtime_available() -> bool:
    return serial is not None or (select is not None and termios is not None)


def pico_available(config: dict[str, Any]) -> bool:
    return bool(config.get("pico_enabled", True)) and _serial_runtime_available() and discover_pico_port(config) is not None


def _matches_response(data: Any) -> bool:
    return isinstance(data, dict) and ("ok" in data or data.get("type") in {"status", "pong", "error"})


class PicoBridge:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.baud = int(config.get("pico_baud", 115200))
        self.timeout = float(config.get("pico_timeout_seconds", 2.0))

    @property
    def port(self) -> str | None:
        return discover_pico_port(self.config)

    def available(self) -> bool:
        return pico_available(self.config)

    def request(self, payload: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        if not self.config.get("pico_enabled", True):
            raise PicoProtocolError("Pico bridge is disabled")
        port = self.port
        if not port:
            raise PicoProtocolError("Pico serial device was not found")
        if not _serial_runtime_available():
            raise PicoProtocolError("No serial runtime is available")

        timeout = self.timeout if timeout is None else timeout
        encoded = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        with _SERIAL_LOCK:
            if serial is not None:
                return self._request_pyserial(port, encoded, timeout)
            return self._request_termios(port, encoded, timeout)

    def _handle_line(self, line: str, seen_lines: list[str]) -> dict[str, Any] | None:
        if not line:
            return None
        seen_lines.append(line)
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not _matches_response(data):
            return None
        if data.get("type") == "error" or data.get("ok") is False:
            raise PicoProtocolError(str(data.get("error") or data))
        return data

    def _request_pyserial(self, port: str, encoded: bytes, timeout: float) -> dict[str, Any]:
        seen_lines: list[str] = []
        deadline = time.monotonic() + timeout
        try:
            with serial.Serial(port, self.baud, timeout=0.1, write_timeout=1.0) as handle:  # type: ignore[union-attr]
                time.sleep(float(self.config.get("pico_open_delay_seconds", 0.05)))
                try:
                    handle.reset_input_buffer()
                except Exception:
                    pass
                handle.write(encoded)
                handle.flush()
                while time.monotonic() < deadline:
                    raw = handle.readline()
                    if not raw:
                        continue
                    data = self._handle_line(raw.decode("utf-8", "replace").strip(), seen_lines)
                    if data is not None:
                        return data
        except PicoProtocolError:
            raise
        except Exception as exc:  # noqa: BLE001 - surfaced in UI status
            raise PicoProtocolError(str(exc)) from exc
        raise self._timeout_error(seen_lines)

    def _request_termios(self, port: str, encoded: bytes, timeout: float) -> dict[str, Any]:
        if select is None or termios is None:
            raise PicoProtocolError("termios/select are not available")
        seen_lines: list[str] = []
        deadline = time.monotonic() + timeout
        buffer = b""
        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            self._configure_fd(fd)
            self._drain_fd(fd)
            os.write(fd, encoded)
            while time.monotonic() < deadline:
                ready, _, _ = select.select([fd], [], [], 0.1)
                if not ready:
                    continue
                try:
                    chunk = os.read(fd, 4096)
                except BlockingIOError:
                    continue
                if not chunk:
                    continue
                buffer += chunk
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)
                    data = self._handle_line(raw.decode("utf-8", "replace").strip(), seen_lines)
                    if data is not None:
                        return data
        except PicoProtocolError:
            raise
        except Exception as exc:  # noqa: BLE001 - surfaced in UI status
            raise PicoProtocolError(str(exc)) from exc
        finally:
            os.close(fd)
        raise self._timeout_error(seen_lines)

    def _configure_fd(self, fd: int) -> None:
        if termios is None:
            return
        attrs = termios.tcgetattr(fd)
        baud_name = BAUD_CONSTANTS.get(self.baud, "B115200")
        baud_value = getattr(termios, baud_name)
        attrs[0] = attrs[0] & ~(getattr(termios, "IXON", 0) | getattr(termios, "IXOFF", 0) | getattr(termios, "ICRNL", 0))
        attrs[1] = attrs[1] & ~getattr(termios, "OPOST", 0)
        attrs[2] = attrs[2] | getattr(termios, "CLOCAL", 0) | getattr(termios, "CREAD", 0)
        attrs[3] = attrs[3] & ~(getattr(termios, "ECHO", 0) | getattr(termios, "ICANON", 0))
        attrs[4] = baud_value
        attrs[5] = baud_value
        termios.tcsetattr(fd, termios.TCSANOW, attrs)

    def _drain_fd(self, fd: int) -> None:
        if select is None:
            return
        deadline = time.monotonic() + 0.2
        while time.monotonic() < deadline:
            ready, _, _ = select.select([fd], [], [], 0.02)
            if not ready:
                continue
            try:
                os.read(fd, 4096)
            except BlockingIOError:
                return

    def _timeout_error(self, seen_lines: list[str]) -> PicoProtocolError:
        tail = "; ".join(seen_lines[-3:]) if seen_lines else "no serial response"
        return PicoProtocolError(f"No Pico JSON response before timeout: {tail}")

    def status(self) -> dict[str, Any]:
        return self.request({"cmd": "status"})

    def ping(self) -> dict[str, Any]:
        return self.request({"cmd": "ping"})

    def set_light(self, on: bool, brightness: float, color: str) -> dict[str, Any]:
        return self.request(
            {
                "cmd": "light",
                "mode": "on" if on else "off",
                "brightness": brightness,
                "color": color,
            }
        )