"""
effect_colour_state.py  (v2.1)
------------------------------
Unified effect colour — blends gesture + pitch contributions.
"""
from __future__ import annotations

import colorsys
import math
import time
from dataclasses import dataclass


def _smooth(current: float, target: float, alpha: float) -> float:
    return current + (target - current) * max(0.0, min(1.0, alpha))


def _wrap_hue(h: float) -> float:
    return h % 1.0


@dataclass
class ColourState:
    hue:            float = 0.55
    saturation:     float = 0.85
    value:          float = 0.90
    feedback:       float = 0.60
    particle_speed: float = 0.55
    bloom:          float = 0.55
    vignette:       float = 0.20
    shimmer:        float = 0.15
    fog:            float = 0.10
    burst_coeff:    float = 0.0
    band:           int   = 2
    band_name:      str   = "flowing"

    @property
    def bgr(self) -> tuple[int, int, int]:
        r, g, b = colorsys.hsv_to_rgb(self.hue, self.saturation, self.value)
        return (int(b * 255), int(g * 255), int(r * 255))

    @property
    def rgb(self) -> tuple[int, int, int]:
        r, g, b = colorsys.hsv_to_rgb(self.hue, self.saturation, self.value)
        return (int(r * 255), int(g * 255), int(b * 255))

    @property
    def rgb_float(self) -> tuple[float, float, float]:
        return colorsys.hsv_to_rgb(self.hue, self.saturation, self.value)


class EffectColourState:
    def __init__(self, pitch_weight: float = 0.60):
        self._pitch_weight = pitch_weight
        self._colour       = ColourState()
        self._burst_flash  = 0.0
        self._drift_phase  = 0.0
        self._last_time    = time.monotonic()
        self._td_override_rgb: tuple[float, float, float] | None = None
        self._td_override_weight = 0.0

    def update(self, frame, pitch_params=None) -> ColourState:
        now = time.monotonic()
        dt  = min(now - self._last_time, 0.1)
        self._last_time = now

        primary = frame.primary
        active  = primary.active or frame.secondary.active

        self._drift_phase = (self._drift_phase + dt * 0.04) % 1.0
        idle_hue = 0.58 + math.sin(self._drift_phase * math.tau) * 0.06

        if active:
            p = primary if primary.active else frame.secondary
            gesture_hue = 0.45 * (1.0 - p.pinch_norm) + 0.95 * p.pinch_norm
            gesture_hue = _wrap_hue(gesture_hue + p.spin * 0.02)
            g_hue = _wrap_hue(idle_hue * (1.0 - p.energy) + gesture_hue * p.energy)
            g_sat = 0.65 + p.energy * 0.35
            g_val = 0.75 + p.energy * 0.20
            self._burst_flash = max(self._burst_flash, p.burst * 0.4)
        else:
            g_hue = idle_hue
            g_sat = 0.70
            g_val = 0.75

        self._burst_flash *= max(0.0, 1.0 - dt * 6.0)

        if pitch_params is not None and pitch_params.pitch_confidence > 0.3:
            pw = self._pitch_weight
            h_delta = (_wrap_hue(pitch_params.hue - g_hue + 0.5) - 0.5)
            target_hue      = _wrap_hue(g_hue + h_delta * pw)
            target_sat      = g_sat * (1.0 - pw) + pitch_params.saturation * pw
            target_val      = g_val * (1.0 - pw) + pitch_params.value * pw
            target_feedback = pitch_params.feedback
            target_speed    = pitch_params.particle_speed
            target_bloom    = pitch_params.bloom
            target_vignette = pitch_params.vignette
            target_shimmer  = pitch_params.shimmer
            target_fog      = pitch_params.fog
            burst_coeff     = pitch_params.burst_coefficient
            band            = pitch_params.band
            band_name       = pitch_params.band_name
        else:
            target_hue      = g_hue
            target_sat      = g_sat
            target_val      = g_val
            target_feedback = 0.60
            target_speed    = 0.55
            target_bloom    = 0.55
            target_vignette = 0.20
            target_shimmer  = 0.10
            target_fog      = 0.08
            burst_coeff     = 0.0
            band            = 2
            band_name       = "flowing"

        a = 0.06
        hd = (_wrap_hue(target_hue - self._colour.hue + 0.5) - 0.5)
        self._colour.hue        = _wrap_hue(self._colour.hue + hd * a)
        self._colour.saturation = _smooth(self._colour.saturation, target_sat,     a * 1.3)
        self._colour.value      = _smooth(self._colour.value,
                                          min(1.0, target_val + self._burst_flash), a * 1.5)
        self._colour.feedback       = _smooth(self._colour.feedback,       target_feedback, a)
        self._colour.particle_speed = _smooth(self._colour.particle_speed, target_speed,    a)
        self._colour.bloom          = _smooth(self._colour.bloom,          target_bloom,    a * 1.5)
        self._colour.vignette       = _smooth(self._colour.vignette,       target_vignette, a)
        self._colour.shimmer        = _smooth(self._colour.shimmer,        target_shimmer,  a * 1.5)
        self._colour.fog            = _smooth(self._colour.fog,            target_fog,      a)
        self._colour.burst_coeff    = _smooth(self._colour.burst_coeff,    burst_coeff,     0.25)
        self._colour.band           = band
        self._colour.band_name      = band_name

        if self._td_override_rgb and self._td_override_weight > 0.0:
            ovr_r, ovr_g, ovr_b = self._td_override_rgb
            h, s, v = colorsys.rgb_to_hsv(ovr_r, ovr_g, ovr_b)
            w = self._td_override_weight
            self._colour.hue        = _wrap_hue(self._colour.hue * (1 - w) + h * w)
            self._colour.saturation = self._colour.saturation * (1 - w) + s * w
            self._colour.value      = self._colour.value * (1 - w) + v * w

        return self._colour

    def set_td_override(self, r: float, g: float, b: float, weight: float = 0.5) -> None:
        self._td_override_rgb    = (r, g, b)
        self._td_override_weight = max(0.0, min(1.0, weight))

    def clear_td_override(self) -> None:
        self._td_override_rgb    = None
        self._td_override_weight = 0.0

    @property
    def colour(self) -> ColourState:
        return self._colour

    @property
    def bgr(self) -> tuple[int, int, int]:
        return self._colour.bgr

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self._colour.rgb
