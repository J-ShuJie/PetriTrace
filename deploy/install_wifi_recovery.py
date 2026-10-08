"""Install the network recovery worker as root-owned files, without restarting Wi-Fi."""
import os
from pathlib import Path
import shutil
import subprocess
import time


UNIT = """[Unit]
Description=PetriTrace saved Wi-Fi connection recovery
After=NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/lib/petritrace/wifi_recovery.py
Restart=on-failure
RestartSec=30
UMask=0077
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""


def install_file(path: Path, data: bytes):
    if path.is_file() and path.read_bytes() == data:
        return
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + f".backup-{time.time_ns()}"))
    temporary = path.with_suffix(".new")
    temporary.write_bytes(data)
    temporary.chmod(0o644)
    os.chown(temporary, 0, 0)
    temporary.replace(path)


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run this installer with sudo.")
    subprocess.run(["nmcli", "--version"], check=True)
    target = Path("/usr/local/lib/petritrace")
    target.mkdir(parents=True, exist_ok=True)
    os.chown(target, 0, 0)
    target.chmod(0o755)
    install_file(target / "wifi_recovery.py", Path(__file__).with_name("wifi_recovery.py").read_bytes())
    install_file(Path("/etc/systemd/system/petritrace-wifi-recovery.service"), UNIT.encode())
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "petritrace-wifi-recovery.service"], check=True)
    subprocess.run(["systemctl", "restart", "petritrace-wifi-recovery.service"], check=True)
    print("Wi-Fi recovery installed. First reconnect after 90 seconds if disconnected.")


if __name__ == "__main__":
    main()
