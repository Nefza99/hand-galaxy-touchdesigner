from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AudioFeatures:
    amplitude: float = 0.0
    peak: float = 0.0
    decibels: float = -80.0
    pulse: float = 0.0
    active: bool = False
    timestamp: float = 0.0


class AudioFeatureTracker:
    def __init__(
        self,
        pipeline,
        attack: float = 0.30,
        release: float = 0.08,
        activity_threshold: float = 0.015,
    ):
        self._attack = attack
        self._release = release
        self._activity_threshold = activity_threshold
        self._latest = AudioFeatures()
        self._lock = threading.Lock()
        pipeline.add_consumer("amplitude", self._on_audio)

    @property
    def latest(self) -> AudioFeatures:
        with self._lock:
            return self._latest

    def _on_audio(self, pcm_bytes: bytes, frames: int) -> None:
        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return
        samples /= 32768.0
        rms = float(np.sqrt(np.mean(samples * samples)))
        peak = float(np.max(np.abs(samples)))
        previous = self._latest.amplitude
        alpha = self._attack if rms >= previous else self._release
        amplitude = previous + (rms - previous) * alpha
        pulse = max(0.0, rms - previous) * 8.0
        decibels = 20.0 * math.log10(max(rms, 1e-5))
        features = AudioFeatures(
            amplitude=max(0.0, min(1.0, amplitude / 0.30)),
            peak=max(0.0, min(1.0, peak)),
            decibels=max(-80.0, min(6.0, decibels)),
            pulse=max(0.0, min(1.0, pulse)),
            active=rms >= self._activity_threshold,
            timestamp=time.monotonic(),
        )
        with self._lock:
            self._latest = features
