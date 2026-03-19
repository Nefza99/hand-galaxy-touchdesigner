"""
main.py  v2.1.3
---------------
Hand Galaxy — full integrated system.
Adds pitch detection + atmospheric effects to v2.0 base.
"""
from __future__ import annotations
import logging, threading, time
from pathlib import Path
import cv2, mediapipe as mp, numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .config import AppConfig, config_from_args, ensure_model_file
from .gestures import GestureEngine, GestureFrame
from .osc_bridge import OscBridge
from .virtual_camera import VirtualCameraPublisher, VirtualCameraSetupError
# v2.0
from .finger_counter import FingerCounter
from .letter_parser import LetterMemory, parse_letters
from .animal_insect_parser import AnimalInsectParser, ALL_KEYWORDS
from .effect_colour_state import EffectColourState
from .asset_loader import AssetLoader
from .ui_overlay import HUD
# v2.1
from .audio_pipeline import AudioPipeline
from .speech_input import make_speech_input
from .pitch_detector import make_pitch_detector
from .vocal_range_tracker import VocalRangeTracker
from .pitch_effect_mapper import PitchEffectMapper
from .atmospheric_overlay import AtmosphericOverlay

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

WINDOW_NAME    = "Hand Galaxy v2.1.3"
_KEYWORD_LIST  = sorted(ALL_KEYWORDS)


