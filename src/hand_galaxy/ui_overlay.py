from __future__ import annotations

import colorsys
import math
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from .colour_mapper import ColourTransition, apply_highlight

_FONT = cv2.FONT_HERSHEY_DUPLEX
_FONT_MONO = cv2.FONT_HERSHEY_TRIPLEX
_HUD_DIM = (80, 80, 80)
_PHONEME_FAMILY_COLOURS = {
    "vowel": (90, 220, 255),
    "plosive": (100, 170, 255),
    "fricative": (110, 255, 180),
    "nasal": (220, 160, 100),
    "liquid": (220, 120, 220),
    "glide": (140, 220, 120),
    "breath": (180, 180, 180),
    "affricate": (90, 120, 255),
}


def _draw_text_shadow(frame, text, pos, font, scale, colour, thickness=2, shadow_offset=2):
    sx, sy = pos[0] + shadow_offset, pos[1] + shadow_offset
    cv2.putText(frame, text, (sx, sy), font, scale, (8, 8, 8), thickness + 1, cv2.LINE_AA)
    cv2.putText(frame, text, pos, font, scale, colour, thickness, cv2.LINE_AA)


def _alpha_blend(frame: np.ndarray, sprite: np.ndarray, x: int, y: int, alpha: float = 1.0) -> None:
    h, w = frame.shape[:2]
    sh, sw = sprite.shape[:2]
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(w, x + sw)
    y1 = min(h, y + sh)
    if x0 >= x1 or y0 >= y1:
        return
    sx0 = x0 - x
    sy0 = y0 - y
    sx1 = sx0 + (x1 - x0)
    sy1 = sy0 + (y1 - y0)
    crop = sprite[sy0:sy1, sx0:sx1]
    roi = frame[y0:y1, x0:x1]
    sprite_alpha = (crop[:, :, 3].astype(np.float32) / 255.0) * alpha
    for channel in range(3):
        roi[:, :, channel] = np.clip(
            roi[:, :, channel] * (1.0 - sprite_alpha) +
            crop[:, :, channel] * sprite_alpha,
            0,
            255,
        ).astype(np.uint8)


