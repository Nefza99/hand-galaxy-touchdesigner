"""
ui_overlay.py  (v2.1)
---------------------
All HUD elements.  New in v2.1: pitch band display + real-time pitch meter.
"""
from __future__ import annotations
import math, time
from dataclasses import dataclass, field
from typing import Optional
import cv2
import numpy as np
from .colour_mapper import apply_highlight, ColourTransition

_FONT       = cv2.FONT_HERSHEY_DUPLEX
_FONT_MONO  = cv2.FONT_HERSHEY_TRIPLEX
_HUD_DIM    = (80, 80, 80)


def _draw_text_shadow(frame, text, pos, font, scale, colour, thickness=2, shadow_offset=2):
    sx, sy = pos[0] + shadow_offset, pos[1] + shadow_offset
    cv2.putText(frame, text, (sx, sy), font, scale, (8, 8, 8), thickness + 1, cv2.LINE_AA)
    cv2.putText(frame, text, pos,      font, scale, colour,    thickness,     cv2.LINE_AA)


# ── Finger count ─────────────────────────────────────────────────────────────

class FingerCountDisplay:
    def draw(self, frame, count: int, hands_active: bool,
             effect_bgr: tuple = (200, 220, 50)) -> None:
        h, w = frame.shape[:2]
        cx  = w // 2
        txt = str(count)
        sc  = 3.2 if count < 10 else 2.6
        tk  = 3
        (tw, th), _ = cv2.getTextSize(txt, _FONT_MONO, sc, tk)
        tx  = cx - tw // 2
        ty  = th + 28
        line_y  = ty + 8
        lhalf   = max(tw, 60) // 2 + 14
        cv2.line(frame, (cx - lhalf, line_y), (cx + lhalf, line_y), effect_bgr, 1, cv2.LINE_AA)
        colour = effect_bgr if hands_active else _HUD_DIM
        _draw_text_shadow(frame, txt, (tx, ty), _FONT_MONO, sc, colour, tk)
        label = "FINGERS"
        (lw, _), _ = cv2.getTextSize(label, _FONT, 0.44, 1)
        cv2.putText(frame, label, (cx - lw // 2, line_y + 18),
                    _FONT, 0.44, _HUD_DIM, 1, cv2.LINE_AA)


# ── Pitch meter ──────────────────────────────────────────────────────────────

_BAND_COLOURS_BGR = [
    (120,  30,  80),   # void    — deep purple-black
    (200,  60, 120),   # deep    — violet
    ( 80, 200, 140),   # flowing — teal
    ( 40, 160, 240),   # radiant — orange-gold (BGR)
    (240, 230, 200),   # celestial — near-white cyan
]
_BAND_LABELS = ["VOID", "DEEP", "FLOW", "RADI", "CELE"]


class PitchMeter:
    """
    Vertical pitch meter on the right edge.  Shows:
      - Current frequency (Hz)
      - Normalised bar
      - Band zone label with colour
      - Rising/falling arrow
    """
    def draw(self, frame, pitch_result, colour_state) -> None:
        if pitch_result is None:
            return
        h, w = frame.shape[:2]

        bar_x     = w - 52
        bar_y_top = 60
        bar_h     = int(h * 0.55)
        bar_w     = 14
        norm      = pitch_result.normalised
        band      = pitch_result.band
        hz        = pitch_result.hz
        is_voiced = pitch_result.is_voiced

        # Background track
        cv2.rectangle(frame,
                      (bar_x, bar_y_top),
                      (bar_x + bar_w, bar_y_top + bar_h),
                      (30, 30, 30), -1)
        cv2.rectangle(frame,
                      (bar_x, bar_y_top),
                      (bar_x + bar_w, bar_y_top + bar_h),
                      (60, 60, 60), 1)

        if is_voiced:
            fill_h  = int(bar_h * norm)
            fill_y  = bar_y_top + bar_h - fill_h
            band_bgr = _BAND_COLOURS_BGR[min(band, 4)]
            # Gradient fill — fade from dim at bottom to bright at top
            for i in range(fill_h):
                row_y  = fill_y + i
                alpha  = i / max(fill_h, 1)
                colour = tuple(int(c * (0.4 + 0.6 * alpha)) for c in band_bgr)
                cv2.line(frame,
                         (bar_x + 1, row_y),
                         (bar_x + bar_w - 1, row_y),
                         colour, 1)

        # Hz label
        hz_text = f"{int(hz)}Hz" if is_voiced else "---"
        cv2.putText(frame, hz_text,
                    (bar_x - 2, bar_y_top + bar_h + 18),
                    _FONT, 0.38, colour_state.bgr if is_voiced else _HUD_DIM,
                    1, cv2.LINE_AA)

        # Band label
        band_label = _BAND_LABELS[band]
        cv2.putText(frame, band_label,
                    (bar_x - 2, bar_y_top - 10),
                    _FONT, 0.40,
                    _BAND_COLOURS_BGR[band] if is_voiced else _HUD_DIM,
                    1, cv2.LINE_AA)

        # Velocity arrow
        vel = getattr(pitch_result, "velocity", 0.0)
        if abs(vel) > 30 and is_voiced:
            arrow_x = bar_x + bar_w + 6
            arrow_y = bar_y_top + bar_h - int(bar_h * norm)
            arrow_char = "^" if vel > 0 else "v"
            arrow_col  = (80, 220, 255) if vel > 0 else (60, 80, 220)
            cv2.putText(frame, arrow_char,
                        (arrow_x, arrow_y),
                        _FONT, 0.55, arrow_col, 1, cv2.LINE_AA)

        # "PITCH" label
        cv2.putText(frame, "PITCH",
                    (bar_x - 2, bar_y_top - 24),
                    _FONT, 0.36, _HUD_DIM, 1, cv2.LINE_AA)


# ── Mic indicator ─────────────────────────────────────────────────────────────

class MicIndicator:
    def __init__(self):
        self._phase = 0.0
    def draw(self, frame, is_listening: bool, has_error: bool = False,
             dt: float = 0.016) -> None:
        h, w = frame.shape[:2]
        self._phase = (self._phase + dt * 3.0) % math.tau
        cx, cy = w - 26, 26
        if has_error:
            colour = (40, 40, 180)
        elif is_listening:
            pulse  = 0.55 + 0.45 * math.sin(self._phase)
            colour = tuple(int(c * pulse) for c in (60, 200, 80))
        else:
            colour = (80, 80, 80)
        pulse = 0.7 if not is_listening else (0.55 + 0.45 * math.sin(self._phase))
        cv2.circle(frame, (cx, cy), int(9 + 2 * pulse), colour, 1, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), 5, colour, -1, cv2.LINE_AA)
        label = "MIC" if is_listening else "OFF"
        cv2.putText(frame, label, (cx - 10, cy + 20), _FONT, 0.35, colour, 1, cv2.LINE_AA)


