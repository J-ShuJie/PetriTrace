"""Reconnect saved, visible NetworkManager Wi-Fi profiles without a password agent.

Runs independently of the camera service. Never restarts NetworkManager, disables
an interface, changes credentials, or treats lack of Internet as a Wi-Fi failure.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import time
from dataclasses import dataclass


def nmcli(*args: str, timeout: int = 10) -> str:
    result = subprocess.run(
        ["nmcli", *args], capture_output=True, text=True, timeout=timeout,
        env={**os.environ, "LC_ALL": "C"},
    )
    if result.returncode:
        # Do not copy arbitrary connection/agent output into the service log.
        raise RuntimeError(f"nmcli exited with status {result.returncode}")
    return result.stdout.strip()


@dataclass
class Retry:
    due: float
    failures: int = 0


class Recovery:
    def __init__(self, run=nmcli, clock=time.monotonic, log=print):
        self.run, self.clock, self.log = run, clock, log
        self.retries: dict[str, Retry] = {}

    def candidate(self, device: str) -> str | None:
        visible = set(self.run("-t", "--escape", "no", "-f", "SSID", "device", "wifi",
                               "list", "ifname", device, "--rescan", "no").splitlines())
        profiles = self.run("-t", "-f", "UUID,TYPE", "connection", "show")
        candidates = []
        for row in profiles.splitlines():
            uuid, kind = row.split(":", 1)
            if kind != "802-11-wireless":
                continue
            auto = self.run("-g", "connection.autoconnect", "connection", "show", "uuid", uuid)
            if auto != "yes":
                continue
            permissions = self.run("-g", "connection.permissions", "connection", "show", "uuid", uuid)
            if permissions and permissions != "--":
                continue  # User-session-only credentials may not be available to this service.
            ssid = self.run("-g", "802-11-wireless.ssid", "connection", "show", "uuid", uuid)
            if ssid not in visible:
                continue
            bound = self.run("-g", "connection.interface-name", "connection", "show", "uuid", uuid)
            if bound and bound != "--" and bound != device:
                continue
            priority = int(self.run("-g", "connection.autoconnect-priority", "connection", "show", "uuid", uuid))
            candidates.append((priority, uuid))
        return max(candidates)[1] if candidates else None

    def tick(self):
        if self.run("radio", "wifi") != "enabled":
            self.retries.clear()
            return
        devices = self.run("-t", "-f", "DEVICE,TYPE", "device", "status")
        for row in devices.splitlines():
            device, kind = row.split(":", 1)
            if kind != "wifi":
                continue
            state = int(self.run("-g", "GENERAL.STATE", "device", "show", device).split()[0])
            if state not in (30, 120):  # Leave connected, activating, unmanaged and unavailable devices alone.
                self.retries.pop(device, None)
                continue
            reason = self.run("-g", "GENERAL.REASON", "device", "show", device).lower()
            if "user-requested" in reason or "user requested" in reason:
                self.retries.pop(device, None)
                continue
            now = self.clock()
            retry = self.retries.setdefault(device, Retry(now + 90))
            if now < retry.due:
                continue
            uuid = self.candidate(device)
            if not uuid:
                retry.due = now + 60
                continue
            self.log(f"wifi-recovery: reconnecting device={device} profile={uuid}", flush=True)
            try:
                self.run("--wait", "25", "connection", "up", "uuid", uuid, "ifname", device, timeout=30)
            except (RuntimeError, subprocess.TimeoutExpired):
                retry.failures += 1
                delay = min(60 * 2 ** min(retry.failures - 1, 4), 900)
                retry.due = self.clock() + delay
                self.log(f"wifi-recovery: failed; next attempt in {delay}s", flush=True)
            else:
                self.retries.pop(device, None)
                self.log(f"wifi-recovery: connected device={device}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Read network state; do not reconnect")
    args = parser.parse_args()
    if args.check:
        print(nmcli("-f", "DEVICE,TYPE,STATE", "device", "status"))
        return
    recovery = Recovery()
    while True:
        try:
            recovery.tick()
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
            print(f"wifi-recovery: check unavailable ({type(error).__name__}); retry in 30s", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
