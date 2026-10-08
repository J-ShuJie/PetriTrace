from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from external_storage import (
    ExternalStorageManager,
    copy_snapshot_archive,
    create_snapshot_payload,
    devices_from_lsblk,
)


class ExternalStorageTests(unittest.TestCase):
    def config(self, root: Path) -> dict:
        photos = root / "local-photos"
        photos.mkdir()
        return {
            "photo_dir": str(photos),
            "history_db_path": str(root / "history.sqlite3"),
            "external_data_dir_name": "PiCameraData",
            "local_reserve_mb": 5120,
        }

    def test_snapshot_preserves_existing_drive_content_and_verifies_incrementally(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            mount = root / "external"
            mount.mkdir()
            existing = mount / "personal-document.txt"
            existing.write_text("do not touch", encoding="utf-8")
            source = Path(config["photo_dir"]) / "2026-08-15_20-40-08.jpg"
            source.write_bytes(b"camera-image" * 100)

            payload = create_snapshot_payload(config)
            first = copy_snapshot_archive(config, mount, payload)
            second = copy_snapshot_archive(config, mount, payload)

            snapshot = mount / "PiCameraData" / "snapshots" / payload["snapshot_id"]
            copied = snapshot / "photos" / source.name
            manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(first["ok"])
            self.assertEqual(first["copied"], 1)
            self.assertEqual(second["copied"], 0)
            self.assertEqual(second["verified"], 1)
            self.assertEqual(copied.read_bytes(), source.read_bytes())
            self.assertEqual(len(manifest["items"][f"photos/{source.name}"]["sha256"]), 64)
            self.assertEqual(existing.read_text(encoding="utf-8"), "do not touch")
            self.assertTrue((snapshot / "exports" / "history.csv").is_file())

    def test_snapshot_copy_never_deletes_local_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            mount = root / "external"
            mount.mkdir()
            source = Path(config["photo_dir"]) / "plate.jpg"
            source.write_bytes(b"verified-before-removal")

            payload = create_snapshot_payload(config)
            result = copy_snapshot_archive(config, mount, payload)

            self.assertEqual(result["cleaned_local"], 0)
            self.assertTrue(source.exists())
            copied = mount / "PiCameraData" / "snapshots" / payload["snapshot_id"] / "photos" / source.name
            self.assertEqual(copied.read_bytes(), b"verified-before-removal")

    def test_snapshot_payload_is_fixed_at_button_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            mount = root / "external"
            mount.mkdir()
            before = Path(config["photo_dir"]) / "before.jpg"
            before.write_bytes(b"before")

            payload = create_snapshot_payload(config)
            after = Path(config["photo_dir"]) / "after.jpg"
            after.write_bytes(b"after")
            copy_snapshot_archive(config, mount, payload)

            copied = mount / "PiCameraData" / "snapshots" / payload["snapshot_id"] / "photos"
            self.assertTrue((copied / "before.jpg").is_file())
            self.assertFalse((copied / "after.jpg").exists())

    def test_lsblk_parser_distinguishes_supported_and_unformatted_usb_devices(self):
        devices = devices_from_lsblk({
            "blockdevices": [
                {
                    "path": "/dev/sda", "type": "disk", "tran": "usb", "rm": False,
                    "fstype": None, "mountpoints": [None], "size": 128000000000,
                    "children": [
                        {
                            "path": "/dev/sda1", "type": "part", "fstype": "ntfs", "uuid": "ARCHIVE",
                            "label": "LAB", "mountpoints": ["/media/lab/LAB"], "size": 127000000000,
                            "fsavail": 100000000000, "rm": False, "ro": False,
                        }
                    ],
                },
                {
                    "path": "/dev/sdb", "type": "disk", "tran": "usb", "rm": True,
                    "fstype": None, "mountpoints": [None], "size": 64000000000, "ro": False,
                },
            ]
        })

        formatted = next(item for item in devices if item["path"] == "/dev/sda1")
        unformatted = next(item for item in devices if item["path"] == "/dev/sdb")
        self.assertTrue(formatted["supported"])
        self.assertEqual(formatted["mount_path"], "/media/lab/LAB")
        self.assertTrue(unformatted["unformatted"])
        self.assertEqual(unformatted["recommended_format"], "ntfs")

    def test_manager_reports_unformatted_media_without_modifying_it(self):
        manager = ExternalStorageManager({"storage_policy": "external_preferred"})
        raw_device = {
            "path": "/dev/sdb", "filesystem": "", "mount_path": "", "supported": False,
            "unformatted": True, "recommended_format": "ntfs", "read_only": False,
        }
        with mock.patch("external_storage.discover_external_devices", return_value=[raw_device]):
            manager._cycle()
        status = manager.status()
        self.assertEqual(status["state"], "unformatted")
        self.assertEqual(status["recommended_format"], "ntfs")
        self.assertFalse(status["connected"])

    def test_local_preferred_never_migrates_existing_local_photos(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            config["storage_policy"] = "local_preferred"
            source = Path(config["photo_dir"]) / "local-only.jpg"
            source.write_bytes(b"stay local")
            mount = root / "external"
            mount.mkdir()
            device = self.device(mount, free_mb=2048)
            manager = ExternalStorageManager(config)

            with mock.patch("external_storage.discover_external_devices", return_value=[device]):
                manager._cycle()

            self.assertTrue(source.exists())
            self.assertFalse((mount / "PiCameraData" / "photos" / source.name).exists())

    def test_external_preferred_routes_directly_to_external_when_healthy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            config.update({"storage_policy": "external_preferred", "local_reserve_mb": 512})
            mount = root / "external"
            mount.mkdir()
            manager = ExternalStorageManager(config)
            with mock.patch("external_storage.discover_external_devices", return_value=[self.device(mount, free_mb=2048)]):
                manager._cycle()

            target = manager.capture_target()
            self.assertTrue(target["ready"])
            self.assertEqual(target["location"], "external")
            self.assertEqual(Path(target["directory"]), mount / "PiCameraData" / "photos")

    def test_external_preferred_falls_back_to_local_when_external_is_full(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            config.update({"storage_policy": "external_preferred", "local_reserve_mb": 512})
            mount = root / "external"
            mount.mkdir()
            manager = ExternalStorageManager(config)
            with mock.patch("external_storage.discover_external_devices", return_value=[self.device(mount, free_mb=400)]):
                manager._cycle()

            target = manager.capture_target()
            self.assertTrue(target["ready"])
            self.assertEqual(target["location"], "local")
            self.assertEqual(target["reason"], "external_low_space")
            self.assertTrue(manager.status()["low_space"])

    def test_external_preferred_falls_back_to_local_when_external_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            config.update({"storage_policy": "external_preferred", "local_reserve_mb": 512})
            manager = ExternalStorageManager(config)
            with mock.patch("external_storage.discover_external_devices", return_value=[]):
                manager._cycle()

            target = manager.capture_target()
            self.assertTrue(target["ready"])
            self.assertEqual(target["location"], "local")
            self.assertEqual(target["reason"], "external_unavailable")

    def test_local_preferred_spills_new_captures_without_migrating_old_photos(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            config.update({"storage_policy": "local_preferred", "local_reserve_mb": 512})
            source = Path(config["photo_dir"]) / "old-local.jpg"
            source.write_bytes(b"old")
            mount = root / "external"
            mount.mkdir()
            manager = ExternalStorageManager(config)
            with mock.patch("external_storage.discover_external_devices", return_value=[self.device(mount, free_mb=2048)]), mock.patch(
                "external_storage.check_storage", return_value={"ready": False, "low_space": True, "free_mb": 400, "reserve_mb": 512}
            ):
                manager._cycle()
                target = manager.capture_target()

            self.assertEqual(target["location"], "external")
            self.assertEqual(target["reason"], "local_low_space")
            self.assertTrue(source.exists())
            self.assertFalse((mount / "PiCameraData" / "photos" / source.name).exists())

    def test_external_preferred_migrates_local_fallback_then_deletes_verified_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            config.update({"storage_policy": "external_preferred", "local_reserve_mb": 512})
            source = Path(config["photo_dir"]) / "fallback.jpg"
            source.write_bytes(b"fallback")
            mount = root / "external"
            mount.mkdir()
            manager = ExternalStorageManager(config)
            with mock.patch("external_storage.discover_external_devices", return_value=[self.device(mount, free_mb=2048)]):
                manager._cycle()

            self.assertFalse(source.exists())
            self.assertEqual((mount / "PiCameraData" / "photos" / source.name).read_bytes(), b"fallback")

    def test_external_preferred_defers_photo_while_colony_analysis_is_pending(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            config.update({"storage_policy": "external_preferred", "local_reserve_mb": 512})
            source = Path(config["photo_dir"]) / "analysing.jpg"
            source.write_bytes(b"still in use")
            mount = root / "external"
            mount.mkdir()
            manager = ExternalStorageManager(config, is_source_busy=lambda path: path == source.resolve())
            with mock.patch("external_storage.discover_external_devices", return_value=[self.device(mount, free_mb=2048)]):
                manager._cycle()

            self.assertTrue(source.exists())
            self.assertFalse((mount / "PiCameraData" / "photos" / source.name).exists())

    def test_multiple_drives_use_earliest_seen_until_user_selects_uuid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            config.update({"storage_policy": "local_preferred", "local_reserve_mb": 512})
            first_mount = root / "first"
            second_mount = root / "second"
            first_mount.mkdir()
            second_mount.mkdir()
            first = self.device(first_mount, free_mb=2048)
            first["uuid"] = "FIRST"
            second = self.device(second_mount, free_mb=2048)
            second["uuid"] = "SECOND"
            manager = ExternalStorageManager(config)

            with mock.patch("external_storage.discover_external_devices", side_effect=[[first], [second, first], [second, first]]):
                manager._cycle()
                manager._cycle()
                self.assertEqual(manager.status()["device"]["uuid"], "FIRST")
                manager.update_config({**config, "external_device_uuid": "SECOND"})
                manager._cycle()
                self.assertEqual(manager.status()["device"]["uuid"], "SECOND")

    def test_manager_marks_selected_external_drive_near_safety_reserve(self):
        manager = ExternalStorageManager({"storage_policy": "local_preferred", "local_reserve_mb": 512})
        device = self.device(Path("/media/lab/LAB"), free_mb=400)
        with mock.patch("external_storage.discover_external_devices", return_value=[device]):
            manager._cycle()
        status = manager.status()
        self.assertTrue(status["connected"])
        self.assertTrue(status["low_space"])
        self.assertEqual(status["free_mb"], 400)
        self.assertEqual(status["reserve_mb"], 512)

    def test_external_status_exposes_capacity_and_its_own_photo_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.config(root)
            config.update({"storage_policy": "local_preferred", "local_reserve_mb": 512})
            mount = root / "external"
            photos = mount / "PiCameraData" / "photos"
            photos.mkdir(parents=True)
            (photos / "external-only.jpg").write_bytes(b"x" * 2048)
            manager = ExternalStorageManager(config)

            with mock.patch("external_storage.discover_external_devices", return_value=[self.device(mount, free_mb=2048)]):
                manager._cycle()

            status = manager.status()
            self.assertEqual(status["photo_count"], 1)
            self.assertEqual(status["photo_bytes"], 2048)
            self.assertEqual(status["average_photo_bytes"], 2048)
            self.assertGreater(status["estimated_remaining_photos"], 0)
            self.assertGreaterEqual(status["used_mb"], 0)
            self.assertGreaterEqual(status["used_percent"], 0)
            self.assertLessEqual(status["used_percent"], 100)

    @staticmethod
    def device(mount: Path, *, free_mb: int) -> dict:
        return {
            "path": "/dev/sda1", "filesystem": "ntfs", "mount_path": str(mount),
            "supported": True, "unformatted": False, "read_only": False, "uuid": "LAB",
            "size_bytes": 64 * 1024 * 1024 * 1024,
            "free_bytes": free_mb * 1024 * 1024,
        }


if __name__ == "__main__":
    unittest.main()
