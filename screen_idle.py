from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping

from config_store import load_config


def wayland_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(source or os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    env.setdefault("WAYLAND_DISPLAY", "wayland-0")
    return env


def display_names(status_text: str) -> list[str]:
    names = []
    for line in status_text.splitlines():
        parts = line.strip().split()
        if parts and parts[0] not in names:
            names.append(parts[0])
    return names


def set_display_power(mode: str, *, require_output: bool = False) -> bool:
    if mode not in {"on", "off"}:
        raise ValueError(f"Unsupported display power mode: {mode}")
    env = wayland_environment()
    status = subprocess.run(
        ["wlopm"],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    outputs = display_names(status.stdout) if status.returncode == 0 else []
    dsi_outputs = [output for output in outputs if output.upper().startswith("DSI-")]
    if dsi_outputs:
        outputs = dsi_outputs
    if not outputs:
        if require_output:
            raise RuntimeError(status.stderr.strip() or "No Wayland display output found")
        return False
    for output in outputs:
        subprocess.run(
            ["wlopm", f"--{mode}", output],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    return True


def run_idle_manager() -> None:
    timeout_seconds = int(load_config().get("screen_idle_timeout_seconds", 60))
    env = wayland_environment()
    set_display_power("on", require_output=True)
    if timeout_seconds <= 0:
        while True:
            time.sleep(3600)

    script = str(Path(__file__).resolve())
    base_command = shlex.join([sys.executable, script, "--power"])
    off_command = f"{base_command} off"
    on_command = f"{base_command} on"
    os.execvpe(
        "swayidle",
        [
            "swayidle",
            "-w",
            "timeout",
            str(timeout_seconds),
            off_command,
            "resume",
            on_command,
        ],
        env,
    )


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--power":
        set_display_power(sys.argv[2])
        return
    run_idle_manager()


if __name__ == "__main__":
    main()
