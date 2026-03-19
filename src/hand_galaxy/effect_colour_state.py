"""
Unified colour state for gesture, speech theme, amplitude, and pitch.
"""
from __future__ import annotations

import colorsys
import math
import time
from dataclasses import dataclass, field


def _smooth(current: float, target: float, alpha: float) -> float:
    return current + (target - current) * max(0.0, min(1.0, alpha))


def _wrap_hue(hue: float) -> float:
    return hue % 1.0


def _circular_blend(hues: list[float]) -> float:
    if not hues:
        return 0.55
    sx = sum(math.cos(h * math.tau) for h in hues)
    sy = sum(math.sin(h * math.tau) for h in hues)
    return (_wrap_hue(math.atan2(sy, sx) / math.tau)) if (sx or sy) else hues[0]


@dataclass
class ZoneColourState:
    label: str
    hue: float = 0.55
    accent_hue: float = 0.65
    saturation: float = 0.85
    value: float = 0.90
    active: bool = False
    category: str = ""
    word: str = ""

    @property
    def rgb(self) -> tuple[int, int, int]:
        r, g, b = colorsys.hsv_to_rgb(self.hue, self.saturation, self.value)
        return (int(r * 255), int(g * 255), int(b * 255))

    @property
    def bgr(self) -> tuple[int, int, int]:
        r, g, b = self.rgb
        return (b, g, r)

    @property
    def rgb_float(self) -> tuple[float, float, float]:
        return colorsys.hsv_to_rgb(self.hue, self.saturation, self.value)


