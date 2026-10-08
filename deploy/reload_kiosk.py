"""Reload only the already-running PetriTrace kiosk after a healthy deployment."""
import os
from pathlib import Path
import signal
import shlex
import subprocess
import time


def kiosk_processes(proc=Path('/proc')):
    profile = str(Path.home() / '.cache/pi-camera-kiosk-profile')
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            args = [arg for arg in (entry / 'cmdline').read_bytes().decode().split('\0') if arg]
            # Chromium on Raspberry Pi rewrites argv as one space-separated title.
            if len(args) == 1:
                args = shlex.split(args[0])
            if not args or Path(args[0]).name not in {'chromium', 'chromium-browser'}:
                continue
            if '--kiosk' not in args or f'--user-data-dir={profile}' not in args:
                continue
            if any(arg.startswith('--type=') for arg in args):
                continue
            env = dict(item.split('=', 1) for item in (entry / 'environ').read_bytes().decode().split('\0') if '=' in item)
            yield int(entry.name), env
        except (OSError, UnicodeError):
            continue


def main():
    processes = list(kiosk_processes())
    if not processes:
        print('Kiosk not running; updated page will load at next launch.')
        return
    env = os.environ.copy()
    for key in ('WAYLAND_DISPLAY', 'DISPLAY', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS'):
        if key in processes[0][1]:
            env[key] = processes[0][1][key]
    runtime = f'/run/user/{os.getuid()}'
    env.setdefault('XDG_RUNTIME_DIR', runtime)
    if Path(runtime, 'wayland-0').exists():
        env.setdefault('WAYLAND_DISPLAY', 'wayland-0')
    for pid, _ in processes:
        os.kill(pid, signal.SIGTERM)
    for _ in range(100):
        if not list(kiosk_processes()):
            break
        time.sleep(.1)
    else:
        raise RuntimeError('Kiosk did not exit; automatic restart deferred.')
    time.sleep(1)
    log_path = Path.home() / '.local/state/pi-camera-control/kiosk-launch.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('ab') as log:
        child = subprocess.Popen([str(Path.home() / '.local/bin/pi-camera-control-kiosk.sh')], env=env,
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    for _ in range(50):
        time.sleep(.2)
        if list(kiosk_processes()):
            break
        if child.poll() is not None:
            raise RuntimeError(f'Kiosk launch failed; see {log_path}')
    else:
        raise RuntimeError(f'Kiosk launch not verified; see {log_path}')
    print('Kiosk relaunched with updated webpage.')


if __name__ == '__main__':
    main()
