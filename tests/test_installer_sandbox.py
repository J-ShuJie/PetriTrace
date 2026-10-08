"""Linux installer orchestration checks. All privileged/network actions are stubs.

Set PICAMERA_TEST_ARCHIVE to a built release tarball. No real app service is run.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PICAMERA_TEST_ARCHIVE'),
                     'requires Linux and a built PICAMERA_TEST_ARCHIVE')
class InstallerSandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='pi-installer-audit-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / 'home'
        self.home.mkdir()
        self.source = self.base / 'payload'
        self.source.mkdir()
        with tarfile.open(os.environ['PICAMERA_TEST_ARCHIVE']) as archive:
            archive.extractall(self.source, filter='data')
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        self.log = self.base / 'commands.jsonl'
        self.env = dict(os.environ, HOME=str(self.home), PATH=f'{self.bin}:/usr/bin:/bin',
                        XDG_DATA_HOME=str(self.home / '.local/share'),
                        XDG_STATE_HOME=str(self.home / '.local/state'),
                        TMPDIR=str(self.base), AUDIT_LOG=str(self.log))
        self.stub('uname', "print('aarch64')")
        self.stub('df', "print('Filesystem 1024-blocks Used Available Capacity Mounted\\nfixture 99999999 0 99999999 0% /')")
        self.stub('id', "print('tester' if '-un' in sys.argv else os.environ.get('AUDIT_GROUPS','tester dialout video render'))")
        self.stub('getent', "print('group:x:1000:tester')")
        self.stub('dpkg-query', 'sys.exit(1)')
        self.stub('labwc', 'pass')
        self.stub('curl', "print('{\"ok\":true}')")
        log = "with open(os.environ['AUDIT_LOG'],'a') as f: f.write(json.dumps(sys.argv)+'\\n')\n"
        self.stub('sudo', log + "if os.environ.get('AUDIT_TAILSCALE_FAIL') and 'bash' in sys.argv: sys.exit(31)")
        self.stub('systemctl', log)
        pip = '#!' + sys.executable + '\nimport os,sys\nif sys.argv[1:3]==["-m","pip"]: sys.exit(17 if os.environ.get("AUDIT_PIP_FAIL") else 0)\nos.execv(' + repr(sys.executable) + ',[' + repr(sys.executable) + ']+sys.argv[1:])\n'
        self.stub('python3', 'from pathlib import Path\n'
                  'if sys.argv[1:3]==["-m","venv"]:\n'
                  ' p=Path(sys.argv[3])/"bin/python";p.parent.mkdir(parents=True,exist_ok=True);'
                  f'p.write_text({pip!r});p.chmod(0o755)\n'
                  f'else: os.execv({sys.executable!r},[{sys.executable!r}]+sys.argv[1:])')

    def stub(self, name, body):
        p = self.bin / name
        p.write_text(f'#!{sys.executable}\nimport os,sys,json\n{body}\n')
        p.chmod(0o755)

    def run_install(self, *args):
        return subprocess.run(['/bin/bash', str(self.source / 'deploy/install_pi.sh'),
                               '--source', str(self.source), '--disable-kiosk', '--pico-mode', 'skip', *args],
                              env=self.env, text=True, capture_output=True, timeout=30)

    def test_first_install_and_repeat_preserve_data(self):
        for iteration in range(2):
            result = self.run_install('--ui-language', 'de')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('status=ready ', result.stdout)
            app = self.home / '.local/share/pi-camera-control'
            self.assertTrue((app / 'current/app.py').is_file())
            config_path = self.home / '.local/state/pi-camera-control/config.json'
            config = json.loads(config_path.read_text())
            if iteration:
                self.assertEqual(config['audit_marker'], 'keep')
                self.assertEqual(config['ui_language'], 'zh')
            self.assertTrue(Path(config['mcount_python']).is_file())
            self.assertEqual(config['ui_language'], 'de' if not iteration else 'zh')
            config['ui_language'] = 'zh'
            config['audit_marker'] = 'keep'
            config_path.write_text(json.dumps(config))
        self.assertEqual(json.loads(config_path.read_text())['audit_marker'], 'keep')
        commands = self.log.read_text()
        self.assertIn('udisks2', commands)
        self.assertIn('enable-linger', commands)

    def test_upgrade_recovers_settings_from_broken_legacy_symlink(self):
        app = self.home / '.local/share/pi-camera-control'
        old = app / 'releases/old'
        old.mkdir(parents=True)
        (app / 'current').symlink_to(old)
        (old / 'config.json').write_text('{"interval_seconds":600,"ui_language":"en"}')
        state = self.home / '.local/state/pi-camera-control/config.json'
        state.parent.mkdir(parents=True)
        state.write_text('{"interval_seconds":5,"ui_language":"zh"}')
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(state.read_text())['interval_seconds'], 600)
        self.assertEqual(json.loads(state.read_text())['ui_language'], 'en')
        self.assertTrue((app / 'current/config.json').is_symlink())
        self.assertEqual(len(list((state.parent / 'config-backups').glob('*.json'))), 1)

    def test_dependency_failure_leaves_active_release_and_config_unchanged(self):
        app = self.home / '.local/share/pi-camera-control'
        old = app / 'releases/old'
        old.mkdir(parents=True)
        (app / 'current').symlink_to(old)
        config = self.home / '.local/state/pi-camera-control/config.json'
        config.parent.mkdir(parents=True)
        config.write_text('{"untouched":true}')
        self.env['AUDIT_PIP_FAIL'] = '1'
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((app / 'current').resolve(), old)
        self.assertEqual(config.read_text(), '{"untouched":true}')
        self.assertNotIn('systemctl', self.log.read_text())

    def test_missing_hardware_group_fails_before_privileged_work(self):
        self.env['AUDIT_GROUPS'] = 'tester video render'
        result = self.run_install()
        self.assertEqual(result.returncode, 28)
        self.assertIn('missing-hardware-group:dialout', result.stderr)
        self.assertFalse(self.log.exists())

    def test_missing_desktop_rejected_for_kiosk(self):
        (self.bin / 'labwc').unlink()
        # Force command lookup to fail only for labwc, regardless of the host OS.
        script = self.source / 'deploy/install_pi.sh'
        text = script.read_text().replace('command -v labwc', 'command -v audit-no-such-labwc')
        script.write_text(text)
        manifest_path = self.source / 'release-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        import hashlib
        for entry in manifest['files']:
            if entry['path'] == 'deploy/install_pi.sh':
                entry.update(size=script.stat().st_size, sha256=hashlib.sha256(script.read_bytes()).hexdigest())
        manifest_path.write_text(json.dumps(manifest))
        result = self.run_install('--enable-kiosk')
        self.assertEqual(result.returncode, 29)
        self.assertFalse(self.log.exists())

    def test_optional_tailscale_failure_keeps_lan_install_usable(self):
        self.env['AUDIT_TAILSCALE_FAIL'] = '1'
        result = self.run_install('--tailscale', 'install')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PICAMERA_TAILSCALE error installation-incomplete', result.stdout)
        self.assertIn('tailscale=incomplete', result.stdout)


if __name__ == '__main__':
    unittest.main()
