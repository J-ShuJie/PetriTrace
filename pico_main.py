# MicroPython program for Raspberry Pi Pico WH + Crowtail/Grove shield.
# USB serial JSON protocol for Pi Camera Control.

import json
import sys
import time

try:
    import select
except ImportError:
    import uselect as select

from machine import I2C, Pin

try:
    import neopixel
except ImportError:
    neopixel = None

LED_PIN = 18
# Send a complete uniform frame beyond the installed strip length.
# 64 slots cover the enclosure strip (<=36 cm at 60 LEDs/m) with margin.
LED_FRAME_PIXELS = 64
I2C_A_ID = 1
I2C_A_SDA = 6
I2C_A_SCL = 7
I2C_B_ID = 0
I2C_B_SDA = 8
I2C_B_SCL = 9

light_mode = "off"
light_brightness = 0.35
light_color = "#ffffff"

np = None
if neopixel:
    try:
        np = neopixel.NeoPixel(Pin(LED_PIN, Pin.OUT), LED_FRAME_PIXELS)
    except Exception:
        np = None


def now_s():
    try:
        return time.time()
    except Exception:
        return 0


def write_json(data):
    print(json.dumps(data))
    try:
        sys.stdout.flush()
    except Exception:
        pass


def parse_color(value):
    value = str(value or "#ffffff").strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6:
        return (255, 255, 255)
    try:
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except Exception:
        return (255, 255, 255)


def apply_light():
    if np is None:
        return False
    rgb = parse_color(light_color)
    if light_mode != "on":
        rgb = (0, 0, 0)
    else:
        brightness = max(0.0, min(1.0, float(light_brightness)))
        rgb = tuple(int(channel * brightness) for channel in rgb)
    for index in range(LED_FRAME_PIXELS):
        np[index] = rgb
    np.write()
    return True


def light_status():
    return {
        "mode": light_mode,
        "effective_on": light_mode == "on" and np is not None,
        "brightness": light_brightness,
        "color": light_color,
        "pin": LED_PIN,
        "coverage": "all",
        "frame_pixels": LED_FRAME_PIXELS,
        "ready": np is not None,
    }


def make_i2c(bus_id, sda, scl):
    return I2C(bus_id, sda=Pin(sda), scl=Pin(scl), freq=100000)


def read_th02(i2c):
    def convert(command, shift, divisor, offset):
        i2c.writeto_mem(0x40, 0x03, bytes([command]))
        for _ in range(100):
            if not (i2c.readfrom_mem(0x40, 0x00, 1)[0] & 1):
                data = i2c.readfrom_mem(0x40, 0x01, 2)
                return (((data[0] << 8) | data[1]) >> shift) / divisor - offset
            time.sleep_ms(5)
        raise OSError("TH02 conversion timeout")
    temperature = convert(0x11, 2, 32.0, 50)
    humidity = convert(0x01, 4, 16.0, 24)
    return {"id": "i2c1_0x40", "name": "I2C1 0x40", "kind": "TH02",
            "temperature_c": round(temperature, 1),
            "humidity_percent": round(max(0.0, min(100.0, humidity)), 1),
            "updated_at": now_s(), "status": "ok"}


def read_htu21d():
    i2c = make_i2c(I2C_A_ID, I2C_A_SDA, I2C_A_SCL)
    if 0x40 not in i2c.scan():
        raise OSError("0x40 not found")
    try:
        device_id = i2c.readfrom_mem(0x40, 0x11, 1)[0]
    except OSError:
        device_id = 0
    if device_id == 0x50:
        return read_th02(i2c)
    i2c.writeto(0x40, b"\xf3")
    time.sleep_ms(60)
    temp_raw = i2c.readfrom(0x40, 3)
    i2c.writeto(0x40, b"\xf5")
    time.sleep_ms(30)
    hum_raw = i2c.readfrom(0x40, 3)
    temp_code = ((temp_raw[0] << 8) | temp_raw[1]) & 0xFFFC
    hum_code = ((hum_raw[0] << 8) | hum_raw[1]) & 0xFFFC
    temp_c = -46.85 + 175.72 * temp_code / 65536.0
    hum = -6.0 + 125.0 * hum_code / 65536.0
    return {
        "id": "i2c1_0x40",
        "name": "I2C1 0x40",
        "kind": "TH06/HTU21D-compatible",
        "temperature_c": round(temp_c, 1),
        "humidity_percent": round(max(0.0, min(100.0, hum)), 1),
        "updated_at": now_s(),
        "status": "ok",
    }


def read_aht20():
    i2c = make_i2c(I2C_B_ID, I2C_B_SDA, I2C_B_SCL)
    if 0x38 not in i2c.scan():
        raise OSError("0x38 not found")
    try:
        i2c.writeto(0x38, b"\xbe\x08\x00")
        time.sleep_ms(10)
    except Exception:
        pass
    i2c.writeto(0x38, b"\xac\x33\x00")
    time.sleep_ms(90)
    data = i2c.readfrom(0x38, 6)
    hum_raw = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4)) & 0xFFFFF
    temp_raw = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5]) & 0xFFFFF
    hum = hum_raw * 100.0 / 1048576.0
    temp_c = temp_raw * 200.0 / 1048576.0 - 50.0
    return {
        "id": "i2c2_0x38",
        "name": "I2C2 0x38",
        "kind": "AHT20/DHT20-like",
        "temperature_c": round(temp_c, 1),
        "humidity_percent": round(max(0.0, min(100.0, hum)), 1),
        "updated_at": now_s(),
        "status": "ok",
    }


def sensor_error(sensor_id, name, kind, exc):
    return {
        "id": sensor_id,
        "name": name,
        "kind": kind,
        "status": "error",
        "error": str(exc),
        "updated_at": now_s(),
    }


def read_sensors():
    sensors = []
    try:
        sensors.append(read_htu21d())
    except Exception as exc:
        sensors.append(sensor_error("i2c1_0x40", "I2C1 0x40", "TH06/HTU21D-compatible", exc))
    try:
        sensors.append(read_aht20())
    except Exception as exc:
        sensors.append(sensor_error("i2c2_0x38", "I2C2 0x38", "AHT20/DHT20-like", exc))
    return sensors


def status_payload():
    return {
        "type": "status",
        "ok": True,
        "light": light_status(),
        "sensors": read_sensors(),
    }


def handle_command(command):
    global light_mode, light_brightness, light_color
    name = str(command.get("cmd") or "status").lower()
    if name == "ping":
        return {"type": "pong", "ok": True}
    if name == "light":
        mode = str(command.get("mode") or "off").lower()
        if mode not in ("off", "on"):
            raise ValueError("light mode must be off or on")
        light_mode = mode
        if "brightness" in command:
            light_brightness = max(0.0, min(1.0, float(command.get("brightness"))))
        if "color" in command:
            light_color = str(command.get("color") or "#ffffff")
        apply_light()
        return status_payload()
    if name == "status":
        return status_payload()
    raise ValueError("unknown cmd: " + name)


def main():
    apply_light()
    write_json({"type": "boot", "ok": True, "light": light_status()})
    poller = select.poll()
    poller.register(sys.stdin, select.POLLIN)
    while True:
        events = poller.poll(200)
        if not events:
            continue
        line = sys.stdin.readline()
        if not line:
            continue
        try:
            command = json.loads(line)
            if not isinstance(command, dict):
                raise ValueError("command must be an object")
            write_json(handle_command(command))
        except Exception as exc:
            write_json({"type": "error", "ok": False, "error": str(exc)})


main()