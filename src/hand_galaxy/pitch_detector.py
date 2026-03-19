"""
pitch_detector.py
-----------------
Real-time pitch (fundamental frequency) detection using aubio YIN when
available, with a built-in numpy autocorrelation fallback for easy setup.
Registers itself as a consumer on the shared AudioPipeline so it never opens
a second mic stream.

Requires::

    pip install numpy
    pip install aubio   # optional, preferred backend

Aubio YIN is a fast C implementation (~0.3 ms per block at 512 frames).
If aubio is unavailable, the fallback uses a windowed autocorrelation estimate
so pitch still works on typical Windows installs without requiring build tools.
Confidence output is 0.0–1.0; values below 0.5 are treated as silence/noise.

Pitch is smoothed with an exponential moving average to remove transient
spikes without adding perceptible latency.

Usage::

    pipeline = AudioPipeline()
    detector = PitchDetector(pipeline)
    pipeline.start()

    # main loop:
    result = detector.latest
    print(result.hz, result.confidence, result.band)
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
import numpy as np

log = logging.getLogger(__name__)

# ── vocal frequency bands ────────────────────────────────────────────────────
# These map to atmospheric effect zones.  Tuned to a broad human vocal range
# that includes speech (100–300 Hz) and singing (80–1 100 Hz).

BAND_NAMES = ("void", "deep", "flowing", "radiant", "celestial")
BAND_THRESHOLDS = (0.0, 120.0, 250.0, 500.0, 800.0)  # Hz lower edges

# Normalised band index → atmosphere weights sent to TD
# band 0: sub/very-low  band 4: ultra-high


def hz_to_band(hz: float) -> int:
    """Return band index 0–4 for a given frequency in Hz."""
    for i in range(len(BAND_THRESHOLDS) - 1, -1, -1):
        if hz >= BAND_THRESHOLDS[i]:
            return i
    return 0


def hz_to_normalised(hz: float, low: float = 80.0, high: float = 1_100.0) -> float:
    """Return 0.0–1.0 position of ``hz`` within the detected vocal range."""
    if high <= low:
        return 0.5
    return max(0.0, min(1.0, (hz - low) / (high - low)))


# ── result dataclass ─────────────────────────────────────────────────────────

@dataclass
class PitchResult:
    hz:           float    # fundamental frequency in Hz (0 = silence)
    confidence:   float    # 0.0–1.0 from aubio
    band:         int      # 0–4 atmosphere zone
    normalised:   float    # 0.0–1.0 within detected vocal range
    velocity:     float    # Hz/s — rate of pitch change (positive = rising)
    is_voiced:    bool     # True if confidence ≥ threshold
    timestamp:    float    # time.monotonic()
    band_name:    str = "" # human-readable band

    def __post_init__(self):
        if not self.band_name and 0 <= self.band < len(BAND_NAMES):
            self.band_name = BAND_NAMES[self.band]


_SILENT = PitchResult(
    hz=0.0, confidence=0.0, band=0, normalised=0.0,
    velocity=0.0, is_voiced=False,
    timestamp=0.0, band_name=BAND_NAMES[0],
)


def _parabolic_offset(y_prev: float, y_peak: float, y_next: float) -> float:
    """Return a sub-sample peak offset in the range about -0.5..0.5."""
    denom = (y_prev - (2.0 * y_peak) + y_next)
    if abs(denom) < 1e-9:
        return 0.0
    return 0.5 * (y_prev - y_next) / denom


# ── main class ───────────────────────────────────────────────────────────────

class PitchDetector:
    """
    Detects pitch from shared AudioPipeline audio and exposes the latest
    result via the ``.latest`` property.

    Parameters
    ----------
    pipeline : AudioPipeline
        The shared mic source.  Must be started separately.
    sample_rate : int
        Must match ``pipeline.sample_rate``.
    confidence_threshold : float
        Frames below this are treated as silence.
    smoothing_alpha : float
        Exponential moving-average coefficient for Hz smoothing.
        Higher = faster response.  0.35 is a good real-time balance.
    vocal_low, vocal_high : float
        Starting Hz boundaries for normalisation.  Vocal range tracker
        can update these live.
    """

    def __init__(
        self,
        pipeline,
        sample_rate:          int   = 16_000,
        confidence_threshold: float = 0.50,
        smoothing_alpha:      float = 0.35,
        vocal_low:            float = 80.0,
        vocal_high:           float = 1_100.0,
    ):
        self._sample_rate          = sample_rate
        self._confidence_threshold = confidence_threshold
        self._smoothing_alpha      = smoothing_alpha
        self._vocal_low            = vocal_low
        self._vocal_high           = vocal_high

        self._hz_smooth    = 0.0
        self._hz_prev      = 0.0
        self._prev_time    = time.monotonic()
        self._velocity     = 0.0

        self._latest: PitchResult = _SILENT
        self._lock = threading.Lock()

        # Initialise aubio detector lazily on first audio block
        self._aubio_pitch = None
        self._aubio_ok    = False
        self._fallback_ok = False
        self._block_size  = pipeline.block_size

        pipeline.add_consumer("pitch", self._on_audio)
        self._init_aubio(pipeline.block_size, sample_rate)

    # ── public ───────────────────────────────────────────────────────────────

    @property
    def latest(self) -> PitchResult:
        with self._lock:
            return self._latest

    def set_vocal_range(self, low: float, high: float) -> None:
        """Update the normalisation range (called by VocalRangeTracker)."""
        self._vocal_low  = max(20.0, low)
        self._vocal_high = max(self._vocal_low + 50.0, high)

    @property
    def is_ready(self) -> bool:
        return self._aubio_ok or self._fallback_ok

    # ── internal ─────────────────────────────────────────────────────────────

    def _init_aubio(self, block_size: int, sample_rate: int) -> None:
        try:
            import aubio
            self._aubio_pitch = aubio.pitch(
                method="yin",
                buf_size=block_size * 4,   # analysis window = 4× hop
                hop_size=block_size,
                samplerate=sample_rate,
            )
            self._aubio_pitch.set_unit("Hz")
            self._aubio_pitch.set_silence(-40)   # dB floor
            self._aubio_pitch.set_tolerance(0.85)
            self._aubio_ok = True
            log.info("PitchDetector: aubio YIN ready  block=%d  sr=%d",
                     block_size, sample_rate)
        except ImportError:
            self._fallback_ok = True
            log.warning(
                "PitchDetector: aubio not installed — using numpy fallback."
            )
        except Exception as exc:                          # noqa: BLE001
            self._fallback_ok = True
            log.error("PitchDetector: aubio init error: %s", exc)
            log.info("PitchDetector: falling back to numpy autocorrelation.")

    def _prepare_samples(self, pcm_bytes: bytes) -> np.ndarray:
        samples = (
            np.frombuffer(pcm_bytes, dtype=np.int16)
            .astype(np.float32) / 32768.0
        )
        if len(samples) != self._block_size:
            if len(samples) < self._block_size:
                samples = np.pad(samples, (0, self._block_size - len(samples)))
            else:
                samples = samples[:self._block_size]
        return samples

    def _detect_pitch_fallback(self, samples: np.ndarray) -> tuple[float, float]:
        """
        Lightweight windowed autocorrelation pitch estimate.

        This is intentionally simple and dependency-free so pitch remains
        usable when aubio cannot be compiled on Windows.
        """
        if samples.size < 8:
            return 0.0, 0.0

        centered = samples - float(np.mean(samples))
        rms = float(np.sqrt(np.mean(centered * centered)))
        if rms < 0.008:
            return 0.0, 0.0

        windowed = centered * np.hanning(len(centered))
        corr = np.correlate(windowed, windowed, mode="full")[len(windowed) - 1:]
        if corr.size < 4 or corr[0] <= 1e-8:
            return 0.0, 0.0
        corr = corr / (corr[0] + 1e-9)

        max_hz = max(self._vocal_high, 120.0)
        min_hz = max(40.0, min(self._vocal_low, max_hz - 20.0))
        min_lag = max(1, int(self._sample_rate / max_hz))
        max_lag = min(len(corr) - 2, int(self._sample_rate / min_hz))
        if max_lag <= min_lag:
            return 0.0, 0.0

        search = corr[min_lag:max_lag + 1]
        if search.size < 3:
            return 0.0, 0.0

        peak_candidates = (
            np.flatnonzero(
                (search[1:-1] > search[:-2]) &
                (search[1:-1] >= search[2:])
            ) + 1
        )
        if peak_candidates.size == 0:
            peak_rel = int(np.argmax(search))
        else:
            strong = peak_candidates[search[peak_candidates] >= 0.30]
            choice = strong if strong.size else peak_candidates
            peak_rel = int(choice[np.argmax(search[choice])])

        peak_value = float(search[peak_rel])
        if peak_value < 0.18:
            return 0.0, 0.0

        refine = 0.0
        if 0 < peak_rel < search.size - 1:
            refine = _parabolic_offset(
                float(search[peak_rel - 1]),
                float(search[peak_rel]),
                float(search[peak_rel + 1]),
            )
            refine = max(-0.5, min(0.5, refine))

        lag = min_lag + peak_rel + refine
        if lag <= 0.0:
            return 0.0, 0.0

        hz = self._sample_rate / lag
        if not (20.0 <= hz <= max(self._vocal_high * 1.25, 1_200.0)):
            return 0.0, 0.0

        zc = float(
            np.mean(np.signbit(windowed[1:]) != np.signbit(windowed[:-1]))
        ) if len(windowed) > 1 else 0.0
        periodicity = max(0.0, min(1.0, (peak_value - 0.18) / 0.82))
        energy = max(0.0, min(1.0, rms / 0.08))
        stability = max(0.0, min(1.0, 1.2 - (zc * 2.0)))
        confidence = (
            periodicity * 0.70
            + energy * 0.20
            + stability * 0.10
        )
        return hz, confidence

    def _on_audio(self, pcm_bytes: bytes, frames: int) -> None:
        """AudioPipeline consumer callback — called from capture thread."""
        if not self.is_ready:
            return

        try:
            samples = self._prepare_samples(pcm_bytes)
            if self._aubio_ok and self._aubio_pitch is not None:
                raw_hz = float(self._aubio_pitch(samples)[0])
                conf   = float(self._aubio_pitch.get_confidence())
            else:
                raw_hz, conf = self._detect_pitch_fallback(samples)

            now = time.monotonic()
            dt  = max(now - self._prev_time, 1e-4)
            self._prev_time = now

            is_voiced = conf >= self._confidence_threshold and raw_hz > 20.0

            if is_voiced:
                # Exponential smoothing on Hz
                alpha = self._smoothing_alpha
                self._hz_smooth = (
                    self._hz_smooth * (1.0 - alpha) + raw_hz * alpha
                )
                # Velocity (Hz/s)
                self._velocity = (
                    self._velocity * 0.7
                    + ((self._hz_smooth - self._hz_prev) / dt) * 0.3
                )
                self._hz_prev = self._hz_smooth
            else:
                # Decay toward silence quickly
                self._hz_smooth *= 0.85
                self._velocity  *= 0.6
                if self._hz_smooth < 20.0:
                    self._hz_smooth = 0.0

            band = hz_to_band(self._hz_smooth) if is_voiced else 0
            norm = hz_to_normalised(
                self._hz_smooth, self._vocal_low, self._vocal_high
            )

            result = PitchResult(
                hz         = self._hz_smooth,
                confidence = conf,
                band       = band,
                normalised = norm,
                velocity   = self._velocity,
                is_voiced  = is_voiced,
                timestamp  = now,
            )
            with self._lock:
                self._latest = result

        except Exception as exc:                         # noqa: BLE001
            log.debug("PitchDetector._on_audio error: %s", exc)


# ── stub ─────────────────────────────────────────────────────────────────────

class PitchDetectorStub:
    """No-op fallback when audio capture is unavailable."""

    def __init__(self, *_, **__):
        pass

    @property
    def latest(self) -> PitchResult:
        return _SILENT

    @property
    def is_ready(self) -> bool:
        return False

    def set_vocal_range(self, *_) -> None:
        pass


def make_pitch_detector(pipeline, **kwargs) -> PitchDetector | PitchDetectorStub:
    if pipeline is None:
        return PitchDetectorStub()
    return PitchDetector(pipeline, **kwargs)
