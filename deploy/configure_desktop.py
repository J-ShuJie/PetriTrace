"""Configure the selected Pi desktop user without restarting their session."""
import argparse
import pathlib
import re
import shutil
import time


def desktop_config(text, user, session):
    if not re.fullmatch(r"[a-z_][a-z0-9_-]*[$]?", user):
        raise ValueError("Invalid desktop user")
    if session not in {"rpd-labwc", "LXDE-pi-labwc", "labwc"}:
        raise ValueError("Unsupported desktop session")
    values = {"autologin-user": user, "autologin-user-timeout": "0",
              "autologin-session": session, "user-session": session}
    lines = text.splitlines()
    output = []
    in_seat = False
    found = False
    for line in lines:
        if re.match(r"\s*\[", line):
            if in_seat:
                output.extend(f"{k}={v}" for k, v in values.items())
            in_seat = line.strip() == "[Seat:*]"
            found |= in_seat
        if in_seat and re.match(r"\s*(autologin-user|autologin-user-timeout|autologin-session|user-session)\s*=", line):
            continue
        output.append(line)
    if not found:
        output.extend(["", "[Seat:*]"])
    if in_seat or not found:
        output.extend(f"{k}={v}" for k, v in values.items())
    return "\n".join(output) + "\n"


def main():
    import pwd
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    args = parser.parse_args()
    pwd.getpwnam(args.user)
    sessions = pathlib.Path('/usr/share/wayland-sessions')
    session = next((s for s in ('rpd-labwc', 'LXDE-pi-labwc', 'labwc')
                    if (sessions / (s + '.desktop')).is_file()), None)
    if not session:
        raise SystemExit('No Labwc desktop session installed')
    path = pathlib.Path('/etc/lightdm/lightdm.conf')
    original = path.read_text()
    updated = desktop_config(original, args.user, session)
    if updated != original:
        shutil.copy2(path, path.with_name(path.name + f'.petritrace-{time.time_ns()}.bak'))
        temporary = path.with_suffix('.petritrace.tmp')
        temporary.write_text(updated)
        shutil.copymode(path, temporary)
        temporary.replace(path)
    print(f'PICAMERA_DESKTOP user={args.user} session={session} autologin=enabled')


if __name__ == '__main__':
    main()
