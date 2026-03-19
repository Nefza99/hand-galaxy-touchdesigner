from __future__ import annotations

from pythonosc.udp_client import SimpleUDPClient

from .gestures import GestureFrame, HandTelemetry


class OscBridge:
    def __init__(self, host: str, port: int, send_landmarks: bool = False):
        self.client = SimpleUDPClient(host, port)
        self.send_landmarks = send_landmarks

    def send_frame(self, frame: GestureFrame) -> None:
        self._send("/galaxy/system/timestamp_ms", frame.timestamp_ms)
        self._send("/galaxy/system/frame_width", frame.frame_width)
        self._send("/galaxy/system/frame_height", frame.frame_height)
        self._send("/galaxy/system/active_hands", frame.active_hands)
        self._send_hand("primary", frame.primary)
        self._send_hand("secondary", frame.secondary)
        self._send_hand("main", frame.primary)

    def _send_hand(self, slot: str, hand: HandTelemetry) -> None:
        prefix = f"/galaxy/{slot}"
        values = {
            "active": 1.0 if hand.active else 0.0,
            "handedness": hand.handedness_value,
            "score": hand.score,
            "x": hand.x,
            "y": hand.y,
            "x_raw": hand.x_raw,
            "y_raw": hand.y_raw,
            "thumb_x": hand.thumb_x,
            "thumb_y": hand.thumb_y,
            "index_x": hand.index_x,
            "index_y": hand.index_y,
            "wrist_x": hand.wrist_x,
            "wrist_y": hand.wrist_y,
            "world_x": hand.world_x,
            "world_y": hand.world_y,
            "world_z": hand.world_z,
            "pinch_raw": hand.pinch_raw,
            "pinch": hand.pinch_norm,
            "radius": hand.radius,
            "velocity": hand.velocity,
            "dx": hand.dx,
            "dy": hand.dy,
            "spin": hand.spin,
            "burst": hand.burst,
            "energy": hand.energy,
            "depth": hand.depth,
            "angle": hand.angle,
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
