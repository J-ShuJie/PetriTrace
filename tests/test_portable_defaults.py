from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from colony_counting import _mcount_paths
from pico_bridge import discover_pico_port


class PortableDefaultsTests(unittest.TestCase):
    def test_mcount_uses_current_users_installed_runtime_and_honours_override(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            runtime = home / '.local/opt/pi-camera-colony/mcount/bin/python'
            runtime.parent.mkdir(parents=True)
            runtime.touch()
            alternate = home / 'custom-python'
            alternate.touch()
            with patch('colony_counting.Path.home', return_value=home):
                self.assertEqual(_mcount_paths({})[0], runtime)
                self.assertEqual(_mcount_paths({'mcount_python': str(alternate)})[0], alternate)

    def test_pico_discovers_another_board_and_keeps_configured_port_priority(self):
        found = '/dev/serial/by-id/usb-MicroPython_Board_TEST-if00'
        explicit = '/dev/ttyACM4'
        with patch('pico_bridge.glob.glob', side_effect=lambda pattern: [found] if 'by-id' in pattern else []), patch('pico_bridge.os.path.exists', side_effect=lambda port: port in {found, explicit}):
            self.assertEqual(discover_pico_port({}), found)
            self.assertEqual(discover_pico_port({'pico_serial_port': explicit}), explicit)