def _scale_and_rotate(sprite: np.ndarray, scale: float, rotation_rad: float = 0.0) -> np.ndarray:
    scale = max(0.1, scale)
    target_w = max(12, int(sprite.shape[1] * scale))
    target_h = max(12, int(sprite.shape[0] * scale))
    resized = cv2.resize(sprite, (target_w, target_h), interpolation=cv2.INTER_AREA if scale <= 1.0 else cv2.INTER_LINEAR)
    if abs(rotation_rad) < 1e-3:
        return resized
    center = (target_w / 2.0, target_h / 2.0)
    rot = cv2.getRotationMatrix2D(center, math.degrees(rotation_rad), 1.0)
    cos = abs(rot[0, 0])
    sin = abs(rot[0, 1])
    bound_w = int((target_h * sin) + (target_w * cos))
    bound_h = int((target_h * cos) + (target_w * sin))
    rot[0, 2] += (bound_w / 2.0) - center[0]
    rot[1, 2] += (bound_h / 2.0) - center[1]
    return cv2.warpAffine(
        resized,
        rot,
        (bound_w, bound_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )


class FingerCountDisplay:
    def draw(self, frame, count: int, hands_active: bool, effect_bgr: tuple = (200, 220, 50)) -> None:
        h, w = frame.shape[:2]
        cx = w // 2
        text = str(count)
        scale = 3.2 if count < 10 else 2.6
        thickness = 3
        (tw, th), _ = cv2.getTextSize(text, _FONT_MONO, scale, thickness)
        tx = cx - tw // 2
        ty = th + 28
        line_y = ty + 8
        lhalf = max(tw, 60) // 2 + 14
        cv2.line(frame, (cx - lhalf, line_y), (cx + lhalf, line_y), effect_bgr, 1, cv2.LINE_AA)
        colour = effect_bgr if hands_active else _HUD_DIM
        _draw_text_shadow(frame, text, (tx, ty), _FONT_MONO, scale, colour, thickness)
        label = "FINGERS"
        (lw, _), _ = cv2.getTextSize(label, _FONT, 0.44, 1)
        cv2.putText(frame, label, (cx - lw // 2, line_y + 18), _FONT, 0.44, _HUD_DIM, 1, cv2.LINE_AA)


_BAND_COLOURS_BGR = [
    (120, 30, 80),
    (200, 60, 120),
    (80, 200, 140),
    (40, 160, 240),
    (240, 230, 200),
]
_BAND_LABELS = ["VOID", "DEEP", "FLOW", "RADI", "CELE"]


class PitchMeter:
    def draw(self, frame, pitch_result, colour_state) -> None:
        if pitch_result is None:
            return
        h, w = frame.shape[:2]
        bar_x = w - 52
        bar_y_top = 60
        bar_h = int(h * 0.55)
        bar_w = 14
        norm = pitch_result.normalised
        band = pitch_result.band
        hz = pitch_result.hz
        is_voiced = pitch_result.is_voiced
        cv2.rectangle(frame, (bar_x, bar_y_top), (bar_x + bar_w, bar_y_top + bar_h), (30, 30, 30), -1)
        cv2.rectangle(frame, (bar_x, bar_y_top), (bar_x + bar_w, bar_y_top + bar_h), (60, 60, 60), 1)
        if is_voiced:
            fill_h = int(bar_h * norm)
            fill_y = bar_y_top + bar_h - fill_h
            band_bgr = _BAND_COLOURS_BGR[min(band, 4)]
            for i in range(fill_h):
                row_y = fill_y + i
                alpha = i / max(fill_h, 1)
                colour = tuple(int(c * (0.4 + 0.6 * alpha)) for c in band_bgr)
                cv2.line(frame, (bar_x + 1, row_y), (bar_x + bar_w - 1, row_y), colour, 1)
        hz_text = f"{int(hz)}Hz" if is_voiced else "---"
        cv2.putText(frame, hz_text, (bar_x - 2, bar_y_top + bar_h + 18), _FONT, 0.38, colour_state.bgr if is_voiced else _HUD_DIM, 1, cv2.LINE_AA)
        cv2.putText(frame, _BAND_LABELS[band], (bar_x - 2, bar_y_top - 10), _FONT, 0.40, _BAND_COLOURS_BGR[band] if is_voiced else _HUD_DIM, 1, cv2.LINE_AA)
        vel = getattr(pitch_result, "velocity", 0.0)
        if abs(vel) > 30 and is_voiced:
            arrow_x = bar_x + bar_w + 6
            arrow_y = bar_y_top + bar_h - int(bar_h * norm)
            arrow_char = "^" if vel > 0 else "v"
            arrow_col = (80, 220, 255) if vel > 0 else (60, 80, 220)
            cv2.putText(frame, arrow_char, (arrow_x, arrow_y), _FONT, 0.55, arrow_col, 1, cv2.LINE_AA)
        cv2.putText(frame, "PITCH", (bar_x - 2, bar_y_top - 24), _FONT, 0.36, _HUD_DIM, 1, cv2.LINE_AA)


class AmplitudeMeter:
    def draw(self, frame, audio_features, colour_state) -> None:
        if audio_features is None:
            return
        h, _ = frame.shape[:2]
        bar_x = 18
        bar_y_top = 64
        bar_h = int(h * 0.36)
        bar_w = 12
        amplitude = getattr(audio_features, "amplitude", 0.0)
        pulse = getattr(audio_features, "pulse", 0.0)
        cv2.rectangle(frame, (bar_x, bar_y_top), (bar_x + bar_w, bar_y_top + bar_h), (30, 30, 30), -1)
        cv2.rectangle(frame, (bar_x, bar_y_top), (bar_x + bar_w, bar_y_top + bar_h), (60, 60, 60), 1)
        fill_h = int(bar_h * amplitude)
        fill_y = bar_y_top + bar_h - fill_h
        amp_colour = tuple(int(c * (0.6 + 0.4 * pulse)) for c in colour_state.left_zone.bgr)
        if fill_h > 0:
            cv2.rectangle(frame, (bar_x + 1, fill_y), (bar_x + bar_w - 1, bar_y_top + bar_h - 1), amp_colour, -1)
        db_text = f"{int(getattr(audio_features, 'decibels', -80.0))}dB"
        cv2.putText(frame, db_text, (bar_x - 4, bar_y_top + bar_h + 18), _FONT, 0.34, amp_colour, 1, cv2.LINE_AA)
        cv2.putText(frame, "AMP", (bar_x - 2, bar_y_top - 14), _FONT, 0.34, _HUD_DIM, 1, cv2.LINE_AA)


class MicIndicator:
    def __init__(self):
        self._phase = 0.0

    def draw(self, frame, is_listening: bool, has_error: bool = False, dt: float = 0.016) -> None:
        h, w = frame.shape[:2]
        self._phase = (self._phase + dt * 3.0) % math.tau
        cx, cy = w - 26, 26
        if has_error:
            colour = (40, 40, 180)
        elif is_listening:
            pulse = 0.55 + 0.45 * math.sin(self._phase)
            colour = tuple(int(c * pulse) for c in (60, 200, 80))
        else:
            colour = (80, 80, 80)
        pulse = 0.7 if not is_listening else (0.55 + 0.45 * math.sin(self._phase))
        cv2.circle(frame, (cx, cy), int(9 + 2 * pulse), colour, 1, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), 5, colour, -1, cv2.LINE_AA)
        label = "MIC" if is_listening else "OFF"
        cv2.putText(frame, label, (cx - 10, cy + 20), _FONT, 0.35, colour, 1, cv2.LINE_AA)


class LetterDisplay:
    def draw(self, frame, visible_letters, effect_bgr) -> None:
        if not visible_letters:
            return
        h, _ = frame.shape[:2]
        overlay = frame.copy()
        for i, (letter, alpha) in enumerate(reversed(visible_letters)):
            y = h - 110 - i * 56
            if y < 60:
                break
            colour = tuple(int(c * alpha) for c in effect_bgr)
            _draw_text_shadow(overlay, letter, (32, y), _FONT_MONO, 1.8, colour, 2)
        cv2.addWeighted(overlay, 1.0, frame, 0.0, 0.0, frame)


class SpeechTextStrip:
    def __init__(self, display_duration: float = 2.5):
        self._text = ""
        self._ts = 0.0
        self._dur = display_duration

    def set_text(self, text: str) -> None:
        self._text = text
        self._ts = time.monotonic()

    def draw(self, frame) -> None:
        if not self._text:
            return
        age = time.monotonic() - self._ts
        if age > self._dur:
            self._text = ""
            return
        alpha = max(0.0, 1.0 - age / self._dur)
        h, w = frame.shape[:2]
        text = f"» {self._text}"
        scale = 0.60
        (tw, _), _ = cv2.getTextSize(text, _FONT, scale, 1)
        x, y = (w - tw) // 2, h - 28
        overlay = frame.copy()
        _draw_text_shadow(overlay, text, (x, y), _FONT, scale, (220, 220, 220), 1)
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0.0, frame)


class SentenceBannerDisplay:
    def draw(self, frame, banner_items, colour_state) -> None:
        if not banner_items:
            return
        now = time.monotonic()
        h, w = frame.shape[:2]
        y = h - 72
        overlay = frame.copy()
        for item in banner_items:
            age = now - item.timestamp
            progress = min(1.0, age / 12.0)
            x = int(w - progress * (w + 320))
            text = item.text.upper()
            colour = tuple(int(c * max(0.35, 1.0 - progress * 0.55)) for c in colour_state.bgr)
            _draw_text_shadow(overlay, text, (x, y), _FONT, 0.56, colour, 1)
            y -= 22
            if y < h - 130:
                break
        cv2.addWeighted(overlay, 0.92, frame, 0.08, 0.0, frame)


class PhonemeRibbonDisplay:
    def draw(self, frame, phoneme_state, colour_state) -> None:
        if not phoneme_state.tokens:
            return
        h, w = frame.shape[:2]
        base_y = h - 145
        x = 26
        for family, level in phoneme_state.family_levels.items():
            if level <= 0.02:
                continue
            colour = _PHONEME_FAMILY_COLOURS.get(family, colour_state.bgr)
            bar_w = int(18 + 46 * level)
            cv2.rectangle(frame, (x, base_y), (x + bar_w, base_y + 8), colour, -1)
            cv2.putText(frame, family[:3].upper(), (x, base_y - 4), _FONT, 0.28, colour, 1, cv2.LINE_AA)
            x += bar_w + 14
            if x > w - 180:
                break
        token_x = 28
        token_y = h - 165
        for token in phoneme_state.tokens[-8:]:
            colour = _PHONEME_FAMILY_COLOURS.get(token.family, colour_state.bgr)
            cv2.rectangle(frame, (token_x, token_y - 18), (token_x + 32, token_y + 6), (20, 20, 20), -1)
            cv2.rectangle(frame, (token_x, token_y - 18), (token_x + 32, token_y + 6), colour, 1)
            cv2.putText(frame, token.symbol, (token_x + 3, token_y), _FONT, 0.34, colour, 1, cv2.LINE_AA)
            token_x += 38
            if token_x > w - 120:
                break


@dataclass
class _ImageSlot:
    clip: object | None = None
    word: str = ""
    category: str = ""
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

    def trigger(self, clip, word, colour_bgr, style="glow", category: str = "") -> None:
        self._slot = _ImageSlot(
            clip=clip,
            word=word,
            category=category,
            colour_bgr=colour_bgr,
            entered_at=time.monotonic(),
            display_duration=self._display_duration,
            style=style,
        )

    def current_rect_norm(self, frame_shape) -> tuple[float, float, float, float] | None:
        if self._slot is None or not self._slot.is_alive() or self._slot.clip is None:
            return None
        h, w = frame_shape[:2]
        image = self._slot.clip.still
        ih, iw = image.shape[:2]
        x = max(0, min((w - iw) // 2, w - iw))
        y = max(0, min((h - ih) // 2 - 20, h - ih))
        return (x / max(w, 1), y / max(h, 1), iw / max(w, 1), ih / max(h, 1))

    def draw(self, frame, effect_bgr) -> None:
        if self._slot is None or not self._slot.is_alive() or self._slot.clip is None:
            self._slot = None
            return
        now = time.monotonic()
        dt = now - self._last_time
        self._last_time = now
        current_colour = self._colour_transition.update(effect_bgr, dt, speed=3.0)
        slot = self._slot
        alpha = slot.alpha()
        current = slot.clip.frame_at(now, slot.entered_at)
        highlighted = apply_highlight(current, current_colour, style=slot.style, intensity=0.85)
        ih, iw = highlighted.shape[:2]
        h, w = frame.shape[:2]
        x = max(0, min((w - iw) // 2, w - iw))
        y = max(0, min((h - ih) // 2 - 20, h - ih))
        _alpha_blend(frame, highlighted, x, y, alpha)
        label = f"{slot.word.upper()}  //  {slot.category.upper()}" if slot.category else slot.word.upper()
        label_y = y + ih + 22
        if label_y < h - 8:
            (lw, _), _ = cv2.getTextSize(label, _FONT, 0.72, 1)
            lx = x + (iw - lw) // 2
            _draw_text_shadow(frame, label, (lx, label_y), _FONT, 0.72, current_colour, 1)

    @property
    def is_active(self) -> bool:
        return self._slot is not None and self._slot.is_alive()


class SpawnedMediaDisplay:
    def draw(self, frame, spawns, colour_state) -> None:
        if not spawns:
            return
        now = time.monotonic()
        h, w = frame.shape[:2]
        for spawn in spawns:
            clip_frame = spawn.clip.frame_at(now, spawn.born_at)
            theme_hue = getattr(spawn.event.theme, "hue", colour_state.hue)
            theme_sat = getattr(spawn.event.theme, "saturation", colour_state.saturation)
            theme_val = getattr(spawn.event.theme, "value", colour_state.value)
            r, g, b = colorsys.hsv_to_rgb(theme_hue, theme_sat, theme_val)
            themed_bgr = (int(b * 255), int(g * 255), int(r * 255))
            highlighted = apply_highlight(clip_frame, themed_bgr, style="aura", intensity=0.82)
            scale = max(0.18, spawn.scale * 0.85)
            sprite = _scale_and_rotate(highlighted, scale, spawn.rotation)
            cx = int(spawn.x * w)
            cy = int(spawn.y * h)
            x = cx - sprite.shape[1] // 2
            y = cy - sprite.shape[0] // 2
            _alpha_blend(frame, sprite, x, y, spawn.alpha(now))
            label = spawn.event.word.upper()
            label_x = cx - 32
            label_y = y + sprite.shape[0] + 14
            if 0 < label_y < h - 8:
                _draw_text_shadow(frame, label, (label_x, label_y), _FONT, 0.40, themed_bgr, 1)


class AtmosphereBandLabel:
    def __init__(self):
        self._last_band = -1
        self._alpha = 0.0

    def draw(self, frame, colour_state, dt: float) -> None:
        h, w = frame.shape[:2]
        band = colour_state.band
        band_name = colour_state.band_name.upper()
        if band != self._last_band:
            self._alpha = 1.0
            self._last_band = band
        else:
            self._alpha = max(0.0, self._alpha - dt * 0.3)
        if self._alpha < 0.02:
            return
        text = f"✦ {band_name}"
        scale = 0.65
        (tw, _), _ = cv2.getTextSize(text, _FONT, scale, 1)
        x = w - tw - 60
        y = h - 55
        colour = tuple(int(c * self._alpha) for c in colour_state.bgr)
        _draw_text_shadow(frame, text, (x, y), _FONT, scale, colour, 1)


class ZoneLegend:
    def draw(self, frame, colour_state) -> None:
        h, w = frame.shape[:2]
        left = colour_state.left_zone
        right = colour_state.right_zone
        for zone, x in ((left, 20), (right, w - 190)):
            colour = zone.bgr if zone.active else (90, 90, 90)
            cv2.rectangle(frame, (x, h - 220), (x + 170, h - 190), (20, 20, 20), -1)
            cv2.rectangle(frame, (x, h - 220), (x + 170, h - 190), colour, 1)
            label = zone.label.upper()
            sub = zone.category.upper() if zone.category else "IDLE"
            cv2.putText(frame, label, (x + 8, h - 202), _FONT, 0.38, colour, 1, cv2.LINE_AA)
            cv2.putText(frame, sub, (x + 72, h - 202), _FONT, 0.34, colour, 1, cv2.LINE_AA)


class HUD:
    def __init__(self):
        self.finger_display = FingerCountDisplay()
        self.mic_indicator = MicIndicator()
        self.letter_display = LetterDisplay()
        self.animal_display = AnimalImageDisplay()
        self.spawn_display = SpawnedMediaDisplay()
        self.speech_strip = SpeechTextStrip()
        self.sentence_banner = SentenceBannerDisplay()
        self.phoneme_display = PhonemeRibbonDisplay()
        self.pitch_meter = PitchMeter()
        self.amplitude_meter = AmplitudeMeter()
        self.band_label = AtmosphereBandLabel()
        self.zone_legend = ZoneLegend()
