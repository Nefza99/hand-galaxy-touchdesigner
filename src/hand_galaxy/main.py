"""
Hand Galaxy runtime.
"""
from __future__ import annotations

import logging
import threading
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .animal_insect_parser import AnimalInsectParser
from .asset_loader import AssetLoader
from .atmospheric_overlay import AtmosphericOverlay
from .audio_features import AudioFeatureTracker, AudioFeatures
from .audio_pipeline import AudioPipeline
from .config import AppConfig, config_from_args, ensure_model_file
from .effect_colour_state import EffectColourState
from .finger_counter import FingerCounter
from .gestures import GestureEngine, GestureFrame
from .letter_parser import LetterMemory, parse_letters
from .midi_bridge import MidiBridge
from .osc_bridge import OscBridge
from .pitch_detector import make_pitch_detector
from .pitch_effect_mapper import PitchEffectMapper
from .spawn_controller import SpawnController
from .speech_analysis import PhonemeTracker, SentenceBanner
from .speech_input import make_speech_input
from .ui_overlay import HUD
from .virtual_camera import VirtualCameraPublisher, VirtualCameraSetupError
from .vocal_range_tracker import VocalRangeTracker

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

WINDOW_NAME = "Hand Galaxy v2.2.0"


class HandGalaxyApp:
    def __init__(self, config: AppConfig):
        self.config = config

        self.engine = GestureEngine(config)
        self.osc = OscBridge(config.osc_host, config.osc_port, send_landmarks=config.send_landmarks)
        self.virtual_camera = VirtualCameraPublisher(
            width=config.frame_width,
            height=config.frame_height,
            fps=max(24, min(config.camera_fps, 60)),
            enabled=config.virtual_cam,
        )

        self.finger_counter = FingerCounter(
            window_size=config.finger_count_window,
            hand_timeout_ms=config.finger_hand_timeout_ms,
        )
        self.letter_memory = LetterMemory(
            max_letters=config.letter_max_visible,
            display_duration=config.letter_display_duration,
            fade_duration=config.letter_fade_duration,
        )
        self.animal_parser = AnimalInsectParser(
            cooldown=config.animal_cooldown,
            keywords_dir=config.keywords_dir,
        )
        self._keyword_list = self.animal_parser.keyword_list
        self.colour_state = EffectColourState(pitch_weight=config.pitch_weight)
        self.assets = AssetLoader(config.assets_dir, display_size=config.image_display_size)
        self.hud = HUD()
        self.hud.animal_display._display_duration = config.animal_display_duration
        self.spawn_controller = SpawnController(prompt_duration=config.animal_display_duration)
        self.sentence_banner = SentenceBanner()
        self.phoneme_tracker = PhonemeTracker()
        self.midi = MidiBridge(enabled=config.midi_enabled, port_name=config.midi_port)

        self.audio_pipeline: AudioPipeline | None = None
        self.audio_features: AudioFeatureTracker | None = None
        self.speech: object | None = None
        self.pitch_detector: object | None = None
        self.vocal_tracker = VocalRangeTracker()
        self.pitch_mapper = PitchEffectMapper()
        self.atm_overlay = AtmosphericOverlay() if config.atmosphere_enabled else None

        audio_needed = config.speech_enabled or config.pitch_enabled or config.midi_enabled
        if audio_needed:
            self.audio_pipeline = AudioPipeline(
                device_index=config.mic_device_index,
                block_size=config.audio_block_size,
            )
            self.audio_features = AudioFeatureTracker(self.audio_pipeline)

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

        self._lock = threading.Lock()
        self._latest_frame: GestureFrame | None = None
        self._latest_finger_data: dict = {
            "total": 0,
            "primary": 0,
            "secondary": 0,
            "hands_active": False,
        }
        self._display_fps = 0.0
        self._fps_count = 0
        self._fps_last = time.perf_counter()
        self._started_at = time.perf_counter()
        self._last_dt = 1 / 60.0
        self._latest_pitch = None
        self._latest_audio = AudioFeatures()
        self._latest_partial_text = ""
        self._latest_phoneme = self.phoneme_tracker.latest

    def run(self) -> None:
        model_path = ensure_model_file(self.config)
        cap = cv2.VideoCapture(self.config.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)
        cap.set(cv2.CAP_PROP_FPS, self.config.camera_fps)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open webcam {self.config.camera_index}")

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
                    if self.config.max_seconds and (time.perf_counter() - self._started_at) >= self.config.max_seconds:
                        break
                    ok, frame = cap.read()
                    if not ok:
                        break

                    t_now = time.perf_counter()
                    self._last_dt = min(t_now - t_prev, 0.1)
                    t_prev = t_now

                    if self.config.mirror:
                        frame = cv2.flip(frame, 1)

                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    ts_ms = int(time.perf_counter() * 1000)
                    landmarker.detect_async(mp_img, ts_ms)

                    with self._lock:
                        latest = self._latest_frame
                        finger_data = self._latest_finger_data.copy()

                    if self.audio_features:
                        self._latest_audio = self.audio_features.latest

                    if self.pitch_detector and getattr(self.pitch_detector, "is_ready", True):
                        pitch_result = self.pitch_detector.latest
                        vrange = self.vocal_tracker.update(pitch_result.hz, pitch_result.is_voiced)
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

                    self._process_speech()
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
            self.midi.close()
            cap.release()
            self.virtual_camera.close()
            if self.config.preview:
                cv2.destroyAllWindows()

    def _on_result(self, result, output_image, timestamp_ms: int) -> None:
        w = getattr(output_image, "width", None)
        h = getattr(output_image, "height", None)
        if callable(w):
            w = w()
        if callable(h):
            h = h()
        frame = self.engine.process(
            result,
            int(w or self.config.frame_width),
            int(h or self.config.frame_height),
            timestamp_ms,
        )
        self.osc.send_frame(frame)
        finger_data = self.finger_counter.process(frame)
        self.osc.send_finger_counts(
            finger_data["total"],
            finger_data["primary"],
            finger_data["secondary"],
        )
        with self._lock:
            self._latest_frame = frame
            self._latest_finger_data = finger_data

    def _process_speech(self) -> None:
        if not self.speech:
            return
        for sr in self.speech.drain():
            clean_text = sr.text.strip()
            if not clean_text:
                continue
            self.hud.speech_strip.set_text(clean_text)
            self._latest_partial_text = clean_text if not sr.is_final else ""
            self._latest_phoneme = self.phoneme_tracker.update(clean_text)
            if not sr.is_final:
                continue

            self.sentence_banner.push(clean_text)
            letters = parse_letters(clean_text)
            for letter in letters:
                self.letter_memory.add(letter)
                self.osc.send_letter_event(letter)

            for event in self.animal_parser.parse_all(clean_text):
                clip = self.assets.get_clip(event.asset_name, category=event.category)
                self.spawn_controller.set_prompt(event, clip)
                self.hud.animal_display.trigger(
                    clip,
                    event.word,
                    self.colour_state.bgr,
                    style=self.config.highlight_style,
                    category=event.category,
                )
                self.osc.send_animal_event(event.word, self._keyword_list)
        self.osc.flush_pulses()

    def _render_frame(self, frame, latest, finger_data, pitch_params) -> np.ndarray:
        gesture_frame = latest if latest else self._make_null_frame()
        prompt_rect = self.hud.animal_display.current_rect_norm(frame.shape)
        self.spawn_controller.update(gesture_frame, prompt_rect)
        hand_themes = self.spawn_controller.active_hand_themes(gesture_frame)

        cs = self.colour_state.update(
            gesture_frame,
            pitch_params,
            amplitude=self._latest_audio,
            hand_themes=hand_themes,
        )

        overlay = frame.copy()
        for hand, zone in ((gesture_frame.left, cs.left_zone), (gesture_frame.right, cs.right_zone)):
            if hand.active or hand.energy > 0.05:
                self._draw_hand_overlay(overlay, hand, zone.bgr)
        cv2.addWeighted(overlay, 0.84, frame, 0.16, 0.0, frame)

        self.osc.send_effect_colour(cs)
        self.osc.send_atmosphere(cs)
        self.osc.send_audio_features(self._latest_audio)
        banner_items = self.sentence_banner.items()
        self.osc.send_speech_state(self._latest_partial_text, len(banner_items), self._latest_phoneme)
        self.osc.send_spawn_state(self.spawn_controller.spawn_count())
        self.midi.update(gesture_frame, self._latest_pitch, self._latest_audio, hand_themes)

        if self.atm_overlay is not None:
            self.atm_overlay.draw(frame, cs, self._last_dt)

        self.hud.spawn_display.draw(frame, self.spawn_controller.spawns, cs)
        self.hud.animal_display.draw(frame, cs.bgr)
        self.hud.finger_display.draw(frame, finger_data.get("total", 0), finger_data.get("hands_active", False), cs.bgr)
        self.hud.letter_display.draw(frame, self.letter_memory.visible(), cs.bgr)
        self.hud.pitch_meter.draw(frame, self._latest_pitch, cs)
        self.hud.amplitude_meter.draw(frame, self._latest_audio, cs)
        self.hud.zone_legend.draw(frame, cs)
        self.hud.band_label.draw(frame, cs, self._last_dt)
        is_listening = getattr(self.speech, "is_listening", False) if self.speech else False
        has_error = bool(getattr(self.speech, "error", None)) if self.speech else False
        self.hud.mic_indicator.draw(frame, is_listening, has_error, self._last_dt)
        self.hud.phoneme_display.draw(frame, self._latest_phoneme, cs)
        self.hud.sentence_banner.draw(frame, banner_items, cs)
        self.hud.speech_strip.draw(frame)
        self._draw_header(frame, gesture_frame.active_hands)
        return frame

    def _make_null_frame(self):
        inactive = self.engine._inactive_telemetry("primary") if hasattr(self.engine, "_inactive_telemetry") else None
        if inactive is None:
            return None
        left = self.engine._inactive_telemetry("left")
        right = self.engine._inactive_telemetry("right")
        return GestureFrame(
            timestamp_ms=0,
            frame_width=self.config.frame_width,
            frame_height=self.config.frame_height,
            active_hands=0,
            left=left,
            right=right,
            primary=inactive,
            secondary=inactive,
        )

    def _draw_hand_overlay(self, frame, hand, color_bgr) -> None:
        h, w = frame.shape[:2]
        center = (int(hand.x * w), int(hand.y * h))
        thumb = (int(hand.thumb_x * w), int(hand.thumb_y * h))
        index = (int(hand.index_x * w), int(hand.index_y * h))
        r_px = int(max(12, min(w, h) * (0.02 + hand.radius * 0.08)))
        cv2.line(frame, thumb, index, color_bgr, 2, cv2.LINE_AA)
        cv2.circle(frame, thumb, 7, color_bgr, -1, cv2.LINE_AA)
        cv2.circle(frame, index, 7, color_bgr, -1, cv2.LINE_AA)
        for ring in range(3):
            cv2.circle(
                frame,
                center,
                int(r_px * (1.0 + ring * (0.35 + hand.energy * 0.25))),
                color_bgr,
                1,
                cv2.LINE_AA,
            )
        if hand.trail:
            pts = [(int(px * w), int(py * h)) for px, py in hand.trail]
            for i in range(1, len(pts)):
                cv2.line(frame, pts[i - 1], pts[i], color_bgr, max(1, i // 2), cv2.LINE_AA)
        cv2.putText(
            frame,
            f"{hand.label.upper()}  PINCH {hand.pinch_norm:.2f}  VEL {hand.velocity:.2f}",
            (center[0] + 18, center[1] - 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.46,
            color_bgr,
            1,
        )

    def _draw_header(self, frame, active_hands: int) -> None:
        h, _ = frame.shape[:2]
        pitch_res = self._latest_pitch
        band_txt = pitch_res.band_name.upper() if pitch_res and pitch_res.is_voiced else "SILENT"
        hz_txt = f"{int(pitch_res.hz)}Hz" if pitch_res and pitch_res.is_voiced else "---"
        speech_lbl = "SPEECH ON" if (self.speech and getattr(self.speech, "is_listening", False)) else "SPEECH OFF"
        midi_lbl = f"MIDI {self.midi.status.port_name}" if self.midi.status.enabled else "MIDI OFF"
        amp_txt = f"AMP {self._latest_audio.amplitude:.2f}"
        lines = [
            f"HAND GALAXY v2.2.0  //  OSC @{self.config.osc_host}:{self.config.osc_port}",
            f"HANDS {active_hands}  FPS {self._display_fps:.1f}  {speech_lbl}  PITCH {hz_txt} [{band_txt}]  {amp_txt}",
            midi_lbl,
        ]
        y = h - 58
        for line in lines:
            cv2.putText(frame, line, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (90, 180, 100), 1, cv2.LINE_AA)
            y += 20

    def _update_fps(self) -> None:
        self._fps_count += 1
        now = time.perf_counter()
        if (now - self._fps_last) >= 1.0:
            self._display_fps = self._fps_count / (now - self._fps_last)
            self._fps_count = 0
            self._fps_last = now


def main() -> None:
    config = config_from_args()
    app = HandGalaxyApp(config)
    try:
        app.run()
    except VirtualCameraSetupError as exc:
        print(f"\nHAND GALAXY v2.2.0 // TOUCHDESIGNER SETUP\n{exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