class HandGalaxyApp:
    def __init__(self, config: AppConfig):
        self.config = config

        # ── Core gesture engine ──────────────────────────────────────────────
        self.engine = GestureEngine(config)
        self.osc    = OscBridge(config.osc_host, config.osc_port,
                                send_landmarks=config.send_landmarks)
        self.virtual_camera = VirtualCameraPublisher(
            width=config.frame_width, height=config.frame_height,
            fps=max(24, min(config.camera_fps, 60)), enabled=config.virtual_cam,
        )

        # ── v2.0 modules ─────────────────────────────────────────────────────
        self.finger_counter = FingerCounter(
            window_size=config.finger_count_window,
            hand_timeout_ms=config.finger_hand_timeout_ms,
        )
        self.letter_memory = LetterMemory(
            max_letters=config.letter_max_visible,
            display_duration=config.letter_display_duration,
            fade_duration=config.letter_fade_duration,
        )
        self.animal_parser = AnimalInsectParser(cooldown=config.animal_cooldown)
        self.colour_state  = EffectColourState(pitch_weight=config.pitch_weight)
        self.assets        = AssetLoader(config.assets_dir, display_size=config.image_display_size)
        self.hud           = HUD()
        self.hud.animal_display._display_duration = config.animal_display_duration

        # ── v2.1 — audio pipeline + pitch ────────────────────────────────────
        self.audio_pipeline:  AudioPipeline | None = None
        self.speech:          object | None        = None
        self.pitch_detector:  object | None        = None
        self.vocal_tracker    = VocalRangeTracker()
        self.pitch_mapper     = PitchEffectMapper()
        self.atm_overlay      = AtmosphericOverlay() if config.atmosphere_enabled else None

        audio_needed = config.speech_enabled or config.pitch_enabled
        if audio_needed:
            self.audio_pipeline = AudioPipeline(
                device_index=config.mic_device_index,
                block_size=config.audio_block_size,
            )

        if config.speech_enabled and self.audio_pipeline:
            self.speech = make_speech_input(config.vosk_model_path, self.audio_pipeline)
            if getattr(self.speech, "error", None):
                log.warning("Speech dependency issue: %s", self.speech.error)

        if config.pitch_enabled and self.audio_pipeline:
            self.pitch_detector = make_pitch_detector(
                self.audio_pipeline,
                confidence_threshold=config.pitch_confidence_thresh,
                smoothing_alpha=config.pitch_smoothing_alpha,
                vocal_low=config.vocal_low_hz,
                vocal_high=config.vocal_high_hz,
            )

        # ── Shared state ─────────────────────────────────────────────────────
        self._lock = threading.Lock()
        self._latest_frame: GestureFrame | None = None
        self._latest_finger_data: dict = {
            "total": 0, "primary": 0, "secondary": 0, "hands_active": False,
        }
        self._display_fps    = 0.0
        self._fps_count      = 0
        self._fps_last       = time.perf_counter()
        self._started_at     = time.perf_counter()
        self._last_dt        = 1 / 60.0
        self._latest_pitch   = None

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(self) -> None:
        model_path = ensure_model_file(self.config)
        cap = cv2.VideoCapture(self.config.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.config.frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)
        cap.set(cv2.CAP_PROP_FPS,          self.config.camera_fps)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open webcam {self.config.camera_index}")

        # Start audio pipeline first, then start any microphone consumers.
        audio_started = False
        if self.audio_pipeline:
            audio_started = self.audio_pipeline.start()
            if not audio_started:
                log.warning("Audio pipeline failed: %s", self.audio_pipeline.error)

        if self.speech and audio_started:
            speech_started = self.speech.start()
            if not speech_started:
                log.warning("Speech input unavailable: %s", getattr(self.speech, "error", "unknown error"))
        elif self.speech and self.config.speech_enabled:
            log.warning("Speech input not started because microphone capture is unavailable.")

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
                t_prev = time.perf_counter()
                while True:
                    if self.config.max_seconds and (
                        time.perf_counter() - self._started_at
                    ) >= self.config.max_seconds:
                        break

                    ok, frame = cap.read()
                    if not ok:
                        break

                    t_now         = time.perf_counter()
                    self._last_dt = min(t_now - t_prev, 0.1)
                    t_prev        = t_now

                    if self.config.mirror:
                        frame = cv2.flip(frame, 1)

                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    ts_ms  = int(time.perf_counter() * 1000)
                    landmarker.detect_async(mp_img, ts_ms)

                    with self._lock:
                        latest       = self._latest_frame
                        finger_data  = self._latest_finger_data.copy()

                    # Update pitch on main thread (thread-safe read)
                    if self.pitch_detector and getattr(self.pitch_detector, "is_ready", True):
                        pitch_result = self.pitch_detector.latest
                        vrange       = self.vocal_tracker.update(
                            pitch_result.hz, pitch_result.is_voiced
                        )
                        if vrange.is_calibrated:
                            self.pitch_detector.set_vocal_range(vrange.low, vrange.high)
                        pitch_params = self.pitch_mapper.update(pitch_result)
                        self._latest_pitch = pitch_result

                        self.osc.send_pitch(
                            pitch_result.hz,
                            pitch_result.normalised,
                            pitch_result.band,
                            pitch_result.confidence,
                            pitch_result.velocity,
                        )
                    else:
                        pitch_params = None

                    self._process_speech(latest)

                    preview = self._render_frame(frame, latest, finger_data, pitch_params)
                    self.virtual_camera.send(preview)
                    self._update_fps()

                    if self.config.preview:
                        cv2.imshow(WINDOW_NAME, preview)
                        if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                            break
        finally:
            if self.speech:
                self.speech.stop()
            if self.audio_pipeline:
                self.audio_pipeline.stop()
            cap.release()
            self.virtual_camera.close()
            if self.config.preview:
                cv2.destroyAllWindows()

    # ── MediaPipe callback ────────────────────────────────────────────────────

    def _on_result(self, result, output_image, timestamp_ms: int) -> None:
        w = getattr(output_image, "width", None)
        h = getattr(output_image, "height", None)
        if callable(w): w = w()
        if callable(h): h = h()
        frame = self.engine.process(
            result,
            int(w or self.config.frame_width),
            int(h or self.config.frame_height),
            timestamp_ms,
        )
        self.osc.send_frame(frame)
        finger_data = self.finger_counter.process(frame)
        self.osc.send_finger_counts(
            finger_data["total"], finger_data["primary"], finger_data["secondary"],
        )
        with self._lock:
            self._latest_frame       = frame
            self._latest_finger_data = finger_data

    # ── Speech processing ─────────────────────────────────────────────────────

    def _process_speech(self, gesture_frame: GestureFrame | None) -> None:
        if not self.speech:
            return
        for sr in self.speech.drain():
            if not sr.text:
                continue
            self.hud.speech_strip.set_text(sr.text.strip())
            if not sr.is_final:
                continue
            letters = parse_letters(sr.text)
            for letter in letters:
                self.letter_memory.add(letter)
                self.osc.send_letter_event(letter)
            event = self.animal_parser.parse(sr.text)
            if event:
                effect_bgr = self.colour_state.bgr
                img        = self.assets.get_animal(event.word)
                self.hud.animal_display.trigger(
                    img, event.word, effect_bgr, style=self.config.highlight_style,
                )
                self.osc.send_animal_event(event.word, _KEYWORD_LIST)
        self.osc.flush_pulses()

    # ── Frame rendering ───────────────────────────────────────────────────────

    def _render_frame(self, frame, latest, finger_data, pitch_params) -> np.ndarray:
        # Hand overlay art
        if latest is not None:
            overlay = frame.copy()
            for colour, hand in (((255,160,60), latest.secondary),
                                  ((80,220,255), latest.primary)):
                if hand.active or hand.energy > 0.05:
                    self._draw_hand_overlay(overlay, hand, colour)
            cv2.addWeighted(overlay, 0.82, frame, 0.18, 0.0, frame)

        # Update effect colour (gesture + pitch combined)
        cs = self.colour_state.update(
            latest if latest else self._make_null_frame(),
            pitch_params,
        )
        effect_bgr = cs.bgr

        # Send all OSC
        r, g, b = cs.rgb_float
        self.osc.send_effect_colour(r, g, b)
        self.osc.send_atmosphere(cs)

        # ── Atmospheric overlay ──────────────────────────────────────────────
        if self.atm_overlay is not None:
            self.atm_overlay.draw(frame, cs, self._last_dt)

        # ── HUD elements ─────────────────────────────────────────────────────
        self.hud.animal_display.draw(frame, effect_bgr)
        self.hud.finger_display.draw(frame, finger_data.get("total", 0),
                                     finger_data.get("hands_active", False), effect_bgr)
        self.hud.letter_display.draw(frame, self.letter_memory.visible(), effect_bgr)

        pitch_res = self._latest_pitch
        self.hud.pitch_meter.draw(frame, pitch_res, cs)
        self.hud.band_label.draw(frame, cs, self._last_dt)

        is_listening = getattr(self.speech, "is_listening", False) if self.speech else False
        has_error    = bool(getattr(self.speech, "error", None)) if self.speech else False
        self.hud.mic_indicator.draw(frame, is_listening, has_error, self._last_dt)
        self.hud.speech_strip.draw(frame)
        self._draw_header(frame, latest.active_hands if latest else 0)
        return frame

    def _make_null_frame(self):
        """Minimal stand-in when no gesture frame is available yet."""
        from .gestures import GestureFrame
        inactive = self.engine._inactive_telemetry("primary") if hasattr(self.engine, "_inactive_telemetry") else None
        if inactive is None:
            return None
        return GestureFrame(
            timestamp_ms=0, frame_width=self.config.frame_width,
            frame_height=self.config.frame_height, active_hands=0,
            primary=inactive, secondary=inactive,
        )

    def _draw_hand_overlay(self, frame, hand, color_bgr) -> None:
        h, w = frame.shape[:2]
        center = (int(hand.x * w), int(hand.y * h))
        thumb  = (int(hand.thumb_x * w), int(hand.thumb_y * h))
        index  = (int(hand.index_x * w), int(hand.index_y * h))
        r_px   = int(max(12, min(w, h) * (0.02 + hand.radius * 0.08)))
        cv2.line(frame, thumb, index, color_bgr, 2, cv2.LINE_AA)
        cv2.circle(frame, thumb, 7, color_bgr, -1, cv2.LINE_AA)
        cv2.circle(frame, index, 7, color_bgr, -1, cv2.LINE_AA)
        for ring in range(3):
            cv2.circle(frame, center,
                       int(r_px * (1.0 + ring * (0.35 + hand.energy * 0.25))),
                       color_bgr, 1, cv2.LINE_AA)
        if hand.trail:
            pts = [(int(px * w), int(py * h)) for px, py in hand.trail]
            for i in range(1, len(pts)):
                cv2.line(frame, pts[i-1], pts[i], color_bgr, max(1, i // 2), cv2.LINE_AA)
        cv2.putText(frame,
                    f"{hand.label.upper()}  PINCH {hand.pinch_norm:.2f}  VEL {hand.velocity:.2f}",
                    (center[0] + 18, center[1] - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, color_bgr, 1)

    def _draw_header(self, frame, active_hands: int) -> None:
        h, w = frame.shape[:2]
        pitch_res = self._latest_pitch
        band_txt  = pitch_res.band_name.upper() if pitch_res and pitch_res.is_voiced else "SILENT"
        hz_txt    = f"{int(pitch_res.hz)}Hz" if pitch_res and pitch_res.is_voiced else "---"
        speech_lbl = "SPEECH ON" if (self.speech and getattr(self.speech,"is_listening",False)) else "SPEECH OFF"
        lines = [
            f"HAND GALAXY v2.1.3  //  OSC @{self.config.osc_host}:{self.config.osc_port}",
            f"HANDS {active_hands}  FPS {self._display_fps:.1f}  {speech_lbl}  PITCH {hz_txt} [{band_txt}]",
        ]
        y = h - 58
        for line in lines:
            cv2.putText(frame, line, (16, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.44, (90, 180, 100), 1, cv2.LINE_AA)
            y += 20

    def _update_fps(self) -> None:
        self._fps_count += 1
        now = time.perf_counter()
        if (now - self._fps_last) >= 1.0:
            self._display_fps = self._fps_count / (now - self._fps_last)
            self._fps_count   = 0
            self._fps_last    = now


def main() -> None:
    config = config_from_args()
    app    = HandGalaxyApp(config)
    try:
        app.run()
    except VirtualCameraSetupError as exc:
        print(f"\nHAND GALAXY v2.1.3 // TOUCHDESIGNER SETUP\n{exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
