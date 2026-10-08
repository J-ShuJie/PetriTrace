from __future__ import annotations

import math
import shutil
import subprocess
from datetime import datetime
from typing import Any

from pico_bridge import PicoBridge


def _run_text(command: list[str], timeout: float = 2.0) -> str:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _parse_temp(raw: str) -> float | None:
    if "=" not in raw:
        return None
    value = raw.split("=", 1)[1].replace("'C", "").strip()
    try:
        return round(float(value), 1)
    except ValueError:
        return None


def _parse_pmic(raw: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        name = line.split()[0]
        number = line.rsplit("=", 1)[-1].rstrip("AV")
        try:
            values[name] = float(number)
        except ValueError:
            continue
    return values


def _mock_sensor_values() -> list[dict[str, Any]]:
    phase = datetime.now().second / 60.0 * math.tau
    return [
        {
            "id": "i2c1_0x40",
            "name": "I2C1 0x40",
            "kind": "HTU21D/SHT21/SI7021-like",
            "temperature_c": round(25.2 + math.sin(phase) * 0.4, 1),
            "humidity_percent": round(49.0 + math.cos(phase) * 1.2, 1),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "status": "ok",
        },
        {
            "id": "i2c2_0x38",
            "name": "I2C2 0x38",
            "kind": "AHT20/DHT20-like",
            "temperature_c": round(24.8 + math.sin(phase + 0.5) * 0.3, 1),
            "humidity_percent": round(50.2 + math.cos(phase + 0.5) * 1.0, 1),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "status": "ok",
        },
    ]


def _normalize_sensors(raw_sensors: object) -> list[dict[str, Any]]:
    if not isinstance(raw_sensors, list):
        return []
    sensors: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_sensors):
        if not isinstance(raw, dict):
            continue
        sensor = {
            "id": str(raw.get("id") or f"sensor_{index + 1}"),
            "name": str(raw.get("name") or f"Sensor {index + 1}"),
            "kind": str(raw.get("kind") or "unknown"),
            "updated_at": raw.get("updated_at") or datetime.now().isoformat(timespec="seconds"),
            "status": str(raw.get("status") or "ok"),
        }
        try:
            sensor["temperature_c"] = round(float(raw["temperature_c"]), 1)
            sensor["humidity_percent"] = round(float(raw["humidity_percent"]), 1)
        except (KeyError, TypeError, ValueError):
            sensor["status"] = "error"
            sensor["error"] = raw.get("error") or "missing reading"
        sensors.append(sensor)
    return sensors


def _sensor_delta(config: dict[str, Any], sensors: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [sensor for sensor in sensors if sensor.get("status") == "ok"]
    if len(ok) < 2:
        return {"ready": False, "warning": False, "message": "Need two sensors"}

    a, b = ok[0], ok[1]
    temp_a = float(a["temperature_c"])
    temp_b = float(b["temperature_c"])
    hum_a = float(a["humidity_percent"])
    hum_b = float(b["humidity_percent"])
    temp_delta = abs(temp_a - temp_b)
    hum_delta = abs(hum_a - hum_b)

    def relative_delta(delta: float, left: float, right: float) -> float:
        base = max(0.001, (abs(left) + abs(right)) / 2)
        return delta / base * 100

    temp_relative = relative_delta(temp_delta, temp_a, temp_b)
    hum_relative = relative_delta(hum_delta, hum_a, hum_b)
    temp_warn = temp_delta >= float(config.get("sensor_temp_delta_c_warn", 5.0)) or temp_relative >= float(config.get("sensor_temp_delta_percent_warn", 30.0))
    hum_warn = hum_delta >= float(config.get("sensor_humidity_delta_warn", 20.0)) or hum_relative >= float(config.get("sensor_humidity_delta_percent_warn", 30.0))
    return {
        "ready": True,
        "warning": temp_warn or hum_warn,
        "temperature_delta_c": round(temp_delta, 2),
        "temperature_delta_percent": round(temp_relative, 1),
        "humidity_delta_percent_points": round(hum_delta, 2),
        "humidity_delta_percent": round(hum_relative, 1),
    }


def current_power_status() -> dict[str, Any]:
    if not shutil.which("vcgencmd"):
        return {
            "source": "mock",
            "ready": True,
            "throttled": "0x0",
            "under_voltage": False,
            "cpu_temp_c": 46.0,
            "ext5v_v": 5.10,
        }

    throttled_raw = _run_text(["vcgencmd", "get_throttled"])
    temp_raw = _run_text(["vcgencmd", "measure_temp"])
    pmic_raw = _run_text(["vcgencmd", "pmic_read_adc"], timeout=3.0)
    pmic = _parse_pmic(pmic_raw)
    throttled = throttled_raw.split("=", 1)[-1] if "=" in throttled_raw else None
    try:
        throttled_int = int(str(throttled), 16)
    except (TypeError, ValueError):
        throttled_int = 0
    return {
        "source": "vcgencmd",
        "ready": bool(throttled_raw or temp_raw or pmic),
        "throttled": throttled,
        "under_voltage": bool(throttled_int & 0x1 or throttled_int & 0x10000),
        "cpu_temp_c": _parse_temp(temp_raw),
        "ext5v_v": pmic.get("EXT5V_V"),
        "hdmi_v": pmic.get("HDMI_V"),
    }


def current_sensor_status(config: dict[str, Any]) -> dict[str, Any]:
    bridge = PicoBridge(config)
    if bridge.available():
        try:
            response = bridge.status()
            sensors = _normalize_sensors(response.get("sensors"))
            return {
                "source": "pico",
                "ready": bool(sensors),
                "sensors": sensors,
                "delta": _sensor_delta(config, sensors),
                "raw_light": response.get("light"),
            }
        except Exception as exc:  # noqa: BLE001 - surfaced in UI status
            return {
                "source": "pico-error",
                "ready": False,
                "error": str(exc),
                "sensors": [],
                "delta": {"ready": False, "warning": False, "message": str(exc)},
            }

    sensors = _mock_sensor_values()
    return {
        "source": "mock",
        "ready": True,
        "sensors": sensors,
        "delta": _sensor_delta(config, sensors),
    }


def current_hardware_status(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "sensors": current_sensor_status(config),
        "power": current_power_status(),
    }