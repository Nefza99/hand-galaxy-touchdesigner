"""
vocal_range_tracker.py
----------------------
Adaptively learns the user's personal vocal range over time so the pitch
normalisation stays accurate to the specific voice being detected.

Algorithm:
  - Collects confirmed voiced frames (confidence ≥ threshold).
  - Maintains a percentile-trimmed rolling buffer of Hz values.
  - Slowly expands and contracts the tracked min/max range.
  - Provides the updated range to PitchDetector.set_vocal_range().

The result is that a naturally low voice maps differently to band zones than
a naturally high voice — the system self-calibrates in ~30 seconds of use.

Usage::

    tracker = VocalRangeTracker()
    ...
    # each frame after getting PitchResult:
    low, high = tracker.update(pitch_result)
    detector.set_vocal_range(low, high)
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass


# ── constants ────────────────────────────────────────────────────────────────

_BUFFER_SIZE      = 512        # ~16 s of voiced frames at 512/16 000 block rate
_WARMUP_FRAMES    = 60         # frames before range is used
_LOW_PERCENTILE   = 5          # trim extreme outliers at both ends
_HIGH_PERCENTILE  = 95
_EXPAND_RATE      = 0.08       # alpha for expanding the range
_CONTRACT_RATE    = 0.003      # alpha for slow contraction toward measured range
_MIN_RANGE_HZ     = 80.0       # never compress range tighter than this
_ABSOLUTE_LOW     = 60.0       # floor — below this is rumble/noise
_ABSOLUTE_HIGH    = 1_300.0    # ceiling


@dataclass
class VocalRange:
    low:          float    # Hz lower bound (5th percentile)
    high:         float    # Hz upper bound (95th percentile)
    median:       float    # Hz median voiced pitch
    frames_seen:  int      # total voiced frames collected
    is_calibrated: bool    # True once warmup frames collected


class VocalRangeTracker:
    """
    Tracks the user's real-time vocal range.

    Call ``update(pitch_result)`` on each voiced frame.
    Read ``.range`` for the current calibrated range.
    """

    def __init__(
        self,
        buffer_size:    int   = _BUFFER_SIZE,
        warmup_frames:  int   = _WARMUP_FRAMES,
        initial_low:    float = 80.0,
        initial_high:   float = 1_100.0,
    ):
        self._buffer        = deque(maxlen=buffer_size)
        self._warmup_frames = warmup_frames
        self._frames_seen   = 0
        self._low           = float(initial_low)
        self._high          = float(initial_high)
        self._median        = (initial_low + initial_high) * 0.5
        self._last_update   = time.monotonic()

    # ── public ───────────────────────────────────────────────────────────────

    def update(self, hz: float, is_voiced: bool) -> VocalRange:
        """
        Feed one pitch sample.  Returns the current VocalRange.

        Args:
            hz:        Frequency in Hz.
            is_voiced: Whether the frame had sufficient confidence.
        """
        if is_voiced and _ABSOLUTE_LOW < hz < _ABSOLUTE_HIGH:
            self._buffer.append(hz)
            self._frames_seen += 1
            self._recompute()

        return self.range

    @property
    def range(self) -> VocalRange:
        return VocalRange(
            low           = self._low,
            high          = self._high,
            median        = self._median,
            frames_seen   = self._frames_seen,
            is_calibrated = self._frames_seen >= self._warmup_frames,
        )

    def reset(self) -> None:
        self._buffer.clear()
        self._frames_seen = 0

    # ── internal ─────────────────────────────────────────────────────────────

    def _recompute(self) -> None:
        if len(self._buffer) < 8:
            return

        sorted_hz = sorted(self._buffer)
        n = len(sorted_hz)

        # Percentile indices
        lo_idx = max(0, int(n * _LOW_PERCENTILE / 100))
        hi_idx = min(n - 1, int(n * _HIGH_PERCENTILE / 100))
        med_idx = n // 2

        measured_low    = sorted_hz[lo_idx]
        measured_high   = sorted_hz[hi_idx]
        measured_median = sorted_hz[med_idx]

        # Ensure minimum range
        if (measured_high - measured_low) < _MIN_RANGE_HZ:
            centre = (measured_low + measured_high) * 0.5
            measured_low  = centre - _MIN_RANGE_HZ * 0.5
            measured_high = centre + _MIN_RANGE_HZ * 0.5

        # Expand quickly when new data goes outside current range,
        # contract slowly toward the measured range.
        if measured_low < self._low:
            # Expand downward fast
            self._low = self._low + (measured_low - self._low) * _EXPAND_RATE
        else:
            # Contract upward slowly
            self._low = self._low + (measured_low - self._low) * _CONTRACT_RATE

        if measured_high > self._high:
            self._high = self._high + (measured_high - self._high) * _EXPAND_RATE
        else:
            self._high = self._high + (measured_high - self._high) * _CONTRACT_RATE

        self._low    = max(_ABSOLUTE_LOW,  self._low)
        self._high   = min(_ABSOLUTE_HIGH, self._high)
        self._median = measured_median
