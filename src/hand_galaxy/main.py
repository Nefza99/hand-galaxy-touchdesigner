from __future__ import annotations

import threading
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .config import config_from_args, ensure_model_file
from .gestures import FusionTelemetry, GestureFrame, HandTelemetry, GestureEngine
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
        if latest.fusion.active:
            self._draw_fusion_overlay(overlay, latest.fusion, latest.primary, latest.secondary)

        for hand in (latest.secondary, latest.primary):
            if hand.active or hand.energy > 0.05:
                self._draw_hand_overlay(overlay, hand)

        cv2.addWeighted(overlay, 0.84, frame, 0.16, 0.0, frame)
        self._draw_header(frame, active_hands=latest.active_hands, fusion=latest.fusion)
        return frame

    def _draw_hand_overlay(self, frame, hand: HandTelemetry) -> None:
        h, w = frame.shape[:2]
        center = (int(hand.x * w), int(hand.y * h))
        thumb = (int(hand.thumb_x * w), int(hand.thumb_y * h))
        index = (int(hand.index_x * w), int(hand.index_y * h))
        color_bgr = self._color_bgr(hand.color_r, hand.color_g, hand.color_b, fallback=(255, 180, 80))
        accent_bgr = self._brighten_bgr(color_bgr, 1.28)
        radius_px = int(max(12, min(w, h) * (0.02 + hand.radius * 0.08)))
        halo_radius = int(radius_px * (1.25 + hand.halo * 1.35 + hand.pulse * 0.22))
        flare_radius = int(radius_px * (0.55 + hand.flare * 0.95))
        core_radius = int(max(4, radius_px * (0.3 + hand.pinch_norm * 0.35 + hand.flare * 0.2)))

        cv2.line(frame, thumb, index, accent_bgr, max(1, int(1 + hand.vortex * 2)), cv2.LINE_AA)
        cv2.circle(frame, thumb, 7, accent_bgr, -1, cv2.LINE_AA)
        cv2.circle(frame, index, 7, accent_bgr, -1, cv2.LINE_AA)

        for ring in range(3):
            scale = 1.0 + ring * (0.32 + hand.halo * 0.28) + hand.pulse * 0.15
            alpha_radius = int(radius_px * scale)
            thickness = max(1, int(1 + hand.shimmer * 1.5 + ring))
            cv2.circle(frame, center, alpha_radius, color_bgr, thickness, cv2.LINE_AA)

        cv2.circle(frame, center, halo_radius, accent_bgr, max(1, int(1 + hand.halo * 2)), cv2.LINE_AA)
        cv2.circle(frame, center, flare_radius, accent_bgr, max(1, int(1 + hand.flare * 2)), cv2.LINE_AA)
        cv2.circle(frame, center, core_radius, accent_bgr, -1, cv2.LINE_AA)

        if hand.trail:
            points = [(int(px * w), int(py * h)) for px, py in hand.trail]
            for idx in range(1, len(points)):
                thickness = max(1, int(1 + hand.ribbon * 2 + idx / 7))
                cv2.line(frame, points[idx - 1], points[idx], color_bgr, thickness, cv2.LINE_AA)

        text = (
            f"{hand.label.upper()}  PINCH {hand.pinch_norm:0.2f}  "
            f"VEL {hand.velocity:0.2f}  BURST {hand.burst:0.2f}"
        )
        fx_text = (
            f"HUE {hand.hue:0.2f}  VTX {hand.vortex:0.2f}  "
            f"FLR {hand.flare:0.2f}  SHIM {hand.shimmer:0.2f}"
        )
        cv2.putText(frame, text, (center[0] + 18, center[1] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.46, accent_bgr, 1)
        cv2.putText(frame, fx_text, (center[0] + 18, center[1] + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.43, color_bgr, 1)

    def _draw_fusion_overlay(
        self,
        frame,
        fusion: FusionTelemetry,
        primary: HandTelemetry,
        secondary: HandTelemetry,
    ) -> None:
        h, w = frame.shape[:2]
        p1 = (int(primary.x * w), int(primary.y * h))
        p2 = (int(secondary.x * w), int(secondary.y * h))
        midpoint = (int(fusion.x * w), int(fusion.y * h))
        color_bgr = self._color_bgr(fusion.color_r, fusion.color_g, fusion.color_b, fallback=(255, 255, 180))
        accent_bgr = self._brighten_bgr(color_bgr, 1.25)
        thickness = max(1, int(1 + fusion.bridge * 4))
        midpoint_radius = int(14 + fusion.bridge * 24 + fusion.bloom * 18)

        cv2.line(frame, p1, p2, color_bgr, thickness, cv2.LINE_AA)
        cv2.circle(frame, midpoint, midpoint_radius, accent_bgr, max(1, int(1 + fusion.bloom * 2)), cv2.LINE_AA)
        cv2.circle(frame, midpoint, int(5 + fusion.pulse * 10), accent_bgr, -1, cv2.LINE_AA)

        text = f"FUSION {fusion.bridge:0.2f}  BLOOM {fusion.bloom:0.2f}  CHAOS {fusion.chaos:0.2f}"
        cv2.putText(
            frame,
            text,
            (midpoint[0] - 120, midpoint[1] - midpoint_radius - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.44,
            accent_bgr,
            1,
            cv2.LINE_AA,
        )

    def _draw_header(self, frame, active_hands: int, fusion: FusionTelemetry | None = None) -> None:
        lines = [
            "HAND GALAXY // OSC -> TOUCHDESIGNER",
            f"HANDS {active_hands}  FPS {self._display_fps:0.1f}  OSC {self.config.osc_host}:{self.config.osc_port}",
        ]
        if fusion and fusion.active:
            lines.append(f"FUSION BRIDGE {fusion.bridge:0.2f}  BLOOM {fusion.bloom:0.2f}  VORTEX {fusion.vortex:0.2f}")
        lines.append("ESC/Q TO QUIT")

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

    def _color_bgr(
        self,
        red: float,
        green: float,
        blue: float,
        fallback: tuple[int, int, int],
    ) -> tuple[int, int, int]:
        if red <= 0.0 and green <= 0.0 and blue <= 0.0:
            return fallback
        return (
            int(max(0, min(255, blue * 255.0))),
            int(max(0, min(255, green * 255.0))),
            int(max(0, min(255, red * 255.0))),
        )

    def _brighten_bgr(self, color_bgr: tuple[int, int, int], gain: float) -> tuple[int, int, int]:
        return tuple(int(max(0, min(255, channel * gain + 18))) for channel in color_bgr)


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