@dataclass
class ColourState:
    hue: float = 0.55
    saturation: float = 0.85
    value: float = 0.90
    feedback: float = 0.60
    particle_speed: float = 0.55
    bloom: float = 0.55
    vignette: float = 0.20
    shimmer: float = 0.15
    fog: float = 0.10
    burst_coeff: float = 0.0
    band: int = 2
    band_name: str = "flowing"
    amplitude: float = 0.0
    theme_category: str = ""
    left_zone: ZoneColourState = field(default_factory=lambda: ZoneColourState(label="Left"))
    right_zone: ZoneColourState = field(default_factory=lambda: ZoneColourState(label="Right"))

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
        self._colour = ColourState()
        self._burst_flash = 0.0
        self._drift_phase = 0.0
        self._last_time = time.monotonic()
        self._td_override_rgb: tuple[float, float, float] | None = None
        self._td_override_weight = 0.0

    def update(self, frame, pitch_params=None, amplitude=None, hand_themes: dict[str, object] | None = None) -> ColourState:
        hand_themes = hand_themes or {}
        now = time.monotonic()
        dt = min(now - self._last_time, 0.1)
        self._last_time = now

        self._drift_phase = (self._drift_phase + dt * 0.04) % 1.0
        idle_hue = 0.58 + math.sin(self._drift_phase * math.tau) * 0.06

        self._colour.left_zone = self._update_zone(
            current=self._colour.left_zone,
            hand=frame.left,
            default_hue=_wrap_hue(idle_hue - 0.08),
            theme=hand_themes.get("Left"),
            alpha=0.12,
        )
        self._colour.right_zone = self._update_zone(
            current=self._colour.right_zone,
            hand=frame.right,
            default_hue=_wrap_hue(idle_hue + 0.08),
            theme=hand_themes.get("Right"),
            alpha=0.12,
        )

        active_zones = [zone for zone in (self._colour.left_zone, self._colour.right_zone) if zone.active]
        zone_hues = [zone.hue for zone in active_zones]
        if active_zones:
            gesture_hue = _circular_blend(zone_hues)
            g_sat = max(zone.saturation for zone in active_zones)
            g_val = max(zone.value for zone in active_zones)
            self._colour.theme_category = active_zones[0].category
            hand_energy = max(
                getattr(frame.left, "energy", 0.0),
                getattr(frame.right, "energy", 0.0),
            )
            self._burst_flash = max(self._burst_flash, hand_energy * 0.10)
        else:
            gesture_hue = idle_hue
            g_sat = 0.70
            g_val = 0.75
            self._colour.theme_category = ""

        amp_value = getattr(amplitude, "amplitude", 0.0) if amplitude else 0.0
        amp_pulse = getattr(amplitude, "pulse", 0.0) if amplitude else 0.0
        self._colour.amplitude = _smooth(self._colour.amplitude, amp_value, 0.18)
        self._burst_flash = max(self._burst_flash * max(0.0, 1.0 - dt * 5.0), amp_pulse * 0.20)

        if pitch_params is not None and pitch_params.pitch_confidence > 0.3:
            pw = self._pitch_weight
            hue_delta = (_wrap_hue(pitch_params.hue - gesture_hue + 0.5) - 0.5)
            target_hue = _wrap_hue(gesture_hue + hue_delta * pw)
            target_sat = g_sat * (1.0 - pw) + pitch_params.saturation * pw
            target_val = g_val * (1.0 - pw) + pitch_params.value * pw
            target_feedback = pitch_params.feedback
            target_speed = pitch_params.particle_speed
            target_bloom = pitch_params.bloom
            target_vignette = pitch_params.vignette
            target_shimmer = pitch_params.shimmer
            target_fog = pitch_params.fog
            burst_coeff = pitch_params.burst_coefficient
            band = pitch_params.band
            band_name = pitch_params.band_name
        else:
            target_hue = gesture_hue
            target_sat = g_sat
            target_val = g_val
            target_feedback = 0.60
            target_speed = 0.55
            target_bloom = 0.55
            target_vignette = 0.20
            target_shimmer = 0.12
            target_fog = 0.08
            burst_coeff = 0.0
            band = 2
            band_name = "flowing"

        target_val = min(1.0, target_val + amp_value * 0.10 + self._burst_flash)
        target_bloom = min(1.0, target_bloom + amp_value * 0.18)
        target_shimmer = min(1.0, target_shimmer + amp_value * 0.35 + amp_pulse * 0.25)
        target_feedback = min(1.0, target_feedback + amp_value * 0.08)
        target_speed = min(1.0, target_speed + amp_pulse * 0.20)

        a = 0.08
        hue_delta = (_wrap_hue(target_hue - self._colour.hue + 0.5) - 0.5)
        self._colour.hue = _wrap_hue(self._colour.hue + hue_delta * a)
        self._colour.saturation = _smooth(self._colour.saturation, target_sat, a * 1.2)
        self._colour.value = _smooth(self._colour.value, target_val, a * 1.4)
        self._colour.feedback = _smooth(self._colour.feedback, target_feedback, a)
        self._colour.particle_speed = _smooth(self._colour.particle_speed, target_speed, a)
        self._colour.bloom = _smooth(self._colour.bloom, target_bloom, a * 1.3)
        self._colour.vignette = _smooth(self._colour.vignette, target_vignette, a)
        self._colour.shimmer = _smooth(self._colour.shimmer, target_shimmer, a * 1.4)
        self._colour.fog = _smooth(self._colour.fog, target_fog, a)
        self._colour.burst_coeff = _smooth(self._colour.burst_coeff, burst_coeff + amp_pulse * 0.10, 0.22)
        self._colour.band = band
        self._colour.band_name = band_name

        if self._td_override_rgb and self._td_override_weight > 0.0:
            ovr_r, ovr_g, ovr_b = self._td_override_rgb
            h, s, v = colorsys.rgb_to_hsv(ovr_r, ovr_g, ovr_b)
            weight = self._td_override_weight
            self._colour.hue = _wrap_hue(self._colour.hue * (1 - weight) + h * weight)
            self._colour.saturation = self._colour.saturation * (1 - weight) + s * weight
            self._colour.value = self._colour.value * (1 - weight) + v * weight

        return self._colour

    def _update_zone(self, current: ZoneColourState, hand, default_hue: float, theme, alpha: float) -> ZoneColourState:
        active = bool(getattr(hand, "active", False)) or getattr(hand, "energy", 0.0) > 0.05
        energy = getattr(hand, "energy", 0.0)
        pinch = getattr(hand, "pinch_norm", 0.0)
        theme_hue = getattr(theme, "hue", default_hue)
        accent_hue = getattr(theme, "accent_hue", _wrap_hue(theme_hue + 0.16))
        category = getattr(theme, "category", "")
        word = getattr(theme, "word", "")
        gesture_hue = _wrap_hue(default_hue + pinch * 0.22 + getattr(hand, "spin", 0.0) * 0.018)
        target_hue = _wrap_hue(gesture_hue * 0.55 + theme_hue * 0.45) if active else theme_hue
        target_sat = min(1.0, getattr(theme, "saturation", 0.82) + energy * 0.15)
        target_val = min(1.0, max(0.35, getattr(theme, "value", 0.88) * (0.72 if not active else 0.88) + energy * 0.16))
        hue_delta = (_wrap_hue(target_hue - current.hue + 0.5) - 0.5)
        current.hue = _wrap_hue(current.hue + hue_delta * alpha)
        current.accent_hue = _wrap_hue(current.accent_hue + ((_wrap_hue(accent_hue - current.accent_hue + 0.5) - 0.5) * alpha))
        current.saturation = _smooth(current.saturation, target_sat, alpha * 1.2)
        current.value = _smooth(current.value, target_val, alpha * 1.3)
        current.active = active
        current.category = category
        current.word = word
        return current

    def set_td_override(self, r: float, g: float, b: float, weight: float = 0.5) -> None:
        self._td_override_rgb = (r, g, b)
        self._td_override_weight = max(0.0, min(1.0, weight))

    def clear_td_override(self) -> None:
        self._td_override_rgb = None
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
