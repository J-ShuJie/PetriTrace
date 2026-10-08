import ast
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from deploy.configure_desktop import desktop_config


class DesktopTests(unittest.TestCase):
    def test_idempotent_preserves_other_seats_and_comments(self):
        original = '# mine\n[Seat:*]\nautologin-user=old\nuser-session=old\nfoo=bar\n[Seat:remote]\nuser-session=remote\n'
        result = desktop_config(original, 'tester', 'rpd-labwc')
        self.assertIn('foo=bar', result)
        self.assertIn('[Seat:remote]\nuser-session=remote', result)
        self.assertIn('autologin-user=tester', result)
        self.assertEqual(result, desktop_config(result, 'tester', 'rpd-labwc'))

    def test_new_section_and_reject_injection(self):
        self.assertIn('[Seat:*]\nautologin-user=tester', desktop_config('[LightDM]\n', 'tester', 'labwc'))
        with self.assertRaises(ValueError):
            desktop_config('', 'bad\nuser', 'labwc')


class PicoTests(unittest.TestCase):
    def test_verified_write_and_backup(self):
        from tools import upload_pico_main as uploader
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(uploader, 'read_file', side_effect=[b'old', b'new']), patch.object(uploader, 'raw_exec') as execute:
                result = uploader.install_program(None, b'new', '/main.py', pathlib.Path(directory))
                self.assertEqual(result, 'updated')
                self.assertEqual(next(pathlib.Path(directory).glob('*.py')).read_bytes(), b'old')
                self.assertIn(b'os.rename', execute.call_args[0][1])

    def test_bad_readback_leaves_main(self):
        from tools import upload_pico_main as uploader
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(uploader, 'read_file', side_effect=[b'old', b'bad']), patch.object(uploader, 'raw_exec') as execute:
                with self.assertRaises(RuntimeError):
                    uploader.install_program(None, b'new', '/main.py', pathlib.Path(directory))
                self.assertEqual(execute.call_count, 1)

    def test_raw_repl_error_is_not_success(self):
        from tools import upload_pico_main as uploader
        with patch.object(uploader, 'read_until', return_value=b'OK\x04OSError: disk full\x04>'):
            with patch('tools.upload_pico_main.time.sleep'):
                from unittest.mock import Mock
                with self.assertRaises(RuntimeError):
                    uploader.raw_exec(Mock(), b'write()')


class SensorTests(unittest.TestCase):
    def test_th02_conversion_and_timeout(self):
        source = pathlib.Path('pico_main.py').read_text()
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'read_th02')
        from unittest.mock import Mock
        namespace = {'time': Mock(), 'now_s': lambda: 1}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'sensor', 'exec'), namespace)
        bus = Mock()
        # 25 C -> (25+50)*32 << 2; 50% -> (50+24)*16 << 4.
        bus.readfrom_mem.side_effect = [b'\x00', (9600).to_bytes(2, 'big'), b'\x00', (18944).to_bytes(2, 'big')]
        result = namespace['read_th02'](bus)
        self.assertEqual((result['temperature_c'], result['humidity_percent']), (25, 50))
        bus.readfrom_mem.side_effect = None
        bus.readfrom_mem.return_value = b'\x01'
        with self.assertRaises(OSError):
            namespace['read_th02'](bus)
