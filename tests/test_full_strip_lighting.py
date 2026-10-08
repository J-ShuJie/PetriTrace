import ast
import pathlib
import sys
import types
import unittest
from unittest.mock import patch


class Pixels:
    def __init__(self, pin, count):
        self.values = [(255, 255, 255)] * count
        self.writes = 0

    def __setitem__(self, index, value):
        self.values[index] = value

    def write(self):
        self.writes += 1


class FullStripTests(unittest.TestCase):
    def setUp(self):
        source = ast.parse(pathlib.Path('pico_main.py').read_text(encoding='utf-8'))
        source.body.pop()  # Run the real firmware without entering its serial loop.
        pin = type('Pin', (), {'OUT': 1, '__init__': lambda self, *args: None})
        modules = {'machine': types.SimpleNamespace(Pin=pin, I2C=lambda *a, **k: None),
                   'neopixel': types.SimpleNamespace(NeoPixel=Pixels)}
        self.fw = {}
        with patch.dict(sys.modules, modules):
            exec(compile(source, 'pico_main.py', 'exec'), self.fw)
        self.fw['read_sensors'] = lambda: []

    def test_on_dim_and_off_cover_tail_beyond_old_eighteen(self):
        pixels = self.fw['np']
        self.assertGreaterEqual(len(pixels.values), 22)
        for brightness, expected in [(1.0, (255, 128, 64)), (0.35, (89, 44, 22)), (0, (0, 0, 0))]:
            self.fw['handle_command']({'cmd': 'light', 'mode': 'on', 'brightness': brightness, 'color': '#ff8040'})
            self.assertTrue(all(pixel == expected for pixel in pixels.values))
        self.fw['handle_command']({'cmd': 'light', 'mode': 'off'})
        self.assertTrue(all(pixel == (0, 0, 0) for pixel in pixels.values))
        self.assertEqual(pixels.writes, 4)

    def test_reports_frame_capacity_not_a_detected_physical_count(self):
        status = self.fw['light_status']()
        self.assertEqual(status['coverage'], 'all')
        self.assertNotIn('count', status)
        self.assertEqual(status['frame_pixels'], len(self.fw['np'].values))

    def test_legacy_count_cannot_restrict_new_firmware(self):
        from config_store import DEFAULT_CONFIG, _coerce_config
        for old_count in (6, 18, 'invalid'):
            config = _coerce_config(dict(DEFAULT_CONFIG, pico_led_count=old_count))
            self.assertNotIn('pico_led_count', config)
