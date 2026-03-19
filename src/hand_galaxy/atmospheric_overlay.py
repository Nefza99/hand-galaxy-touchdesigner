"""
atmospheric_overlay.py
----------------------
Real-time OpenCV-based atmospheric overlay effects driven by pitch band.

Five layered effects, each pre-computed at a fast tile resolution and then
upscaled — so they run at ~0.5 ms per frame rather than per-pixel cost.

Effects:
  VOID       : heavy black vignette + dark billowing fog tendrils
  DEEP       : violet nebula haze with slow particle drift
  FLOWING    : faint aurora shimmer across the upper third
  RADIANT    : warm corona bloom radiating from centre
  CELESTIAL  : full-screen crystal sparkle + lens shimmer

All effects are blended on top of the existing frame at their current
intensity (ColourState.vignette / shimmer / fog / bloom) so they never
fully override the camera or galaxy art.
"""
from __future__ import annotations

import math
import time
from typing import Optional

import cv2
import numpy as np


# ── noise helpers ──────────────────────────────────────────────────────────

def _simplex_approx(w: int, h: int, scale: float, t: float) -> np.ndarray:
    """
    Fast perlin-ish noise field via stacked sin/cos.
    Returns float32 array in [0, 1], shape (h, w).
    """
    xs = np.linspace(0, scale, w, dtype=np.float32)
    ys = np.linspace(0, scale, h, dtype=np.float32)
    xg, yg = np.meshgrid(xs, ys)
    n = (
        np.sin(xg * 1.0 + t * 0.7) * np.cos(yg * 0.8 + t * 0.5)
        + np.sin(xg * 2.3 - t * 0.4) * np.cos(yg * 1.9 + t * 0.3) * 0.5
        + np.sin(xg * 4.1 + t * 0.9) * np.cos(yg * 3.7 - t * 0.6) * 0.25
    )
    # Normalise to 0–1
    n = (n - n.min()) / (n.max() - n.min() + 1e-6)
    return n.astype(np.float32)


def _vignette_mask(h: int, w: int, strength: float) -> np.ndarray:
    """Returns a float32 alpha mask 0–1 (1 = no darkening, 0 = black)."""
    cx, cy = w * 0.5, h * 0.5
    xs = (np.arange(w) - cx) / cx
    ys = (np.arange(h) - cy) / cy
    xg, yg = np.meshgrid(xs, ys)
    dist = np.sqrt(xg ** 2 + yg ** 2).astype(np.float32)
    mask = 1.0 - np.clip(dist * strength, 0.0, 1.0)
    return mask


# ── tile resolution (upscaled for speed) ───────────────────────────────────
_TILE_W = 160
_TILE_H = 90


