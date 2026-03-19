"""
osc_bridge.py  (v2.1)
---------------------
Extended OSC bridge — now sends pitch + atmospheric effect channels.
"""
from __future__ import annotations
from pythonosc.udp_client import SimpleUDPClient
from .gestures import GestureFrame, HandTelemetry


class OscBridge:
    def __init__(self, host: str, port: int, send_landmarks: bool = False):
        self.client          = SimpleUDPClient(host, port)
        self.send_landmarks  = send_landmarks
        self._letter_pulse   = False
        self._animal_pulse   = False

    # ── v1 ───────────────────────────────────────────────────────────────────

    def send_frame(self, frame: GestureFrame) -> None:
        self._send("/galaxy/system/timestamp_ms",  frame.timestamp_ms)
        self._send("/galaxy/system/frame_width",   frame.frame_width)
        self._send("/galaxy/system/frame_height",  frame.frame_height)
        self._send("/galaxy/system/active_hands",  frame.active_hands)
        self._send_hand("primary",   frame.primary)
        self._send_hand("secondary", frame.secondary)
        self._send_hand("main",      frame.primary)

    # ── v2.0 ─────────────────────────────────────────────────────────────────

    def send_finger_counts(self, total: int, primary: int, secondary: int) -> None:
        self._send("/galaxy/system/finger_count",           float(total))
        self._send("/galaxy/system/finger_count_primary",   float(primary))
        self._send("/galaxy/system/finger_count_secondary", float(secondary))

    def send_letter_event(self, letter: str) -> None:
        ascii_val = ord(letter.upper()) if letter else 0
        self._send("/galaxy/speech/letter_ascii",   float(ascii_val))
        self._send("/galaxy/speech/letter_trigger", 1.0)
        self._letter_pulse = True

    def send_animal_event(self, word: str, keyword_list: list[str]) -> None:
        idx = keyword_list.index(word) if word in keyword_list else -1
        self._send("/galaxy/speech/animal_trigger", 1.0)
        self._send("/galaxy/speech/animal_id",      float(idx))
        self._animal_pulse = True

    def send_effect_colour(self, r: float, g: float, b: float) -> None:
        self._send("/galaxy/effect/r", r)
        self._send("/galaxy/effect/g", g)
        self._send("/galaxy/effect/b", b)

    # ── v2.1 — pitch + atmosphere ─────────────────────────────────────────

    def send_pitch(self, hz: float, normalised: float,
                   band: int, confidence: float, velocity: float) -> None:
        self._send("/galaxy/pitch/hz",          hz)
        self._send("/galaxy/pitch/normalised",  normalised)
        self._send("/galaxy/pitch/band",        float(band))
        self._send("/galaxy/pitch/confidence",  confidence)
        self._send("/galaxy/pitch/velocity",    velocity)

    def send_atmosphere(self, cs) -> None:
        """Send all ColourState atmospheric parameters."""
        self._send("/galaxy/atmosphere/feedback",        cs.feedback)
        self._send("/galaxy/atmosphere/particle_speed",  cs.particle_speed)
        self._send("/galaxy/atmosphere/bloom",           cs.bloom)
        self._send("/galaxy/atmosphere/vignette",        cs.vignette)
        self._send("/galaxy/atmosphere/shimmer",         cs.shimmer)
        self._send("/galaxy/atmosphere/fog",             cs.fog)
        self._send("/galaxy/atmosphere/burst_coeff",     cs.burst_coeff)
        self._send("/galaxy/atmosphere/band",            float(cs.band))

    def flush_pulses(self) -> None:
        if self._letter_pulse:
            self._send("/galaxy/speech/letter_trigger", 0.0)
            self._letter_pulse = False
        if self._animal_pulse:
            self._send("/galaxy/speech/animal_trigger", 0.0)
            self._animal_pulse = False

    # ── internal ─────────────────────────────────────────────────────────────

    def _send_hand(self, slot: str, hand: HandTelemetry) -> None:
        prefix = f"/galaxy/{slot}"
        values = {
            "active": 1.0 if hand.active else 0.0,
            "handedness": hand.handedness_value, "score": hand.score,
            "x": hand.x, "y": hand.y, "x_raw": hand.x_raw, "y_raw": hand.y_raw,
            "thumb_x": hand.thumb_x, "thumb_y": hand.thumb_y,
            "index_x": hand.index_x, "index_y": hand.index_y,
            "wrist_x": hand.wrist_x, "wrist_y": hand.wrist_y,
            "world_x": hand.world_x, "world_y": hand.world_y, "world_z": hand.world_z,
            "pinch_raw": hand.pinch_raw, "pinch": hand.pinch_norm,
            "radius": hand.radius, "velocity": hand.velocity,
            "dx": hand.dx, "dy": hand.dy, "spin": hand.spin,
            "burst": hand.burst, "energy": hand.energy,
            "depth": hand.depth, "angle": hand.angle,
            "pinch_active": 1.0 if hand.pinch_active else 0.0,
            "open": 1.0 if hand.open_state else 0.0,
            "just_pinched": 1.0 if hand.just_pinched else 0.0,
            "just_released": 1.0 if hand.just_released else 0.0,
            "trail_len": float(len(hand.trail)),
        }
        for key, value in values.items():
            self._send(f"{prefix}/{key}", value)
        if self.send_landmarks:
            for idx, point in enumerate(hand.landmarks):
                self._send(f"{prefix}/landmark/{idx}/x", point[0])
                self._send(f"{prefix}/landmark/{idx}/y", point[1])
                self._send(f"{prefix}/landmark/{idx}/z", point[2])
            for idx, point in enumerate(hand.trail[-8:]):
                self._send(f"{prefix}/trail/{idx}/x", point[0])
                self._send(f"{prefix}/trail/{idx}/y", point[1])

    def _send(self, address: str, value: float | int) -> None:
        self.client.send_message(address, value)
