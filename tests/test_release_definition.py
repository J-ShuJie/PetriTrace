from __future__ import annotations

import json
import re
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]


class ReleaseDefinitionTests(unittest.TestCase):
    def test_manifest_contract_matches_windows_manager_protocol(self):
        manifest = json.loads((ROOT / "deploy" / "release-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["installScript"], "deploy/install_pi.sh")
        self.assertRegex(manifest["packageVersion"], r"^[0-9A-Za-z][0-9A-Za-z._+-]*$")
        self.assertTrue(manifest["features"]["lanOnlyInstallSupported"])
        self.assertFalse(manifest["features"]["tailscaleDefault"])
        self.assertFalse(manifest["features"]["tailscaleBundled"])
        schema = json.loads((ROOT / "deploy" / "release-manifest.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schemaVersion"]["const"], 1)
        self.assertEqual(schema["properties"]["installScript"]["const"], "deploy/install_pi.sh")

    def test_release_allow_list_is_safe_complete_and_unique(self):
        lines = (ROOT / "deploy" / "release-files.txt").read_text(encoding="utf-8").splitlines()
        files = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(len(files), len(set(files)))
        self.assertIn("deploy/install_pi.sh", files)
        self.assertIn("THIRD_PARTY_NOTICES.md", files)
        for relative in files:
            self.assertNotIn("\\", relative)
            path = PurePosixPath(relative)
            self.assertFalse(path.is_absolute())
            self.assertNotIn("..", path.parts)
            self.assertTrue(ROOT.joinpath(*path.parts).is_file(), relative)
            self.assertFalse(re.search(r"(^|/)(config\.json|photos?|data|\.env)(/|$)", relative))

    def test_installer_exposes_stable_progress_and_offline_success_contract(self):
        script = (ROOT / "deploy" / "install_pi.sh").read_text(encoding="utf-8")
        for marker in (
            "PICAMERA_STAGE=",
            "PICAMERA_ERROR",
            "status=ready-local",
            "--preflight-only",
            "--sudo-auth",
            "--tailscale",
        ):
            self.assertIn(marker, script)
        self.assertIn('TAILSCALE_MODE="skip"', script)
        self.assertNotRegex(script, r"100\.(?:6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.|192\.168\.")

    def test_template_static_dependencies_are_allow_listed(self):
        lines = (ROOT / "deploy" / "release-files.txt").read_text(encoding="utf-8").splitlines()
        release_files = {line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")}
        template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        referenced = {
            f"static/{path}"
            for path in re.findall(r"url_for\('static', filename='([^']+)'\)", template)
        }
        self.assertTrue(referenced, "template should reference packaged static assets")
        self.assertEqual(set(), referenced - release_files)

        stylesheet = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        css_referenced = {
            f"static/{path}"
            for path in re.findall(r'url\(["\']?([^"\')]+)["\']?\)', stylesheet)
            if not path.startswith(("data:", "http:", "https:"))
        }
        self.assertEqual(set(), css_referenced - release_files)

    def test_optional_tailscale_step_returns_authorization_without_blocking_lan(self):
        script = (ROOT / "deploy" / "install_tailscale.sh").read_text(encoding="utf-8")
        self.assertIn("PICAMERA_TAILSCALE_AUTH_URL", script)
        self.assertIn("timeout 25s sudo -n tailscale up", script)
        self.assertIn("Remote access is optional", script)
        self.assertNotIn("auth key", script.lower())


if __name__ == "__main__":
    unittest.main()