class AtmosphericOverlay:
    """
    Call ``draw(frame, colour_state, dt)`` every frame.
    Internally caches and animates each effect layer.
    """

    def __init__(self):
        self._t = 0.0
        # Pre-cache the vignette mask at full resolution per resize
        self._vignette_cache: Optional[tuple[tuple[int, int], float, np.ndarray]] = None
        # Sparkle positions for celestial (randomised once, animated by brightness)
        self._sparkle_xy: Optional[np.ndarray] = None
        self._sparkle_phase: Optional[np.ndarray] = None

    # ── public ───────────────────────────────────────────────────────────────

    def draw(self, frame: np.ndarray, colour_state, dt: float) -> None:
        """
        Composite all atmospheric effects onto ``frame`` in-place.

        Args:
            frame:        BGR uint8 OpenCV frame.
            colour_state: ColourState from EffectColourState.
            dt:           frame delta time in seconds.
        """
        self._t += dt
        h, w = frame.shape[:2]

        cs = colour_state

        # ── 1. Vignette (all bands, scaled by cs.vignette) ─────────────────
        if cs.vignette > 0.02:
            self._draw_vignette(frame, h, w, cs.vignette)

        # ── 2. Fog tendrils (VOID + DEEP) ──────────────────────────────────
        if cs.fog > 0.02:
            self._draw_fog(frame, h, w, cs)

        # ── 3. Aurora shimmer (FLOWING) ────────────────────────────────────
        if 0.03 < cs.shimmer < 0.45 and cs.band in (1, 2):
            self._draw_aurora(frame, h, w, cs)

        # ── 4. Corona bloom (RADIANT) ──────────────────────────────────────
        if cs.bloom > 0.55 and cs.band in (2, 3):
            self._draw_corona(frame, h, w, cs)

        # ── 5. Crystal sparkle (CELESTIAL) ────────────────────────────────
        if cs.shimmer > 0.45:
            self._draw_sparkle(frame, h, w, cs)

    # ── effect methods ────────────────────────────────────────────────────

    def _draw_vignette(self, frame: np.ndarray, h: int, w: int, strength: float) -> None:
        key = ((h, w), round(strength, 2))
        if self._vignette_cache is None or self._vignette_cache[:2] != key:
            mask = _vignette_mask(h, w, strength * 1.8)
            self._vignette_cache = (key[0], key[1], mask)
        mask = self._vignette_cache[2]
        for c in range(3):
            frame[:, :, c] = (frame[:, :, c].astype(np.float32) * mask).astype(np.uint8)

    def _draw_fog(self, frame: np.ndarray, h: int, w: int, cs) -> None:
        t_slow = self._t * 0.18
        noise  = _simplex_approx(_TILE_W, _TILE_H, 3.0, t_slow)
        fog    = cv2.resize(noise, (w, h), interpolation=cv2.INTER_LINEAR)
        fog    = np.clip(fog * cs.fog * 1.6, 0.0, 1.0)

        r, g, b = cs.rgb_float
        fog_r = (fog * r * 60).astype(np.uint8)
        fog_g = (fog * g * 60).astype(np.uint8)
        fog_b = (fog * b * 80).astype(np.uint8)  # slightly heavier blue channel

        overlay = np.stack([fog_b, fog_g, fog_r], axis=2)
        cv2.addWeighted(overlay, 0.55, frame, 1.0, 0.0, frame)

    def _draw_aurora(self, frame: np.ndarray, h: int, w: int, cs) -> None:
        # Horizontal bands in the top 40 % of the frame
        t_slow = self._t * 0.25
        band_h = int(h * 0.40)
        noise  = _simplex_approx(_TILE_W, _TILE_H // 2, 2.5, t_slow)
        band_n = cv2.resize(noise, (w, band_h), interpolation=cv2.INTER_LINEAR)

        r, g, b = cs.rgb_float
        intensity = cs.shimmer * 0.5

        aurora = np.zeros((band_h, w, 3), dtype=np.uint8)
        aurora[:, :, 0] = np.clip(band_n * b * 200 * intensity, 0, 255).astype(np.uint8)
        aurora[:, :, 1] = np.clip(band_n * g * 180 * intensity, 0, 255).astype(np.uint8)
        aurora[:, :, 2] = np.clip(band_n * r * 140 * intensity, 0, 255).astype(np.uint8)

        frame[:band_h] = cv2.add(frame[:band_h], aurora)

    def _draw_corona(self, frame: np.ndarray, h: int, w: int, cs) -> None:
        cx, cy = w // 2, h // 2
        pulse  = 0.7 + 0.3 * math.sin(self._t * 2.0)
        radius = int(min(w, h) * 0.35 * (0.8 + cs.bloom * 0.4) * pulse)

        corona = np.zeros((h, w, 3), dtype=np.uint8)
        r, g, b = cs.rgb_float
        intensity = cs.bloom * 0.40

        # Radial gradient via concentric circles
        for ring in range(6, 0, -1):
            frac = ring / 6.0
            r_px = int(radius * frac)
            alpha_ring = (1.0 - frac) * intensity
            colour = (
                int(b * 255 * alpha_ring),
                int(g * 255 * alpha_ring),
                int(r * 255 * alpha_ring),
            )
            cv2.circle(corona, (cx, cy), r_px, colour, max(1, int(radius / 8)), cv2.LINE_AA)

        corona = cv2.GaussianBlur(corona, (0, 0), max(1, radius // 6))
        cv2.add(frame, corona, frame)

    def _draw_sparkle(self, frame: np.ndarray, h: int, w: int, cs) -> None:
        n_sparkles = int(80 * cs.shimmer)
        if self._sparkle_xy is None or len(self._sparkle_xy) < n_sparkles:
            rng = np.random.default_rng(42)
            self._sparkle_xy    = rng.integers(0, [w, h], size=(n_sparkles * 2, 2))
            self._sparkle_phase = rng.uniform(0, math.tau, n_sparkles * 2)

        r, g, b = cs.rgb_float

        for i in range(n_sparkles):
            phase  = self._sparkle_phase[i] + self._t * (2.0 + i * 0.04)
            bright = (math.sin(phase) * 0.5 + 0.5) * cs.shimmer
            if bright < 0.05:
                continue
            px, py = int(self._sparkle_xy[i, 0]), int(self._sparkle_xy[i, 1])
            if not (0 <= px < w and 0 <= py < h):
                continue
            colour = (
                int(b * 255 * bright),
                int(g * 255 * bright),
                int(r * 255 * bright),
            )
            size = 1 if bright < 0.5 else 2
            cv2.circle(frame, (px, py), size, colour, -1, cv2.LINE_AA)

        # Lens shimmer streak at very high pitch
        if cs.shimmer > 0.75:
            streak_alpha = (cs.shimmer - 0.75) / 0.25
            streak = np.zeros_like(frame)
            cx = w // 2
            streak_colour = (
                int(b * 200 * streak_alpha),
                int(g * 200 * streak_alpha),
                int(r * 200 * streak_alpha),
            )
            cv2.line(streak, (0, h // 2), (w, h // 2), streak_colour, 1, cv2.LINE_AA)
            horiz = cv2.GaussianBlur(streak, (1, int(h * 0.12) | 1), 0)
            cv2.add(frame, horiz, frame)
