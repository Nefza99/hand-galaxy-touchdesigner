"""
pitch_effect_mapper.py
----------------------
Maps real-time pitch data to a full set of visual effect parameters:
colour, atmospheric zone, particle behaviour, and overlay intensity.

Five atmospheric zones (driven by vocal frequency band):

  Band 0 — VOID        (< 120 Hz)
    Colours  : near-black → deep indigo / obsidian
    Feel     : crushing depth, ultra-heavy feedback, almost no motion
    Overlay  : dark vignette, slow black fog tendrils

  Band 1 — DEEP        (120–250 Hz)
    Colours  : deep blue → violet / midnight purple
    Feel     : slow cosmic drift, rich starfield, low hum
    Overlay  : subtle nebula haze, long trails

  Band 2 — FLOWING     (250–500 Hz)
    Colours  : teal → green-cyan (natural speech zone)
    Feel     : normal galaxy — balanced motion, standard trails
    Overlay  : gentle aurora shimmer

  Band 3 — RADIANT     (500–800 Hz)
    Colours  : gold → orange → coral
    Feel     : energetic, faster spin, tighter orbit
    Overlay  : warm corona bloom, light particle scatter

  Band 4 — CELESTIAL   (> 800 Hz)
    Colours  : bright cyan → white → pale pink
    Feel     : intense sparkle, rapid burst, near-white saturation
    Overlay  : full-screen shimmer, crystal scatter, lens flare

Pitch VELOCITY (rising/falling) modifies the effect:
  Rising fast  → increase energy + burst coefficient
  Falling fast → add trail persistence, deepen colour

All parameters are exposed as a flat ``EffectParams`` dataclass that is sent
to TouchDesigner via OSC and also used to modify the Python preview overlay.
"""
from __future__ import annotations

import colorsys
import math
import time
from dataclasses import dataclass, field

from .pitch_detector import PitchResult, BAND_NAMES, BAND_THRESHOLDS


# ── per-band atmosphere definitions ─────────────────────────────────────────

@dataclass(frozen=True)
class AtmosphereDef:
    name:                str
    hue_low:             float    # HSV hue at bottom of band (0–1)
    hue_high:            float    # HSV hue at top of band
    saturation:          float    # base saturation
    value:               float    # base brightness
    feedback_base:       float    # galaxy trail persistence (0–1)
    particle_speed:      float    # orbit speed multiplier (0–1)
    bloom_intensity:     float    # glow / bloom strength (0–1)
    vignette_strength:   float    # dark-edge crush (0–1, 0=none)
    shimmer_intensity:   float    # sparkle / crystal overlay (0–1)
    fog_density:         float    # atmospheric haze (0–1)


_ATMOSPHERES: tuple[AtmosphereDef, ...] = (
    # Band 0 — VOID
    AtmosphereDef(
        name="void",
        hue_low=0.70, hue_high=0.75,
        saturation=0.95, value=0.25,
        feedback_base=0.90,
        particle_speed=0.10,
        bloom_intensity=0.15,
        vignette_strength=0.85,
        shimmer_intensity=0.0,
        fog_density=0.70,
    ),
    # Band 1 — DEEP
    AtmosphereDef(
        name="deep",
        hue_low=0.60, hue_high=0.72,
        saturation=0.90, value=0.55,
        feedback_base=0.78,
        particle_speed=0.28,
        bloom_intensity=0.35,
        vignette_strength=0.55,
        shimmer_intensity=0.05,
        fog_density=0.40,
    ),
    # Band 2 — FLOWING
    AtmosphereDef(
        name="flowing",
        hue_low=0.42, hue_high=0.55,
        saturation=0.80, value=0.80,
        feedback_base=0.60,
        particle_speed=0.55,
        bloom_intensity=0.55,
        vignette_strength=0.20,
        shimmer_intensity=0.15,
        fog_density=0.10,
    ),
    # Band 3 — RADIANT
    AtmosphereDef(
        name="radiant",
        hue_low=0.08, hue_high=0.15,
        saturation=0.85, value=0.92,
        feedback_base=0.45,
        particle_speed=0.75,
        bloom_intensity=0.78,
        vignette_strength=0.05,
        shimmer_intensity=0.35,
        fog_density=0.03,
    ),
    # Band 4 — CELESTIAL
    AtmosphereDef(
        name="celestial",
        hue_low=0.50, hue_high=0.58,
        saturation=0.35, value=1.00,
        feedback_base=0.30,
        particle_speed=1.00,
        bloom_intensity=1.00,
        vignette_strength=0.0,
        shimmer_intensity=1.0,
        fog_density=0.0,
    ),
)


