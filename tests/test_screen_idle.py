from __future__ import annotations

import unittest

from config_store import DEFAULT_CONFIG, _coerce_config
from screen_idle import display_names


class ScreenIdleTests(unittest.TestCase):
    def test_default_timeout_is_one_minute(self):
        self.assertEqual(DEFAULT_CONFIG["screen_idle_timeout_seconds"], 60)

    def test_timeout_is_clamped_and_zero_disables_blanking(self):
        config = _coerce_config({"screen_idle_timeout_seconds": -5})
        self.assertEqual(config["screen_idle_timeout_seconds"], 0)
        config = _coerce_config({"screen_idle_timeout_seconds": 999999})
        self.assertEqual(config["screen_idle_timeout_seconds"], 86400)

    def test_wayland_output_names_are_parsed(self):
        self.assertEqual(display_names("DSI-2 on\nHDMI-A-1 off\n"), ["DSI-2", "HDMI-A-1"])

    def test_external_storage_settings_are_safely_coerced(self):
        config = _coerce_config({
            "storage_policy": "unknown",
            "local_reserve_mb": 0,
            "external_sync_interval_seconds": 1,
            "external_data_dir_name": "../unsafe/path",
            "local_cleanup_policy": "delete_everything",
            "local_cleanup_days": -1,
        })
        self.assertEqual(config["storage_policy"], "local_preferred")
        self.assertEqual(config["local_reserve_mb"], 512)
        self.assertEqual(config["external_data_dir_name"], "path")
        self.assertNotIn("external_sync_interval_seconds", config)
        self.assertNotIn("local_cleanup_policy", config)
        self.assertNotIn("local_cleanup_days", config)

    def test_legacy_local_only_policy_migrates_to_local_preferred(self):
        config = _coerce_config({"storage_policy": "local_only"})
        self.assertEqual(config["storage_policy"], "local_preferred")


if __name__ == "__main__":
    unittest.main()