# ── Letter display ────────────────────────────────────────────────────────────

class LetterDisplay:
    def draw(self, frame, visible_letters, effect_bgr) -> None:
        if not visible_letters:
            return
        h, w = frame.shape[:2]
        overlay = frame.copy()
        for i, (letter, alpha) in enumerate(reversed(visible_letters)):
            y = h - 80 - i * 56
            if y < 60:
                break
            colour = tuple(int(c * alpha) for c in effect_bgr)
            _draw_text_shadow(overlay, letter, (32, y), _FONT_MONO, 1.8, colour, 2)
        cv2.addWeighted(overlay, 1.0, frame, 0.0, 0.0, frame)


# ── Speech strip ──────────────────────────────────────────────────────────────

class SpeechTextStrip:
    def __init__(self, display_duration: float = 2.5):
        self._text = ""
        self._ts   = 0.0
        self._dur  = display_duration
    def set_text(self, text: str) -> None:
        self._text = text
        self._ts   = time.monotonic()
    def draw(self, frame) -> None:
        if not self._text:
            return
        age = time.monotonic() - self._ts
        if age > self._dur:
            self._text = ""
            return
        alpha = max(0.0, 1.0 - age / self._dur)
        h, w  = frame.shape[:2]
        text  = f"» {self._text}"
        scale = 0.60
        (tw, _), _ = cv2.getTextSize(text, _FONT, scale, 1)
        x, y  = (w - tw) // 2, h - 30
        overlay = frame.copy()
        _draw_text_shadow(overlay, text, (x, y), _FONT, scale, (220, 220, 220), 1)
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0.0, frame)


# ── Animal image ──────────────────────────────────────────────────────────────

