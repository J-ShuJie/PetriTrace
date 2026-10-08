#!/usr/bin/env bash
set -Eeuo pipefail

readonly EXIT_UNSUPPORTED_ARCH=20
readonly EXIT_UNSUPPORTED_OS=21
readonly EXIT_DISK_SPACE=22
readonly EXIT_SUDO_REQUIRED=23
readonly EXIT_INTEGRITY=24
readonly EXIT_DEPENDENCY=25
readonly EXIT_SERVICE=26
readonly EXIT_HEALTH=27
readonly EXIT_HARDWARE_ACCESS=28
readonly EXIT_DESKTOP_REQUIRED=29
readonly EXIT_USAGE=64

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
PACKAGE_VERSION=""
APP_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/pi-camera-control"
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/pi-camera-control"
PHOTO_DIR="$HOME/pi-camera-photos"
PHOTO_DIR_EXPLICIT=0
RUNTIME_ROOT="$HOME/.local/opt/pi-camera-colony"
PORT=5000
ENABLE_KIOSK=1
UI_LANGUAGE="en"
PICO_MODE="auto"
TAILSCALE_MODE="skip"
PREFLIGHT_ONLY=0
SKIP_SYSTEM_PACKAGES=0
SUDO_AUTH="noninteractive"
SUDO_READY=0
CURRENT_USER="$(id -un)"

usage() {
  cat <<'EOF'
Usage: install_pi.sh [options]

Installs an extracted Pi Camera Control release for the current SSH user.
Repeated execution with the same release is safe.

Options:
  --source DIR                 Extracted release root (default: script parent)
  --version VERSION            Override manifest packageVersion
  --app-root DIR               Versioned application root
  --state-root DIR             Persistent config/database root
  --photo-dir DIR              Persistent original-photo directory
  --runtime-root DIR           Separate colony-analysis runtimes
  --pico-mode MODE            auto or skip (default: auto)
  --ui-language LANG          Initial web language: en, zh, de
  --port PORT                  Web service port (default: 5000)
  --enable-kiosk               Install touchscreen kiosk (default)
  --disable-kiosk              Do not install/enable touchscreen components
  --tailscale MODE             skip or install (default: skip)
  --preflight-only             Validate target and privileges, change nothing
  --skip-system-packages       Development/test only; do not run apt
  --sudo-auth MODE             noninteractive or stdin (default: noninteractive)
  -h, --help                   Show this help

Tailscale is never bundled. MODE=install explicitly downloads its vendor
installer. MODE=skip is a complete, successful LAN-only deployment.
EOF
}

while (($#)); do
  case "$1" in
    --source) SOURCE_DIR="$2"; shift 2 ;;
    --version) PACKAGE_VERSION="$2"; shift 2 ;;
    --app-root) APP_ROOT="$2"; shift 2 ;;
    --state-root) STATE_ROOT="$2"; shift 2 ;;
    --photo-dir) PHOTO_DIR="$2"; PHOTO_DIR_EXPLICIT=1; shift 2 ;;
    --runtime-root) RUNTIME_ROOT="$2"; shift 2 ;;
    --pico-mode) PICO_MODE="$2"; shift 2 ;;
    --ui-language) UI_LANGUAGE="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --enable-kiosk) ENABLE_KIOSK=1; shift ;;
    --disable-kiosk) ENABLE_KIOSK=0; shift ;;
    --tailscale) TAILSCALE_MODE="$2"; shift 2 ;;
    --preflight-only) PREFLIGHT_ONLY=1; shift ;;
    --skip-system-packages) SKIP_SYSTEM_PACKAGES=1; shift ;;
    --sudo-auth) SUDO_AUTH="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit "$EXIT_USAGE" ;;
  esac
done

stage() {
  printf 'PICAMERA_STAGE=%s\n' "$1"
}

fail() {
  local code="$1"
  shift
  printf 'PICAMERA_ERROR code=%s message=%s\n' "$code" "$*" >&2
  exit "$code"
}

on_error() {
  local exit_code=$?
  local line_no=$1
  printf 'PICAMERA_ERROR code=%s line=%s message=installer-command-failed\n' "$exit_code" "$line_no" >&2
  exit "$exit_code"
}
trap 'on_error $LINENO' ERR

