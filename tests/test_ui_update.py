import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import config_store
from deploy.reload_kiosk import kiosk_processes


class UpdatePersistenceTests(unittest.TestCase):
    def test_save_keeps_deployment_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'persistent.json'
            target.write_text('{}')
            link = root / 'config.json'
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest('symlink privilege unavailable; run on Pi')
            with patch.object(config_store, 'CONFIG_PATH', link):
                config_store.save_config({'ui_language': 'de', 'interval_seconds': 123})
            self.assertTrue(link.is_symlink())
            self.assertEqual(json.loads(target.read_text())['interval_seconds'], 123)

    @unittest.skipUnless(os.name == "posix", "Linux /proc command-line semantics")
    def test_kiosk_accepts_flattened_argv_but_excludes_other_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = f'--user-data-dir={Path.home()}/.cache/pi-camera-kiosk-profile'
            commands = [
                ('/usr/lib/chromium/chromium --kiosk ' + profile + '\0'),
                ('/usr/lib/chromium/chromium\0--kiosk\0' + profile + '\0'),
                ('/usr/lib/chromium/chromium --type=renderer --kiosk ' + profile + '\0'),
                ('/usr/bin/python3 --kiosk ' + profile + '\0'),
                '/usr/lib/chromium/chromium --kiosk --user-data-dir=/different/profile\0',
            ]
            for i, command in enumerate(commands, 1):
                item=root/str(i);item.mkdir();(item/'cmdline').write_bytes(command.encode());(item/'environ').write_bytes(b'WAYLAND_DISPLAY=wayland-0\0')
            with patch('os.getuid', return_value=root.stat().st_uid, create=True):
                self.assertEqual(sorted(pid for pid,_ in kiosk_processes(root)), [1,2])

if __name__ == '__main__':
    unittest.main()
