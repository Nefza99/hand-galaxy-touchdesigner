from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from installer import launch_helper
from hand_galaxy.pitch_detector import PitchDetector, PitchResult
from hand_galaxy.pitch_effect_mapper import PitchEffectMapper


class _FakePipeline:
    def __init__(self, block_size: int = 512):
        self.block_size = block_size
        self.consumer = None

    def add_consumer(self, name: str, callback) -> None:
        self.consumer = callback


class AudioAndLaunchTests(unittest.TestCase):
    def test_numpy_pitch_fallback_detects_sine_wave(self) -> None:
        pipeline = _FakePipeline()
        detector = PitchDetector(
            pipeline,
            sample_rate=16_000,
            confidence_threshold=0.35,
            smoothing_alpha=1.0,
            vocal_low=80.0,
            vocal_high=1_100.0,
        )
        detector._aubio_ok = False
        detector._aubio_pitch = None
        detector._fallback_ok = True

        freq_hz = 220.0
        block = np.arange(pipeline.block_size, dtype=np.float32) / 16_000.0
        wave = 0.55 * np.sin(2.0 * np.pi * freq_hz * block)
        pcm = (wave * 32767.0).astype(np.int16).tobytes()

        for _ in range(8):
            detector._prev_time = time.monotonic() - 0.032
            detector._on_audio(pcm, pipeline.block_size)

        latest = detector.latest
        self.assertTrue(latest.is_voiced)
        self.assertAlmostEqual(latest.hz, freq_hz, delta=18.0)
        self.assertGreater(latest.confidence, 0.45)
        self.assertEqual(latest.band, 1)

    def test_pitch_effect_mapper_emits_radiant_celestial_values(self) -> None:
        mapper = PitchEffectMapper(hue_alpha=1.0, param_alpha=1.0, velocity_gain=0.001)
        pitch = PitchResult(
            hz=920.0,
            confidence=0.92,
            band=4,
            normalised=0.88,
            velocity=420.0,
            is_voiced=True,
            timestamp=time.monotonic(),
        )
        mapper.update(pitch)
        params = mapper.update(pitch)
        self.assertEqual(params.band, 4)
        self.assertGreater(params.bloom, 0.9)
        self.assertGreater(params.shimmer, 0.7)
        self.assertGreaterEqual(params.burst_coefficient, 0.14)

    def test_launch_helper_keeps_pitch_enabled_with_numpy_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "models" / "vosk" / "vosk-model-small-en-us-0.15").mkdir(parents=True)
            python_exe = root / "python.exe"
            python_exe.write_text("", encoding="utf-8")

            with (
                patch.object(launch_helper, "ROOT", root),
                patch.object(launch_helper, "PYTHON", python_exe),
                patch.object(
                    launch_helper,
                    "can_import",
                    side_effect=lambda mod: {
                        "pyaudio": True,
                        "vosk": True,
                        "aubio": False,
                    }.get(mod, True),
                ),
                patch("installer.launch_helper.subprocess.call", return_value=0) as call_mock,
            ):
                rc = launch_helper.main([])

            self.assertEqual(rc, 0)
            command = call_mock.call_args.args[0]
            self.assertNotIn("--no-pitch", command)
            self.assertNotIn("--no-speech", command)

    def test_launch_helper_disables_audio_features_without_pyaudio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            python_exe = root / "python.exe"
            python_exe.write_text("", encoding="utf-8")

            with (
                patch.object(launch_helper, "ROOT", root),
                patch.object(launch_helper, "PYTHON", python_exe),
                patch.object(
                    launch_helper,
                    "can_import",
                    side_effect=lambda mod: {
                        "pyaudio": False,
                        "vosk": True,
                        "aubio": False,
                    }.get(mod, True),
                ),
                patch("installer.launch_helper.subprocess.call", return_value=0) as call_mock,
            ):
                rc = launch_helper.main([])

            self.assertEqual(rc, 0)
            command = call_mock.call_args.args[0]
            self.assertIn("--no-speech", command)
            self.assertIn("--no-pitch", command)


if __name__ == "__main__":
    unittest.main()
