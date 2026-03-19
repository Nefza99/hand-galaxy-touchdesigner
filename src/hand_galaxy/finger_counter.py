"""
finger_counter.py
-----------------
Counts extended fingers on one or two hands using MediaPipe landmark data.

Landmark indices (MediaPipe Hand):
  Wrist      : 0
  Thumb      : CMC=1, MCP=2, IP=3, TIP=4
  Index      : MCP=5, PIP=6, DIP=7, TIP=8
  Middle     : MCP=9, PIP=10, DIP=11, TIP=12
  Ring       : MCP=13, PIP=14, DIP=15, TIP=16
  Pinky      : MCP=17, PIP=18, DIP=19, TIP=20
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field


# Landmark indices
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

_FINGER_PAIRS = [
    (INDEX_TIP, INDEX_PIP),
    (MIDDLE_TIP, MIDDLE_PIP),
    (RING_TIP, RING_PIP),
    (PINKY_TIP, PINKY_PIP),
]


def _dist2d(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def count_extended_fingers(
    landmarks: tuple[tuple[float, float, float], ...],
    hand_label: str,
) -> int:
    """
    Count extended fingers for a single hand.

    Args:
        landmarks: 21 (x, y, z) normalised landmarks from MediaPipe.
        hand_label: "Left" or "Right" as reported by MediaPipe.
                    When mirror=True (default), MediaPipe flips left/right,
                    so "Left" == user's physical right hand.

    Returns:
        int 0–5.
    """
    if len(landmarks) < 21:
        return 0

    count = 0

    # --- Four non-thumb fingers -----------------------------------------------
    # Extended if TIP is above (smaller y) the PIP joint.
    # We also require a minimum vertical gap to avoid noise near half-curl.
    for tip_idx, pip_idx in _FINGER_PAIRS:
        tip_y = landmarks[tip_idx][1]
        pip_y = landmarks[pip_idx][1]
        mcp_idx = pip_idx - 1  # MCP is one index below PIP
        mcp_y = landmarks[mcp_idx][1]
        hand_height = abs(landmarks[WRIST][1] - mcp_y) + 1e-6
        margin = hand_height * 0.12  # 12% of knuckle height
        if (tip_y + margin) < pip_y:
            count += 1

    # --- Thumb ----------------------------------------------------------------
    # Thumb extension is detected laterally (x-axis), not vertically.
    # With mirror=True:
    #   MediaPipe "Left"  → camera-left hand → thumb abducts to the LEFT  → tip.x < IP.x
    #   MediaPipe "Right" → camera-right hand → thumb abducts to the RIGHT → tip.x > IP.x
    thumb_tip = landmarks[THUMB_TIP]
    thumb_ip = landmarks[THUMB_IP]
    thumb_mcp = landmarks[THUMB_MCP]

    # Fall back to distance check if x-delta is ambiguous (palm-down poses)
    x_delta = thumb_tip[0] - thumb_ip[0]
    hand_width = _dist2d(landmarks[INDEX_MCP], landmarks[PINKY_MCP]) + 1e-6
    threshold = hand_width * 0.08

    if hand_label == "Left":
        extended = x_delta < -threshold
    else:
        extended = x_delta > threshold

    # Additional check: tip further from wrist than MCP (catches side-on hands)
    dist_tip_wrist = _dist2d(thumb_tip, landmarks[WRIST])
    dist_mcp_wrist = _dist2d(thumb_mcp, landmarks[WRIST])
    if dist_tip_wrist > dist_mcp_wrist * 1.25:
        extended = True

    if extended:
        count += 1

    return count


@dataclass
class FingerCountState:
    """Smoothed, debounced finger count with timeout-to-zero."""
    window_size: int = 6           # frames for majority vote
    hand_timeout_ms: int = 300     # ms before count drops to 0
    _history: deque = field(default_factory=lambda: deque(maxlen=6))
    _last_seen_ms: int = 0
    _displayed_count: int = 0

    def update(
        self,
        raw_count: int,
        hands_active: bool,
        timestamp_ms: int,
    ) -> int:
        """
        Feed a raw count and return the smoothed display value.

        Args:
            raw_count:    0–10 as computed this frame.
            hands_active: whether any hand is currently visible.
            timestamp_ms: current timestamp.

        Returns:
            Smoothed finger count 0–10.
        """
        if hands_active:
            self._last_seen_ms = timestamp_ms
            # Resize history if window_size changed
            if self._history.maxlen != self.window_size:
                self._history = deque(self._history, maxlen=self.window_size)
            self._history.append(raw_count)
        else:
            elapsed = timestamp_ms - self._last_seen_ms if self._last_seen_ms else self.hand_timeout_ms + 1
            if elapsed > self.hand_timeout_ms:
                self._history.clear()
                self._displayed_count = 0
                return 0

        if not self._history:
            return 0

        # Majority vote across the window
        from collections import Counter
        vote = Counter(self._history).most_common(1)[0][0]
        self._displayed_count = vote
        return vote

    @property
    def current(self) -> int:
        return self._displayed_count


class FingerCounter:
    """
    High-level wrapper: accepts a GestureFrame and returns the smoothed
    total finger count plus per-hand counts.
    """

    def __init__(self, window_size: int = 6, hand_timeout_ms: int = 300):
        self._state = FingerCountState(
            window_size=window_size,
            hand_timeout_ms=hand_timeout_ms,
        )

    def process(self, frame) -> dict:
        """
        Args:
            frame: GestureFrame from GestureEngine.

        Returns:
            dict with keys:
              total       int  0–10
              primary     int  0–5
              secondary   int  0–5
              hands_active bool
        """
        primary_count = 0
        secondary_count = 0
        hands_active = False

        if frame.primary.active and frame.primary.landmarks:
            primary_count = count_extended_fingers(
                frame.primary.landmarks,
                frame.primary.label,
            )
            hands_active = True

        if frame.secondary.active and frame.secondary.landmarks:
            secondary_count = count_extended_fingers(
                frame.secondary.landmarks,
                frame.secondary.label,
            )
            hands_active = True

        raw_total = primary_count + secondary_count
        smoothed = self._state.update(raw_total, hands_active, frame.timestamp_ms)

        return {
            "total": smoothed,
            "primary": primary_count,
            "secondary": secondary_count,
            "hands_active": hands_active,
        }
