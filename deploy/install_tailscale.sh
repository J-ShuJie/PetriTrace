#!/usr/bin/env bash
set -Eeuo pipefail

# Tailscale is deliberately not redistributed with this project. This helper
# runs only after the user explicitly selects the optional Tailscale step in
# the Windows manager. A LAN-only installation never calls this file.

readonly EXIT_SUDO_REQUIRED=23
readonly EXIT_DOWNLOAD_FAILED=31
SUDO_AUTH="noninteractive"

if (($#)); then
  if [[ "$1" == "--sudo-auth" && $# -eq 2 ]]; then
    SUDO_AUTH="$2"
  else
    printf '%s\n' 'Usage: install_tailscale.sh [--sudo-auth noninteractive|stdin]' >&2
    exit 64
  fi
fi
[[ "$SUDO_AUTH" == "noninteractive" || "$SUDO_AUTH" == "stdin" ]] || exit 64

log() {
  printf 'PICAMERA_TAILSCALE %s\n' "$*"
}

if ! sudo -n true >/dev/null 2>&1; then
  if [[ "$SUDO_AUTH" != "stdin" ]] \
    || ! sudo -S -p 'PICAMERA_SUDO_PROMPT password-required\n' -v; then
    log "error sudo-auth-required"
    exit "$EXIT_SUDO_REQUIRED"
  fi
fi

if command -v tailscale >/dev/null 2>&1; then
  log "already-installed"
else
  if ! command -v curl >/dev/null 2>&1; then
    log "error curl-not-installed"
    exit "$EXIT_DOWNLOAD_FAILED"
  fi

  installer="$(mktemp --tmpdir tailscale-install.XXXXXX.sh)"
  cleanup() {
    rm -f -- "$installer"
  }
  trap cleanup EXIT

  log "downloading-vendor-installer"
  if ! curl --proto '=https' --tlsv1.2 --fail --show-error --location \
    https://tailscale.com/install.sh --output "$installer"; then
    log "error download-failed"
    exit "$EXIT_DOWNLOAD_FAILED"
  fi

  chmod 0700 "$installer"
  log "installing"
  sudo -n sh "$installer"
fi

if ! command -v tailscale >/dev/null 2>&1; then
  log "error executable-not-found-after-install"
  exit "$EXIT_DOWNLOAD_FAILED"
fi

if sudo -n tailscale ip -4 >/dev/null 2>&1; then
  log "ready"
  exit 0
fi

# `tailscale up` prints a one-time HTTPS authorization URL, then waits for the
# user to approve it. Limit that wait so optional remote access can never hold
# the base LAN deployment hostage. The Windows manager recognizes the
# PICAMERA_TAILSCALE_AUTH_URL line and exposes it as a button.
log "requesting-browser-authorization"
set +e
auth_output="$(timeout 25s sudo -n tailscale up 2>&1)"
auth_status=$?
set -e

if sudo -n tailscale ip -4 >/dev/null 2>&1; then
  log "ready"
  exit 0
fi

auth_url="$(printf '%s\n' "$auth_output" \
  | grep -Eo 'https://[^[:space:]]+' \
  | sed -n '1p' || true)"
if [[ -n "$auth_url" ]]; then
  printf 'PICAMERA_TAILSCALE_AUTH_URL %s\n' "$auth_url"
  log "authorization-pending command-status=$auth_status"
else
  log "authorization-pending no-url-reported command-status=$auth_status"
  printf '%s\n' 'PICAMERA_TAILSCALE_NEXT Run `sudo tailscale up` on the Pi and complete the browser authorization.'
fi

# Remote access is optional. Reaching this point must not turn a healthy LAN
# install into a failed deployment.
exit 0
