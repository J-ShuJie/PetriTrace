from __future__ import annotations

import shutil
import subprocess
import time
from typing import Any

_LAST_COUNTERS: dict[str, tuple[float, int, int]] = {}


def run_text(command: list[str], timeout: float = 2.0) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def first_ipv4(values: list[str], prefix: str | None = None) -> str | None:
    for value in values:
        if "." not in value:
            continue
        if prefix and not value.startswith(prefix):
            continue
        return value
    return None


def read_int(path: str) -> int | None:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return None


def interface_rates(interface: str | None) -> dict[str, float | None]:
    if not interface:
        return {"download_kbps": None, "upload_kbps": None}
    rx = read_int(f"/sys/class/net/{interface}/statistics/rx_bytes")
    tx = read_int(f"/sys/class/net/{interface}/statistics/tx_bytes")
    if rx is None or tx is None:
        return {"download_kbps": None, "upload_kbps": None}

    now = time.monotonic()
    previous = _LAST_COUNTERS.get(interface)
    _LAST_COUNTERS[interface] = (now, rx, tx)
    if not previous:
        return {"download_kbps": None, "upload_kbps": None}

    previous_time, previous_rx, previous_tx = previous
    elapsed = max(0.001, now - previous_time)
    download_kbps = max(0.0, (rx - previous_rx) * 8 / elapsed / 1000)
    upload_kbps = max(0.0, (tx - previous_tx) * 8 / elapsed / 1000)
    return {"download_kbps": download_kbps, "upload_kbps": upload_kbps}


def current_network_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "interface": None,
        "wifi_ssid": None,
        "wifi_signal": None,
        "wifi_security": None,
        "download_kbps": None,
        "upload_kbps": None,
        "lan_ipv4": None,
        "tailscale_ipv4": None,
    }

    if shutil.which("nmcli"):
        active = run_text(["nmcli", "-t", "-f", "NAME,DEVICE,TYPE", "connection", "show", "--active"])
        for line in active.splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[1] == "wlan0" and parts[2] == "802-11-wireless":
                status["wifi_ssid"] = parts[0] or None
                status["interface"] = parts[1] or None
                break

        wifi_rows = run_text(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "ifname", "wlan0"])
        for line in wifi_rows.splitlines():
            parts = line.split(":")
            if len(parts) >= 4 and parts[0] == "*":
                status["wifi_ssid"] = parts[1] or status["wifi_ssid"]
                status["wifi_signal"] = parts[2] or None
                status["wifi_security"] = parts[3] or None
                break

    host_ips = run_text(["hostname", "-I"]).split()
    status["tailscale_ipv4"] = first_ipv4(host_ips, "100.")
    status["lan_ipv4"] = first_ipv4([ip for ip in host_ips if not ip.startswith("100.")])

    if shutil.which("tailscale"):
        tailscale_ip = run_text(["tailscale", "ip", "--4"])
        if tailscale_ip:
            status["tailscale_ipv4"] = tailscale_ip.splitlines()[0]

    status.update(interface_rates(status["interface"]))
    status["ready"] = bool(status["wifi_ssid"] or status["lan_ipv4"] or status["tailscale_ipv4"])
    return status