[[ "$PORT" =~ ^[0-9]+$ ]] && ((PORT >= 1 && PORT <= 65535)) \
  || fail "$EXIT_USAGE" "invalid-port"
[[ "$TAILSCALE_MODE" == "skip" || "$TAILSCALE_MODE" == "install" ]] \
  || fail "$EXIT_USAGE" "invalid-tailscale-mode"
[[ "$SUDO_AUTH" == "noninteractive" || "$SUDO_AUTH" == "stdin" ]] \
  || fail "$EXIT_USAGE" "invalid-sudo-auth-mode"

[[ "$PICO_MODE" == "auto" || "$PICO_MODE" == "skip" ]] || fail "$EXIT_USAGE" "invalid-pico-mode"
[[ "$UI_LANGUAGE" =~ ^(en|zh|de)$ ]] || fail "$EXIT_USAGE" "invalid-ui-language"

for managed_root in "$APP_ROOT" "$STATE_ROOT" "$RUNTIME_ROOT"; do
  case "$managed_root" in
    "$HOME"|/|"") fail "$EXIT_USAGE" "unsafe-managed-root" ;;
    "$HOME"/*) ;;
    *) fail "$EXIT_USAGE" "managed-roots-must-be-under-home" ;;
  esac
done

SOURCE_DIR="$(cd -- "$SOURCE_DIR" && pwd -P)"
MANIFEST="$SOURCE_DIR/release-manifest.json"
[[ -f "$MANIFEST" ]] || fail "$EXIT_INTEGRITY" "release-manifest-not-found"

stage preflight
arch="$(uname -m)"
case "$arch" in
  aarch64|arm64) ;;
  *) fail "$EXIT_UNSUPPORTED_ARCH" "unsupported-architecture:$arch" ;;
esac

[[ -r /etc/os-release ]] || fail "$EXIT_UNSUPPORTED_OS" "os-release-not-found"
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in
  debian|raspbian) ;;
  *) fail "$EXIT_UNSUPPORTED_OS" "unsupported-operating-system:${ID:-unknown}" ;;
esac

command -v python3 >/dev/null 2>&1 || fail "$EXIT_DEPENDENCY" "python3-not-found"

read_manifest_value() {
  python3 - "$MANIFEST" "$1" <<'PY'
import json
import sys

value = json.load(open(sys.argv[1], encoding="utf-8"))
for part in sys.argv[2].split("."):
    value = value[part]
print(value)
PY
}

if [[ -z "$PACKAGE_VERSION" ]]; then
  PACKAGE_VERSION="$(read_manifest_value packageVersion)"
fi
[[ "$PACKAGE_VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z._+-]*$ ]] \
  || fail "$EXIT_INTEGRITY" "invalid-package-version"

minimum_free_mib="$(read_manifest_value target.minimumFreeSpaceMiB)"
available_kib="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')"
if ((available_kib < minimum_free_mib * 1024)); then
  fail "$EXIT_DISK_SPACE" "insufficient-free-space"
fi

stage verify-payload
python3 - "$MANIFEST" "$SOURCE_DIR" <<'PY' || exit "$EXIT_INTEGRITY"
import hashlib
import json
import pathlib
import sys

manifest_path = pathlib.Path(sys.argv[1])
source = pathlib.Path(sys.argv[2]).resolve()
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("schemaVersion") != 1:
    raise SystemExit("unsupported manifest schema")
if manifest.get("installScript") != "deploy/install_pi.sh":
    raise SystemExit("unexpected install script")
files = manifest.get("files")
if not isinstance(files, list) or not files:
    raise SystemExit("release manifest has no files; run scripts/build_release.ps1")
seen = set()
for item in files:
    relative = item.get("path", "")
    if not relative or "\\" in relative or relative.startswith("/"):
        raise SystemExit(f"invalid release path: {relative!r}")
    candidate = (source / relative).resolve()
    if source not in candidate.parents:
        raise SystemExit(f"release path escapes root: {relative}")
    if relative in seen or not candidate.is_file():
        raise SystemExit(f"missing or duplicate release file: {relative}")
    seen.add(relative)
    data = candidate.read_bytes()
    if len(data) != int(item.get("size", -1)):
        raise SystemExit(f"size mismatch: {relative}")
    if hashlib.sha256(data).hexdigest() != item.get("sha256"):
        raise SystemExit(f"SHA-256 mismatch: {relative}")
PY

# Check access before modifying the existing installation. Group changes require
# a new login/reboot to reach the user systemd manager, so do not silently add
# groups and then report hardware-ready in the same SSH session.
for hardware_group in dialout video render; do
  if getent group "$hardware_group" >/dev/null 2>&1; then
    case " $(id -nG) " in
      *" $hardware_group "*) ;;
      *) fail "$EXIT_HARDWARE_ACCESS" "missing-hardware-group:$hardware_group; add-the-user-to-this-group-and-reboot" ;;
    esac
  fi
done
if ((ENABLE_KIOSK)) && ! command -v labwc >/dev/null 2>&1; then
  fail "$EXIT_DESKTOP_REQUIRED" "kiosk-requires-labwc-desktop; use-Raspberry-Pi-OS-Desktop-or-disable-kiosk"
fi

required_packages=(python3-venv python3-pip curl ca-certificates util-linux udisks2 rpicam-apps opencfu network-manager)
if ((ENABLE_KIOSK)); then
  required_packages+=(chromium swayidle wlopm grim)
fi

packages_to_install=()
for package in "${required_packages[@]}"; do
  dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -qx 'install ok installed' \
    || packages_to_install+=("$package")
done

ensure_sudo() {
  if ((SUDO_READY)); then
    return
  fi
  if sudo -n true >/dev/null 2>&1; then
    SUDO_READY=1
    return
  fi
  if [[ "$SUDO_AUTH" == "stdin" ]]; then
    # The Windows SSH session writes one password line directly to standard
    # input. It never appears in argv, environment variables or log output.
    if sudo -S -p 'PICAMERA_SUDO_PROMPT password-required\n' -v; then
      SUDO_READY=1
      return
    fi
  fi
  fail "$EXIT_SUDO_REQUIRED" "sudo-auth-required"
}

if ((SKIP_SYSTEM_PACKAGES == 0)); then
  ensure_sudo
fi

printf 'PICAMERA_PREFLIGHT arch=%s os=%s version=%s kiosk=%s tailscale=%s\n' \
  "$arch" "${ID:-unknown}" "$PACKAGE_VERSION" "$ENABLE_KIOSK" "$TAILSCALE_MODE"

if ((PREFLIGHT_ONLY)); then
  stage preflight-complete
  exit 0
fi

exec 9>"${TMPDIR:-/tmp}/pi-camera-control-install-${UID}.lock"
flock -n 9 || fail "$EXIT_SERVICE" "another-install-is-running"

if ((${#packages_to_install[@]} > 0)) && ((SKIP_SYSTEM_PACKAGES == 0)); then
  stage install-system-packages
  sudo -n apt-get update
  sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    "${packages_to_install[@]}"
fi

if ((ENABLE_KIOSK)) && ((SKIP_SYSTEM_PACKAGES == 0)); then
  stage configure-desktop-login
  sudo -n python3 "$SOURCE_DIR/deploy/configure_desktop.py" --user "$CURRENT_USER"
  sudo -n systemctl set-default graphical.target
  sudo -n systemctl enable lightdm.service
fi

if ((SKIP_SYSTEM_PACKAGES == 0)); then
  stage configure-wifi-recovery
  sudo -n python3 "$SOURCE_DIR/deploy/install_wifi_recovery.py"
fi

# Finish privileged work before potentially long Python downloads expire sudo.
if ((SUDO_READY)); then
  sudo -n loginctl enable-linger "$CURRENT_USER"
fi
if [[ "$TAILSCALE_MODE" == "install" ]]; then
  stage install-tailscale-optional
  # Invoke the helper through this shell's sudo ticket. A child shell otherwise
  # may not share a no-TTY sudo timestamp. Optional failure must not undo LAN setup.
  if ! sudo -n bash "$SOURCE_DIR/deploy/install_tailscale.sh" --sudo-auth noninteractive; then
    printf '%s\n' 'PICAMERA_TAILSCALE error installation-incomplete; retry-remote-access-setup'
    TAILSCALE_MODE="incomplete"
  fi
fi

mkdir -p -- "$APP_ROOT" "$RUNTIME_ROOT"
stage install-python-runtime
# Keep the working release's environments intact if downloading or installing
# a dependency fails. A fresh generation is selected only by the new service.
runtime_generation="$PACKAGE_VERSION-$(date +%s)-$$"
main_venv="$APP_ROOT/venvs/$runtime_generation"
[[ -x "$main_venv/bin/python" ]] || python3 -m venv "$main_venv"
"$main_venv/bin/python" -m pip install --disable-pip-version-check --upgrade pip
"$main_venv/bin/python" -m pip install --disable-pip-version-check \
  -r "$SOURCE_DIR/requirements.txt"

mcount_venv="$RUNTIME_ROOT/$runtime_generation/mcount"
[[ -x "$mcount_venv/bin/python" ]] || python3 -m venv "$mcount_venv"
"$mcount_venv/bin/python" -m pip install --disable-pip-version-check --upgrade pip
"$mcount_venv/bin/python" -m pip install --disable-pip-version-check \
  -r "$SOURCE_DIR/requirements-mcount.txt"

# Older saves could replace the config symlink with a regular file. Preserve
# the active release's settings before switching releases, even if state exists.
active_config="$APP_ROOT/current/config.json"
if [[ -f "$active_config" && ! -L "$active_config" ]]; then
  mkdir -p "$STATE_ROOT/config-backups"
  if [[ -f "$STATE_ROOT/config.json" ]]; then
    cp -p "$STATE_ROOT/config.json" "$STATE_ROOT/config-backups/before-migration-$(date +%s).json"
  fi
  cp -p "$active_config" "$STATE_ROOT/config.json"
fi

stage install-release
mkdir -p -- "$APP_ROOT/releases" "$STATE_ROOT/data" "$PHOTO_DIR" "$RUNTIME_ROOT" \
  "$HOME/.config/systemd/user" "$HOME/.config/autostart" "$HOME/.local/bin"

release_dir="$APP_ROOT/releases/$PACKAGE_VERSION"
release_stage="$APP_ROOT/releases/.${PACKAGE_VERSION}.installing.$$"
[[ ! -e "$release_stage" ]] || fail "$EXIT_SERVICE" "release-stage-already-exists"
mkdir -p -- "$release_stage"

# The manifest is the allow-list. Runtime data, credentials and developer
# temporary files cannot enter the installed release accidentally.
python3 - "$MANIFEST" "$SOURCE_DIR" "$release_stage" <<'PY'
import json
import pathlib
import shutil
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
source = pathlib.Path(sys.argv[2])
target = pathlib.Path(sys.argv[3])
for item in manifest["files"]:
    relative = pathlib.PurePosixPath(item["path"])
    destination = target.joinpath(*relative.parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source.joinpath(*relative.parts), destination)
PY

cp -- "$MANIFEST" "$release_stage/release-manifest.json"

chmod 0755 "$release_stage/deploy/install_pi.sh" "$release_stage/deploy/install_tailscale.sh"
printf '%s\n' "$PACKAGE_VERSION" >"$release_stage/.package-version"

if [[ -d "$release_dir" ]]; then
  previous="$APP_ROOT/releases/.${PACKAGE_VERSION}.previous.$(date +%s)"
  mv -- "$release_dir" "$previous"
fi
mv -- "$release_stage" "$release_dir"
ln -sfn -- "$release_dir" "$APP_ROOT/.current.new"
mv -Tf -- "$APP_ROOT/.current.new" "$APP_ROOT/current"

config_path="$STATE_ROOT/config.json"
legacy_config="$HOME/pi-camera-auto-capture/config.json"
if [[ ! -f "$config_path" ]]; then
  if [[ -f "$legacy_config" ]]; then
    cp --preserve=mode,timestamps -- "$legacy_config" "$config_path"
  else
    printf '{}\n' >"$config_path"
  fi
fi

if ((PHOTO_DIR_EXPLICIT == 0)); then
  configured_photo_dir="$(python3 - "$config_path" <<'PY'
import json
import pathlib
import sys

try:
    value = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8-sig")).get("photo_dir", "")
except (FileNotFoundError, json.JSONDecodeError):
    value = ""
print(value)
PY
)"
  if [[ -n "$configured_photo_dir" ]]; then
    PHOTO_DIR="$configured_photo_dir"
  fi
fi
mkdir -p -- "$PHOTO_DIR"

# Copy legacy state without removing the source. SQLite's backup API gives a
# consistent snapshot even if the old service is still running during upgrade.
legacy_data="$HOME/pi-camera-auto-capture/data"
if [[ -f "$legacy_data/history.sqlite3" && ! -f "$STATE_ROOT/data/history.sqlite3" ]]; then
  python3 - "$legacy_data/history.sqlite3" "$STATE_ROOT/data/history.sqlite3" <<'PY'
import sqlite3
import sys

source = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
target = sqlite3.connect(sys.argv[2])
with target:
    source.backup(target)
target.close()
source.close()
PY
fi
if [[ -d "$legacy_data/thumbnails" && ! -e "$STATE_ROOT/data/thumbnails" ]]; then
  cp -a -- "$legacy_data/thumbnails" "$STATE_ROOT/data/thumbnails"
fi

stage configure-runtime
python3 - "$config_path" "$PHOTO_DIR" "$STATE_ROOT" "$mcount_venv" "$APP_ROOT/current" "$UI_LANGUAGE" <<'PY'
import json
import os
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
try:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
except (FileNotFoundError, json.JSONDecodeError):
    config = {}
if config.get("ui_language") not in {"en", "zh", "de"}:
    config["ui_language"] = sys.argv[6]
config.update({
    "photo_dir": sys.argv[2],
    "history_db_path": str(pathlib.Path(sys.argv[3]) / "data" / "history.sqlite3"),
    "thumbnail_dir": str(pathlib.Path(sys.argv[3]) / "data" / "thumbnails"),
    "colony_runtime_dir": str(pathlib.Path(sys.argv[3]) / "data" / "colony-runtime"),
    "opencfu_runtime_root": "/",
    "opencfu_command": "/usr/bin/opencfu",
    "mcount_python": str(pathlib.Path(sys.argv[4]) / "bin" / "python"),
    "mcount_script": str(pathlib.Path(sys.argv[5]) / "tools" / "mcount_cli.py"),
})
temporary = path.with_suffix(".tmp")
temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
os.replace(temporary, path)
PY
ln -sfn -- "$config_path" "$release_dir/config.json"

if [[ "$PICO_MODE" == "auto" ]]; then
stage configure-pico
pico_service_active=0
if systemctl --user is-active --quiet pi-camera-web.service; then
  pico_service_active=1
  systemctl --user stop pi-camera-web.service
fi
if "$main_venv/bin/python" "$release_dir/tools/upload_pico_main.py" --if-present \
    --source "$release_dir/pico_main.py" --backup-dir "$STATE_ROOT/pico-backups"; then
  :
else
  if ((pico_service_active)); then systemctl --user start pi-camera-web.service; fi
  fail "$EXIT_HARDWARE_ACCESS" "pico-upload-failed; previous-program-backed-up"
fi

fi

stage install-services
cat >"$HOME/.config/systemd/user/pi-camera-web.service" <<EOF
[Unit]
Description=Pi Camera Web Control
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_ROOT/current
Environment=MOCK_CAMERA=0
Environment=PHOTO_DIR=$PHOTO_DIR
Environment=HOST=0.0.0.0
Environment=PORT=$PORT
Environment=PYTHONUNBUFFERED=1
ExecStart=$main_venv/bin/python app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

cat >"$HOME/.config/systemd/user/pi-camera-screen-idle.service" <<EOF
[Unit]
Description=Pi Camera touchscreen idle power manager
After=graphical-session.target pi-camera-web.service

[Service]
Type=simple
WorkingDirectory=$APP_ROOT/current
Environment=XDG_RUNTIME_DIR=/run/user/$UID
Environment=WAYLAND_DISPLAY=wayland-0
ExecStart=$main_venv/bin/python $APP_ROOT/current/screen_idle.py
ExecStopPost=-$main_venv/bin/python $APP_ROOT/current/screen_idle.py --power on
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

cat >"$HOME/.local/bin/pi-camera-control-kiosk.sh" <<EOF
#!/bin/sh
BASE_URL="http://127.0.0.1:$PORT"
URL="\$BASE_URL/?display=kiosk"
PROFILE_DIR="\$HOME/.cache/pi-camera-kiosk-profile"
LOCK_FILE="/tmp/pi-camera-control-kiosk.lock"
mkdir -p "\$PROFILE_DIR"
exec 9>"\$LOCK_FILE"
flock -n 9 || exit 0
for delay in 1 1 1 1 1 2 2 3 3 5; do
  curl -fsS "\$BASE_URL/health" >/dev/null 2>&1 && break
  sleep "\$delay"
done
exec /usr/bin/chromium --ozone-platform=wayland --no-first-run \
  --no-default-browser-check --disable-session-crashed-bubble \
  --disable-infobars --disable-extensions --disable-translate \
  --disable-features=Translate,TranslateUI --accept-lang=$UI_LANGUAGE,en \
  --touch-events=enabled --password-store=basic --user-data-dir="\$PROFILE_DIR" \
  --start-fullscreen --kiosk "\$URL"
EOF
chmod 0755 "$HOME/.local/bin/pi-camera-control-kiosk.sh"

cat >"$HOME/.config/autostart/pi-camera-control.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Pi Camera Control
Comment=Open Pi Camera Control on the local touchscreen
Exec=$HOME/.local/bin/pi-camera-control-kiosk.sh
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

python3 - "$HOME/.config/labwc/autostart" "$ENABLE_KIOSK" "$HOME/.local/bin/pi-camera-control-kiosk.sh" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
enabled = sys.argv[2] == "1"
command = sys.argv[3]
begin = "# BEGIN Pi Camera Control managed kiosk"
end = "# END Pi Camera Control managed kiosk"
text = path.read_text(encoding="utf-8") if path.exists() else ""
before, marker, remainder = text.partition(begin)
if marker:
    _managed, closing, after = remainder.partition(end)
    text = before.rstrip() + ("\n" + after.lstrip("\n") if closing else "")
if enabled:
    text = text.rstrip() + f"\n\n{begin}\n{command} &\n{end}\n"
elif text and not text.endswith("\n"):
    text += "\n"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(text, encoding="utf-8")
PY

systemctl --user daemon-reload || fail "$EXIT_SERVICE" "systemd-user-daemon-unavailable"
systemctl --user enable pi-camera-web.service >/dev/null
if ((ENABLE_KIOSK)); then
  systemctl --user enable pi-camera-screen-idle.service >/dev/null
else
  systemctl --user disable --now pi-camera-screen-idle.service >/dev/null 2>&1 || true
  sed -i 's/^X-GNOME-Autostart-enabled=.*/X-GNOME-Autostart-enabled=false/' \
    "$HOME/.config/autostart/pi-camera-control.desktop"
