from __future__ import annotations

import argparse
import pathlib
import ast
import hashlib
import json
from serial.tools import list_ports
import time

import serial  # type: ignore[import-not-found]

CTRL_A = b"\x01"
CTRL_B = b"\x02"
CTRL_C = b"\x03"
CTRL_D = b"\x04"


def read_until(handle: serial.Serial, marker: bytes, timeout: float) -> bytes:
    deadline = time.monotonic() + timeout
    data = bytearray()
    while time.monotonic() < deadline:
        chunk = handle.read(1024)
        if chunk:
            data.extend(chunk)
            if marker in data:
                return bytes(data)
    raise TimeoutError(f"Timed out waiting for {marker!r}; got {bytes(data[-200:])!r}")


def enter_raw_repl(handle: serial.Serial) -> None:
    handle.write(CTRL_C)
    time.sleep(0.1)
    handle.write(CTRL_C)
    time.sleep(0.2)
    handle.reset_input_buffer()
    handle.write(CTRL_A)
    read_until(handle, b">", 3.0)


def exit_raw_repl(handle: serial.Serial) -> None:
    handle.write(CTRL_B)
    time.sleep(0.1)


def raw_exec(handle: serial.Serial, code: bytes, timeout: float = 10.0) -> bytes:
    for start in range(0, len(code), 256):
        handle.write(code[start:start + 256])
        time.sleep(0.01)
    handle.write(CTRL_D)
    response = read_until(handle, b"\x04>", timeout)
    if not response.startswith(b"OK"):
        raise RuntimeError("Pico did not accept raw REPL command")
    output, errors, _ = response[2:].split(b"\x04", 2)
    if errors.strip():
        raise RuntimeError(errors.decode("utf-8", "replace"))
    return output


def build_write_code(source: bytes, target: str) -> bytes:
    lines = [f"f=open({target!r},'wb')".encode()]
    for start in range(0, len(source), 512):
        chunk = source[start:start + 512]
        lines.append(b"f.write(" + repr(chunk).encode() + b")")
    lines.append(b"f.close()")
    return b"\n".join(lines) + b"\n"


def select_port(requested):
    if requested:
        return requested
    candidates = [p.device for p in list_ports.comports()
                  if p.vid == 0x2E8A and ('micropython' in (p.product or '').lower()
                                         or p.pid == 0x0005)]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise RuntimeError('Multiple Pico boards detected; specify --port')
    return None


def read_file(handle, target):
    code = ("try:\n f=open(" + repr(target) + ",'rb'); d=f.read(); f.close(); print(repr(d))\n"
            "except OSError as e:\n"
            " if e.args[0] == 2: print('None')\n"
            " else: raise\n")
    return ast.literal_eval(raw_exec(handle, code.encode()).decode().strip())


def install_program(handle, source, target, backup_dir):
    previous = read_file(handle, target)
    backup_dir.mkdir(parents=True, exist_ok=True)
    if previous is not None:
        backup = backup_dir / ('pico-main-' + str(time.time_ns()) + '.py')
        backup.write_bytes(previous)
    if previous == source:
        return 'unchanged'
    temporary = target + '.petritrace-new'
    raw_exec(handle, build_write_code(source, temporary), timeout=30)
    downloaded = read_file(handle, temporary)
    if downloaded != source:
        raise RuntimeError('Pico read-back mismatch; original main.py retained')
    # Rename existing file aside only after the complete candidate has been verified.
    code = ("import os\n"
            "try: os.remove(" + repr(target + '.petritrace-backup') + ")\n"
            "except OSError: pass\n")
    if previous is not None:
        code += 'os.rename(' + repr(target) + ',' + repr(target + '.petritrace-backup') + ')\n'
    code += ("try: os.rename(" + repr(temporary) + ',' + repr(target) + ")\n"
             "except OSError:\n")
    if previous is not None:
        code += ' os.rename(' + repr(target + '.petritrace-backup') + ',' + repr(target) + ')\n'
    code += ' raise\n'
    raw_exec(handle, code.encode())
    return 'updated'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port')
    parser.add_argument('--source', default='pico_main.py')
    parser.add_argument('--target', default='/main.py')
    parser.add_argument('--backup-dir', type=pathlib.Path, required=True)
    parser.add_argument('--baud', type=int, default=115200)
    parser.add_argument('--led-count', type=int, help=argparse.SUPPRESS)  # Ignored legacy option.
    parser.add_argument('--if-present', action='store_true')
    args = parser.parse_args()
    port = select_port(args.port)
    if port is None:
        if args.if_present:
            print('PICAMERA_PICO status=not-found action=connect-Pico-WH-with-MicroPython-and-retry')
            return
        raise SystemExit('Connect a Pico WH running MicroPython or specify --port')
    source = pathlib.Path(args.source).read_bytes().removeprefix(b'\xef\xbb\xbf')
    with serial.Serial(port, args.baud, timeout=0.1, write_timeout=3.0) as handle:
        entered = False
        try:
            enter_raw_repl(handle)
            entered = True
            result = install_program(handle, source, args.target, args.backup_dir)
        finally:
            if entered:
                handle.write(CTRL_B)
                time.sleep(0.1)
                handle.write(CTRL_D)
                time.sleep(1.0)
        handle.reset_input_buffer()
        handle.write(b'{"cmd":"status"}\n')
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                status = json.loads(handle.readline())
            except (ValueError, UnicodeError):
                continue
            if isinstance(status, dict) and status.get("ok") and "light" in status:
                break
        else:
            raise RuntimeError("Pico program did not answer status after restart; backup saved")
    print(f'PICAMERA_PICO status={result} port={port} sha256={hashlib.sha256(source).hexdigest()}')


if __name__ == '__main__':
    main()
