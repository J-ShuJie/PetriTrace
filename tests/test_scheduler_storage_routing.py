from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from camera_backends import MockCameraBackend
from config_store import DEFAULT_CONFIG
from scheduler import CaptureScheduler


class SchedulerStorageRoutingTests(unittest.TestCase):
    def test_capture_uses_resolved_external_directory_without_creating_local_photo(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            local = root / "local"
            external = root / "external" / "PiCameraData" / "photos"
            config = {
                **DEFAULT_CONFIG,
                "photo_dir": str(local),
                "thumbnail_dir": str(root / "thumbnails"),
                "history_db_path": str(root / "history.sqlite3"),
                "pico_enabled": False,
            }
            scheduler = CaptureScheduler(
                MockCameraBackend(),
                config,
                storage_target=lambda: {
                    "ready": True,
                    "location": "external",
                    "directory": str(external),
                    "reason": "external_preferred",
                },
            )

            with mock.patch("scheduler.record_event"), mock.patch("scheduler.record_sensor_sample"):
                result = scheduler.capture_now()

            self.assertEqual(result["storage_location"], "external")
            self.assertTrue((external / result["filename"]).is_file())
            self.assertFalse((local / result["filename"]).exists())


if __name__ == "__main__":
    unittest.main()
