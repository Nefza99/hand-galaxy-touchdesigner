from __future__ import annotations

import threading
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .config import config_from_args, ensure_model_file
from .gestures import GestureEngine, GestureFrame, HandTelemetry
from .osc_bridge import OscBridge
from .virtual_camera import VirtualCameraPublisher, VirtualCameraSetupError


WINDOW_NAME = "Hand Galaxy Tracker"


class HandGalaxyApp:
    def __init__(self, config):
        self.config = config
        self.engine = GestureEngine(config)
        self.osc = OscBridge(config.osc_host, config.osc_port, send_landmarks=config.send_landmarks)
        self.virtual_camera = VirtualCameraPublisher(
            width=config.frame_width,
            height=config.frame_height,
            fps=max(24, min(config.camera_fps, 60)),
            enabled=config.virtual_cam,
        )
        self._lock = threading.Lock()
        self._latest_frame: GestureFrame | None = None
        self._display_fps = 0.0
        self._fps_frame_count = 0
        self._fps_last_time = time.perf_counter()
        self._started_at = time.perf_counter()

    def run(self) -> None:
        model_path = ensure_model_file(self.config)
        capture = cv2.VideoCapture(self.config.camera_index)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)
        capture.set(cv2.CAP_PROP_FPS, self.config.camera_fps)

        if not capture.isOpened():
            raise RuntimeError(f"Could not open webcam index {self.config.camera_index}")

        try:
            self.virtual_camera.start()
            options = vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.LIVE_STREAM,
                num_hands=self.config.max_hands,
                min_hand_detection_confidence=self.config.min_detection_confidence,
                min_hand_presence_confidence=self.config.min_presence_confidence,
                min_tracking_confidence=self.config.min_tracking_confidence,
                result_callback=self._on_result,
            )

            with vision.HandLandmarker.create_from_options(options) as landmarker:
                while True:
                    if self.config.max_seconds and (time.perf_counter() - self._started_at) >= self.config.max_seconds:
                        break

                    ok, frame = capture.read()
                    if not ok:
                        break

                    if self.config.mirror:
                        frame = cv2.flip(frame, 1)

                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                    timestamp_ms = int(time.perf_counter() * 1000)
                    landmarker.detect_async(mp_image, timestamp_ms)

                    with self._lock:
                        latest = self._latest_frame

                    preview_frame = self._draw_preview(frame, latest)
                    self.virtual_camera.send(preview_frame)
                    self._update_fps()

                    if self.config.preview:
                        cv2.imshow(WINDOW_NAME, preview_frame)
                        key = cv2.waitKey(1) & 0xFF
                        if key in (27, ord("q")):
                            break
        finally:
            capture.release()
            self.virtual_camera.close()
            if self.config.preview:
                cv2.destroyAllWindows()

    def _on_result(self, result, output_image, timestamp_ms: int) -> None:
        width = getattr(output_image, "width", None)
        height = getattr(output_image, "height", None)
        if callable(width):
            width = width()
        if callable(height):
            height = height()
        frame = self.engine.process(result, int(width or self.config.frame_width), int(height or self.config.frame_height), timestamp_ms)
        self.osc.send_frame(frame)
        with self._lock:
            self._latest_frame = frame

    def _draw_preview(self, frame, latest: GestureFrame | None):
        if latest is None:
            self._draw_header(frame, active_hands=0)
            return frame

        overlay = frame.copy()
        for color, hand in ((255, 160, 60), latest.secondary), ((80, 220, 255), latest.primary):
            if hand.active or hand.energy > 0.05:
                self._draw_hand_overlay(overlay, hand, color)

        cv2.addWeighted(overlay, 0.82, frame, 0.18, 0.0, frame)
        self._draw_header(frame, active_hands=latest.active_hands)
        return frame

    def _draw_hand_overlay(self, frame, hand: HandTelemetry, color_bgr: tuple[int, int, int]) -> None:
        h, w = frame.shape[:2]
        center = (int(hand.x * w), int(hand.y * h))
        thumb = (int(hand.thumb_x * w), int(hand.thumb_y * h))
        index = (int(hand.index_x * w), int(hand.index_y * h))
        radius_px = int(max(12, min(w, h) * (0.02 + hand.radius * 0.08)))

        cv2.line(frame, thumb, index, color_bgr, 2, cv2.LINE_AA)
        cv2.circle(frame, thumb, 7, color_bgr, -1, cv2.LINE_AA)
        cv2.circle(frame, index, 7, color_bgr, -1, cv2.LINE_AA)

        for ring in range(3):
            scale = 1.0 + ring * (0.35 + hand.energy * 0.25)
            alpha_radius = int(radius_px * scale)
            cv2.circle(frame, center, alpha_radius, color_bgr, 1, cv2.LINE_AA)

        if hand.trail:
            points = [(int(px * w), int(py * h)) for px, py in hand.trail]
            for idx in range(1, len(points)):
                thickness = max(1, idx // 2)
                cv2.line(frame, points[idx - 1], points[idx], color_bgr, thickness, cv2.LINE_AA)

        text = (
            f"{hand.label.upper()}  "
            f"PINCH {hand.pinch_norm:0.2f}  "
            f"VEL {hand.velocity:0.2f}  "
            f"BURST {hand.burst:0.2f}"
        )
        cv2.putText(frame, text, (center[0] + 18, center[1] - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.46, color_bgr, 1)

    def _draw_header(self, frame, active_hands: int) -> None:
        lines = [
            "HAND GALAXY // OSC -> TOUCHDESIGNER",
            f"HANDS {active_hands}  FPS {self._display_fps:0.1f}  OSC {self.config.osc_host}:{self.config.osc_port}",
            "ESC/Q TO QUIT",
        ]
        y = 26
        for line in lines:
            cv2.putText(frame, line, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (120, 255, 180), 1, cv2.LINE_AA)
            y += 22

    def _update_fps(self) -> None:
        self._fps_frame_count += 1
        now = time.perf_counter()
        elapsed = now - self._fps_last_time
        if elapsed >= 1.0:
            self._display_fps = self._fps_frame_count / elapsed
            self._fps_frame_count = 0
            self._fps_last_time = now


def main() -> None:
    config = config_from_args()
    app = HandGalaxyApp(config)
    try:
        app.run()
    except VirtualCameraSetupError as exc:
        print()
        print("HAND GALAXY // TOUCHDESIGNER MODE SETUP")
        print(exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
