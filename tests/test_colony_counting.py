from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
import sqlite3
from contextlib import closing
from pathlib import Path

from colony_counting import parse_mcount_output, parse_opencfu_output
from history_store import (
    colony_results_by_filename,
    export_photo_history_csv,
    informative_photo_filename,
    photo_history_summary,
    photo_history_by_filename,
    photo_timestamp_from_filename,
    query_colony_results,
    query_photo_history,
    record_colony_result,
    record_sensor_sample,
)


class AnalysisDiagnosticEventTests(unittest.TestCase):
    def test_each_failure_gets_a_new_durable_event(self):
        from colony_counting import ColonyCountingWorker
        with tempfile.TemporaryDirectory() as directory:
            photo = Path(directory) / "plate.jpg"
            photo.write_bytes(b"fixture")
            config = {"history_db_path": str(Path(directory) / "history.sqlite3"), "colony_count_backends": ["mcount"]}
            worker = ColonyCountingWorker(config)
            def fail(*args):
                raise RuntimeError("test timeout")
            with patch.dict("colony_counting.BACKEND_RUNNERS", {"mcount": fail}):
                worker._analyze(photo, force=True)
                first = worker.status()["last_error_id"]
                worker._analyze(photo, force=True)
            self.assertNotEqual(first, worker.status()["last_error_id"])
            with closing(sqlite3.connect(config["history_db_path"])) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM events WHERE event_type='analysis_error' AND ok=0").fetchone()[0], 2)


class ColonyBackendOutputTests(unittest.TestCase):
    def test_opencfu_counts_only_valid_rows(self):
        output = """IsValid,X,Y,ROI,N_in_clust\n1,10,20,1,1\n0,30,40,0,2\n1,50,60,1,3\n"""
        result = parse_opencfu_output(output)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["candidate_count"], 3)

    def test_mcount_parses_cli_summary(self):
        output = '{"backend":"mcount","status":"ok","count":17,"duration_seconds":0.256}'
        result = parse_mcount_output(output)
        self.assertEqual(result["count"], 17)
        self.assertEqual(result["status"], "ok")