# ── output parameters ────────────────────────────────────────────────────────

@dataclass
class EffectParams:
    """
    All visual parameters derived from pitch.
    Sent to TouchDesigner via OSC and used in the Python preview overlay.
    """
    # Colour
    hue:               float = 0.55   # 0–1
    saturation:        float = 0.80
    value:             float = 0.80
    r:                 float = 0.0    # computed RGB 0–1
    g:                 float = 0.8
    b:                 float = 1.0

    # Atmospheric zone
    band:              int   = 2      # 0–4
    band_name:         str   = "flowing"
    band_blend:        float = 0.0   # 0–1 crossfade to next band

    # Galaxy behaviour
    feedback:          float = 0.60  # trail persistence
    particle_speed:    float = 0.55  # orbit speed multiplier
    bloom:             float = 0.55  # glow intensity
    burst_coefficient: float = 0.0   # extra burst from velocity

    # Overlays (Python preview + TD)
    vignette:          float = 0.20  # 0–1 dark-edge crush
    shimmer:           float = 0.15  # sparkle/crystal intensity
    fog:               float = 0.10  # haze density

    # Pitch metadata (pass-through for TD)
    pitch_hz:          float = 0.0
    pitch_norm:        float = 0.0   # 0–1 within vocal range
    pitch_confidence:  float = 0.0
    pitch_velocity:    float = 0.0   # Hz/s

    # Internal
    timestamp:         float = field(default_factory=time.monotonic)


# ── mapper ───────────────────────────────────────────────────────────────────

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def _smooth(current: float, target: float, alpha: float) -> float:
    return current + (target - current) * max(0.0, min(1.0, alpha))


def _hue_lerp(h1: float, h2: float, t: float) -> float:
    """Circular interpolation of hue (0–1)."""
    delta = (h2 - h1 + 0.5) % 1.0 - 0.5
    return (h1 + delta * t) % 1.0


