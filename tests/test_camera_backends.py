from __future__ import annotations

import subprocess
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from camera_backends import RpicamStillBackend, create_backend


class RpicamStillBackendTests(unittest.TestCase):
    def test_stream_start_broken_pipe_retries_once_and_keeps_diagnostic(self):
        error = 'Failed to start streaming: Broken pipe\nERROR: *** failed to start camera ***'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'capture.tmp.jpg'
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                if len(calls) == 1:
                    output.write_bytes(b'partial')
                    return subprocess.CompletedProcess(command, 1, stdout='', stderr=error)
                self.assertFalse(output.exists())
                output.write_bytes(b'new-photo')
                return subprocess.CompletedProcess(command, 0, stdout='{}', stderr='')

            with patch('camera_backends.subprocess.run', side_effect=run), patch('camera_backends.time.sleep') as sleep:
                result = RpicamStillBackend().capture(output, 1000)
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0], calls[1])
            self.assertEqual(result['recovery_errors'], [error])
            self.assertEqual(output.read_bytes(), b'new-photo')
            sleep.assert_called_once_with(1)

    def test_persistent_broken_pipe_still_reports_failure(self):
        error = 'Failed to start streaming: Broken pipe\nERROR: *** failed to start camera ***'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'capture.tmp.jpg'
            with patch('camera_backends.subprocess.run', return_value=subprocess.CompletedProcess([], 1, '', error)) as run, patch('camera_backends.time.sleep'):
                with self.assertRaisesRegex(RuntimeError, 'Broken pipe'):
                    RpicamStillBackend().capture(output, 1000)
                self.assertEqual(run.call_count, 2)

    def test_other_camera_failures_are_not_retried(self):
        with patch('camera_backends.subprocess.run', return_value=subprocess.CompletedProcess([], 1, '', 'no cameras available')) as run:
            with self.assertRaisesRegex(RuntimeError, 'no cameras'):
                RpicamStillBackend().capture(Path('unused.jpg'), 1000)
            self.assertEqual(run.call_count, 1)

    def test_capture_triggers_center_weighted_autofocus_before_still(self):
        config = {
            "mock_camera": False,
            "autofocus_mode": "auto",
            "autofocus_range": "full",
            "autofocus_window": "0.25,0.25,0.5,0.5",
            "autofocus_on_capture": True,
            "autofocus_min_preview_ms": 3000,
        }
        backend = create_backend(config)
        self.assertIsInstance(backend, RpicamStillBackend)

        output = Path("focused.jpg")

        def fake_run(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout='{"AfState":3,"LensPosition":9.5}', stderr="")

        with (
            patch("camera_backends.subprocess.run", side_effect=fake_run) as run,
            patch("camera_backends.Path.exists", return_value=True),
            patch("camera_backends.Path.stat", return_value=SimpleNamespace(st_size=4)),
        ):
            result = backend.capture(output, timeout_ms=1000)
            self.assertEqual(result["camera_metadata"]["AfState"], 3)

        command = run.call_args.args[0]
        self.assertEqual(command[0], "rpicam-still")
        self.assertEqual(command[command.index("--timeout") + 1], "3000")
        self.assertEqual(command[command.index("--autofocus-mode") + 1], "auto")
        self.assertEqual(command[command.index("--autofocus-range") + 1], "full")
        self.assertEqual(command[command.index("--autofocus-window") + 1], "0.25,0.25,0.5,0.5")
        self.assertIn("--autofocus-on-capture", command)
        self.assertIn("--zsl", command)
        self.assertIn("--metadata", command)


if __name__ == "__main__":
    unittest.main()