class ColonyResultStoreTests(unittest.TestCase):
    def test_results_are_upserted_per_photo_and_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {"history_db_path": str(Path(directory) / "history.sqlite3")}
            record_colony_result(
                config,
                filename="plate.jpg",
                photo_timestamp="2026-08-14T22:00:00",
                backend="opencfu",
                status="ok",
                count=41,
                duration_seconds=0.5,
                details={"candidate_count": 44},
            )
            record_colony_result(
                config,
                filename="plate.jpg",
                photo_timestamp="2026-08-14T22:00:00",
                backend="opencfu",
                status="ok",
                count=42,
                duration_seconds=0.4,
                details={"candidate_count": 45},
            )
            record_colony_result(
                config,
                filename="plate.jpg",
                photo_timestamp="2026-08-14T22:00:00",
                backend="mcount",
                status="ok",
                count=39,
                duration_seconds=0.2,
                details={"lambda": 30.0},
            )

            rows = query_colony_results(config)
            self.assertEqual(len(rows), 2)
            by_photo = colony_results_by_filename(config, ["plate.jpg"])
            self.assertEqual(by_photo["plate.jpg"]["opencfu"]["count"], 42)
            self.assertEqual(by_photo["plate.jpg"]["mcount"]["count"], 39)
            self.assertEqual(by_photo["plate.jpg"]["mcount"]["status"], "ok")

    def test_photo_history_ignores_unlinked_periodic_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {"history_db_path": str(Path(directory) / "history.sqlite3")}
            hardware = {
                "sensors": {
                    "sensors": [
                        {"temperature_c": 24.5, "humidity_percent": 51.0, "status": "ok"},
                        {"temperature_c": 24.8, "humidity_percent": 50.5, "status": "ok"},
                    ],
                    "delta": {"temperature_delta_c": 0.3, "humidity_delta_percent_points": 0.5},
                }
            }
            record_sensor_sample(config, hardware)
            filename = "2026-08-14_09-05-07.jpg"
            record_sensor_sample(config, hardware, photo_filename=filename)
            record_colony_result(
                config,
                filename=filename,
                photo_timestamp="2026-08-14T09:05:07",
                backend="opencfu",
                status="ok",
                count=37,
                duration_seconds=0.5,
            )

            records = query_photo_history(config)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["timestamp"], "2026-08-14T09:05:07")
            self.assertEqual(records[0]["sensor_a_temp_c"], 24.5)
            self.assertEqual(records[0]["counts"]["opencfu"]["count"], 37)
            csv_text = export_photo_history_csv(config)
            self.assertIn("2026-08-14T09:05:07", csv_text)
            self.assertIn(",37,ok,", csv_text)

    def test_photo_timestamp_comes_from_filename(self):
        self.assertEqual(
            photo_timestamp_from_filename("2026-08-14_09-05-07_001.jpg"),
            "2026-08-14T09:05:07",
        )

    def test_photo_history_auto_query_returns_latest_records_and_exact_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {"history_db_path": str(Path(directory) / "history.sqlite3")}
            hardware = {
                "sensors": {
                    "sensors": [
                        {"temperature_c": 24.0, "humidity_percent": 50.0, "status": "ok"},
                        {"temperature_c": 24.2, "humidity_percent": 49.8, "status": "ok"},
                    ]
                }
            }
            for hour in range(5):
                record_sensor_sample(config, hardware, photo_filename=f"2026-08-14_{hour:02d}-00-00.jpg")

            summary = photo_history_summary(config)
            records = query_photo_history(config, limit=2, newest=True)

            self.assertEqual(summary["total"], 5)
            self.assertEqual(summary["start"], "2026-08-14T00:00:00")
            self.assertEqual(summary["end"], "2026-08-14T04:00:00")
            self.assertEqual([record["filename"] for record in records], [
                "2026-08-14_03-00-00.jpg",
                "2026-08-14_04-00-00.jpg",
            ])

    def test_informative_download_name_uses_capture_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {"history_db_path": str(Path(directory) / "history.sqlite3")}
            filename = "2026-08-14_09-05-07.jpg"
            hardware = {
                "sensors": {
                    "sensors": [
                        {"temperature_c": 24.5, "humidity_percent": 51.0, "status": "ok"},
                        {"temperature_c": 24.9, "humidity_percent": 50.6, "status": "ok"},
                    ]
                }
            }
            record_sensor_sample(config, hardware, photo_filename=filename)
            record_colony_result(
                config,
                filename=filename,
                photo_timestamp="2026-08-14T09:05:07",
                backend="opencfu",
                status="ok",
                count=37,
                duration_seconds=0.5,
            )
            record_colony_result(
                config,
                filename=filename,
                photo_timestamp="2026-08-14T09:05:07",
                backend="mcount",
                status="ok",
                count=39,
                duration_seconds=0.2,
            )

            metadata = photo_history_by_filename(config, [filename])[filename]
            self.assertEqual(
                informative_photo_filename(filename, metadata),
                "20260814-090507_O37_M39_T24.7_H50.8.jpg",
            )

    def test_informative_download_name_distinguishes_missing_and_error(self):
        filename = "2026-08-14_09-05-07_001.JPG"
        metadata = {
            "sensor_a_temp_c": None,
            "sensor_b_temp_c": 23.25,
            "sensor_a_humidity_percent": None,
            "sensor_b_humidity_percent": 48,
            "counts": {"mcount": {"status": "error", "count": None}},
        }
        self.assertEqual(
            informative_photo_filename(filename, metadata),
            "20260814-090507-001_ONA_MERR_T23.2_H48.0.jpg",
        )


if __name__ == "__main__":
    unittest.main()