class PitchEffectMapper:
    """
    Converts a ``PitchResult`` into a full ``EffectParams`` object each frame.

    All parameters are smoothly interpolated — no sudden jumps.

    Parameters
    ----------
    hue_alpha : float
        Smoothing speed for colour hue transitions.
    param_alpha : float
        Smoothing speed for all other parameters.
    velocity_gain : float
        How strongly pitch velocity (rising/falling) boosts burst_coefficient.
    """

    def __init__(
        self,
        hue_alpha:     float = 0.05,
        param_alpha:   float = 0.08,
        velocity_gain: float = 0.0006,
    ):
        self._hue_alpha     = hue_alpha
        self._param_alpha   = param_alpha
        self._velocity_gain = velocity_gain
        self._current       = EffectParams()
        self._last_time     = time.monotonic()

    # ── public ───────────────────────────────────────────────────────────────

    def update(self, pitch: PitchResult) -> EffectParams:
        """
        Compute new EffectParams from the latest PitchResult.
        Call once per main-loop frame.
        """
        now = time.monotonic()
        self._last_time = now

        band      = pitch.band
        velocity  = pitch.velocity
        voiced    = pitch.is_voiced

        atm      = _ATMOSPHERES[band]
        atm_next = _ATMOSPHERES[min(band + 1, 4)]

        # Band crossfade must be computed from absolute Hz, not the voice-normalised
        # 0–1 range, otherwise low/high voices blend into the wrong atmosphere zones.
        hz_edges = list(BAND_THRESHOLDS) + [1100.0]
        hz_lo = hz_edges[band]
        hz_hi = hz_edges[min(band + 1, len(hz_edges) - 1)]
        if band == len(_ATMOSPHERES) - 1:
            hz_hi = max(hz_hi, pitch.hz, hz_lo + 1.0)
        band_range = max(hz_hi - hz_lo, 1e-6)
        within_band = max(0.0, min(1.0, (pitch.hz - hz_lo) / band_range)) if voiced else 0.0
        crossfade = max(0.0, (within_band - 0.80) / 0.20)  # last 20 %

        # Target hue
        target_hue = _hue_lerp(
            _lerp(atm.hue_low, atm.hue_high, within_band),
            _lerp(atm_next.hue_low, atm_next.hue_high, 0.0),
            crossfade,
        )
        if not voiced:
            # Slow drift back toward flowing (band 2) hue when silent
            target_hue = _hue_lerp(
                target_hue,
                _ATMOSPHERES[2].hue_low,
                0.02,
            )

        # Target sat/val with velocity modulation
        vel_abs  = min(abs(velocity) * self._velocity_gain, 1.0)
        vel_sign = 1.0 if velocity > 0 else -1.0

        target_sat = _lerp(atm.saturation, atm_next.saturation, crossfade)
        target_val = _lerp(atm.value, atm_next.value, crossfade)

        # Rising pitch: brighter + desaturated; falling: deeper + more saturated
        if voiced:
            if velocity > 0:
                target_val = min(1.0, target_val + vel_abs * 0.25)
                target_sat = max(0.2, target_sat - vel_abs * 0.15)
            else:
                target_val = max(0.1, target_val - vel_abs * 0.15)
                target_sat = min(1.0, target_sat + vel_abs * 0.12)

        # Target atmospheric params
        target_feedback = _lerp(atm.feedback_base, atm_next.feedback_base, crossfade)
        target_speed    = _lerp(atm.particle_speed, atm_next.particle_speed, crossfade)
        target_bloom    = _lerp(atm.bloom_intensity, atm_next.bloom_intensity, crossfade)
        target_vignette = _lerp(atm.vignette_strength, atm_next.vignette_strength, crossfade)
        target_shimmer  = _lerp(atm.shimmer_intensity, atm_next.shimmer_intensity, crossfade)
        target_fog      = _lerp(atm.fog_density, atm_next.fog_density, crossfade)

        # Rising pitch spikes burst + shimmer
        burst_coeff = vel_abs * max(0.0, vel_sign) * 0.8 if voiced else 0.0
        if not voiced:
            target_shimmer *= 0.3
            target_bloom   *= 0.5

        # ── smooth toward targets ───────────────────────────────────────────
        c = self._current
        pa = self._param_alpha
        ha = self._hue_alpha

        # Hue (circular)
        hdelta = (_hue_lerp(c.hue, target_hue, 1.0) - c.hue + 0.5) % 1.0 - 0.5
        c.hue        = (c.hue + hdelta * ha) % 1.0
        c.saturation = _smooth(c.saturation, target_sat,     pa)
        c.value      = _smooth(c.value,      target_val,     pa)

        c.feedback          = _smooth(c.feedback,          target_feedback, pa)
        c.particle_speed    = _smooth(c.particle_speed,    target_speed,    pa)
        c.bloom             = _smooth(c.bloom,             target_bloom,    pa * 1.5)
        c.burst_coefficient = _smooth(c.burst_coefficient, burst_coeff,     0.25)
        c.vignette          = _smooth(c.vignette,          target_vignette, pa)
        c.shimmer           = _smooth(c.shimmer,           target_shimmer,  pa * 1.2)
        c.fog               = _smooth(c.fog,               target_fog,      pa)

        # Compute RGB
        r_f, g_f, b_f = colorsys.hsv_to_rgb(c.hue, c.saturation, c.value)
        c.r, c.g, c.b = r_f, g_f, b_f

        # Metadata
        c.band             = band
        c.band_name        = atm.name
        c.band_blend       = crossfade
        c.pitch_hz         = pitch.hz
        c.pitch_norm       = pitch.normalised
        c.pitch_confidence = pitch.confidence
        c.pitch_velocity   = pitch.velocity
        c.timestamp        = now

        return c

    @property
    def current(self) -> EffectParams:
        return self._current

    def bgr(self) -> tuple[int, int, int]:
        c = self._current
        return (int(c.b * 255), int(c.g * 255), int(c.r * 255))

    def rgb(self) -> tuple[int, int, int]:
        c = self._current
        return (int(c.r * 255), int(c.g * 255), int(c.b * 255))