@dataclass
class _ImageSlot:
    image_bgra: Optional[np.ndarray] = None
    word: str = ""
    colour_bgr: tuple = (0, 180, 255)
    entered_at: float = 0.0
    display_duration: float = 5.0
    style: str = "glow"
    def is_alive(self) -> bool:
        return (time.monotonic() - self.entered_at) < self.display_duration
    def alpha(self) -> float:
        age = time.monotonic() - self.entered_at
        if age < 0.4:
            return age / 0.4
        remaining = self.display_duration - age
        if remaining < 0.8:
            return max(0.0, remaining / 0.8)
        return 1.0


class AnimalImageDisplay:
    def __init__(self, display_duration: float = 6.0):
        self._slot: Optional[_ImageSlot] = None
        self._display_duration = display_duration
        self._colour_transition = ColourTransition()
        self._last_time = time.monotonic()
        self._highlight_cache = None

    def trigger(self, image_bgra, word, colour_bgr, style="glow") -> None:
        self._slot = _ImageSlot(
            image_bgra=image_bgra, word=word, colour_bgr=colour_bgr,
            entered_at=time.monotonic(), display_duration=self._display_duration,
            style=style,
        )
        self._highlight_cache = None

    def draw(self, frame, effect_bgr) -> None:
        if self._slot is None or not self._slot.is_alive():
            self._slot = None
            return
        now = time.monotonic()
        dt  = now - self._last_time
        self._last_time = now
        current_colour = self._colour_transition.update(effect_bgr, dt, speed=3.0)
        slot  = self._slot
        alpha = slot.alpha()
        h, w  = frame.shape[:2]

        cache_key = (
            round(current_colour[0] / 8),
            round(current_colour[1] / 8),
            round(current_colour[2] / 8),
            slot.style,
        )
        if self._highlight_cache is None or self._highlight_cache[0] != cache_key:
            highlighted = apply_highlight(slot.image_bgra, current_colour,
                                          style=slot.style, intensity=0.85)
            self._highlight_cache = (cache_key, highlighted)
        else:
            highlighted = self._highlight_cache[1]

        ih, iw = highlighted.shape[:2]
        x = max(0, min((w - iw) // 2, w - iw))
        y = max(0, min((h - ih) // 2 - 20, h - ih))
        roi = frame[y:y + ih, x:x + iw]
        if roi.shape[:2] != highlighted.shape[:2]:
            return
        hi_alpha = (highlighted[:, :, 3].astype(np.float32) / 255.0) * alpha
        for c in range(3):
            roi[:, :, c] = np.clip(
                roi[:, :, c] * (1.0 - hi_alpha) +
                highlighted[:, :, c] * hi_alpha, 0, 255,
            ).astype(np.uint8)
        label_y = y + ih + 22
        if label_y < h - 8:
            label = slot.word.upper()
            (lw, _), _ = cv2.getTextSize(label, _FONT, 0.8, 1)
            lx = x + (iw - lw) // 2
            _draw_text_shadow(frame, label, (lx, label_y), _FONT, 0.8, current_colour, 1)

    @property
    def is_active(self) -> bool:
        return self._slot is not None and self._slot.is_alive()


# ── Band atmosphere label ─────────────────────────────────────────────────────

class AtmosphereBandLabel:
    """Small band name shown bottom-right, fades when band changes."""
    def __init__(self):
        self._last_band = -1
        self._alpha     = 0.0
        self._phase     = 0.0

    def draw(self, frame, colour_state, dt: float) -> None:
        h, w = frame.shape[:2]
        band      = colour_state.band
        band_name = colour_state.band_name.upper()
        if band != self._last_band:
            self._alpha     = 1.0
            self._last_band = band
        else:
            self._alpha = max(0.0, self._alpha - dt * 0.3)
        if self._alpha < 0.02:
            return
        text  = f"✦ {band_name}"
        scale = 0.65
        (tw, _), _ = cv2.getTextSize(text, _FONT, scale, 1)
        x = w - tw - 60
        y = h - 55
        colour = tuple(int(c * self._alpha) for c in colour_state.bgr)
        _draw_text_shadow(frame, text, (x, y), _FONT, scale, colour, 1)


# ── Master HUD ────────────────────────────────────────────────────────────────

class HUD:
    def __init__(self):
        self.finger_display  = FingerCountDisplay()
        self.mic_indicator   = MicIndicator()
        self.letter_display  = LetterDisplay()
        self.animal_display  = AnimalImageDisplay()
        self.speech_strip    = SpeechTextStrip()
        self.pitch_meter     = PitchMeter()
        self.band_label      = AtmosphereBandLabel()