fi

systemctl --user restart pi-camera-web.service
if ((ENABLE_KIOSK)); then
  if [[ -S "/run/user/$UID/wayland-0" ]]; then
    systemctl --user restart pi-camera-screen-idle.service || true
  fi
fi

stage health-check
healthy=0
for _ in $(seq 1 45); do
  if curl --fail --silent --show-error --max-time 2 \
    "http://127.0.0.1:$PORT/health" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
    healthy=1
    break
  fi
  sleep 1
done
if ((healthy == 0)); then
  systemctl --user --no-pager --full status pi-camera-web.service >&2 || true
  journalctl --user -u pi-camera-web.service -n 80 --no-pager >&2 || true
  fail "$EXIT_HEALTH" "web-health-check-failed"
fi

if ((ENABLE_KIOSK)); then
  stage refresh-kiosk
  python3 "$APP_ROOT/current/deploy/reload_kiosk.py" || printf 'PICAMERA_WARNING kiosk-refresh-deferred\n' >&2
fi

printf 'PICAMERA_RESULT status=ready-local url=http://127.0.0.1:%s version=%s kiosk=%s\n' \
  "$PORT" "$PACKAGE_VERSION" "$ENABLE_KIOSK"

stage complete
printf 'PICAMERA_RESULT status=ready url=http://127.0.0.1:%s version=%s kiosk=%s tailscale=%s\n' \
  "$PORT" "$PACKAGE_VERSION" "$ENABLE_KIOSK" "$TAILSCALE_MODE"
