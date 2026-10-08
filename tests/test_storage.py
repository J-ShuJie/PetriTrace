from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from storage import check_storage, list_photos, photo_file_summary, safe_photo_path


class StorageSummaryTests(unittest.TestCase):
    def test_external_archive_is_used_when_local_copy_was_cleaned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            local = root / "local"
            external = root / "external"
            local.mkdir()
            external.mkdir()
            archived = external / "plate.jpg"
            archived.write_bytes(b"external copy")
            config = {"photo_dir": str(local), "max_recent_photos": 100}

            photos = list_photos(config, limit=0, additional_dirs=[external])

            self.assertEqual([item["filename"] for item in photos], ["plate.jpg"])
            self.assertEqual(photos[0]["storage_location"], "external")
            self.assertEqual(safe_photo_path(config, "plate.jpg", [external]), archived)

    def test_photo_summary_counts_only_supported_source_photos(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "first.jpg").write_bytes(b"a" * 100)
            (directory / "second.png").write_bytes(b"b" * 300)
            (directory / "notes.txt").write_text("ignored", encoding="utf-8")
            (directory / ".thumbnails").mkdir()

            summary = photo_file_summary(directory)

            self.assertEqual(summary["photo_count"], 2)
            self.assertEqual(summary["photo_bytes"], 400)
            self.assertEqual(summary["average_photo_bytes"], 200)

    def test_storage_status_exposes_persistent_count_and_capacity_estimate(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "photos"
            directory.mkdir()
            (directory / "capture.jpg").write_bytes(b"x" * 1024)
            config = {
                "photo_dir": str(directory),
                "thumbnail_dir": str(directory / ".thumbnails"),
                "require_external_mount": False,
                "storage_low_space_mb": 0,
            }

            status = check_storage(config)

            self.assertTrue(status["ready"])
            self.assertEqual(status["photo_count"], 1)
            self.assertEqual(status["average_photo_bytes"], 1024)
            self.assertGreaterEqual(status["total_mb"], status["used_mb"])
            self.assertGreater(status["estimated_remaining_photos"], 0)
            self.assertEqual(status["reserve_mb"], 0)
            self.assertGreaterEqual(status["used_percent"], 0)
            self.assertLessEqual(status["used_percent"], 100)

            with mock.patch("storage.os.scandir", side_effect=AssertionError("summary cache was not reused")):
                cached_status = check_storage(config)
            self.assertEqual(cached_status["photo_count"], 1)


if __name__ == "__main__":
    unittest.main()
