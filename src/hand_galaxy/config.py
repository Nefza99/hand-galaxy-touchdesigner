"""config.py  v2.1 — all settings including pitch."""
from __future__ import annotations
import argparse, urllib.request
from dataclasses import dataclass
from pathlib import Path

MODEL_URL         = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
                     "hand_landmarker/float16/1/hand_landmarker.task")
PROJECT_ROOT      = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "hand_landmarker.task"
DEFAULT_VOSK_PATH  = PROJECT_ROOT / "models" / "vosk" / "vosk-model-small-en-us-0.15"
DEFAULT_ASSETS_DIR = PROJECT_ROOT / "assets"


@dataclass(slots=True)
class AppConfig:
    # Hand model
    model_path: Path = DEFAULT_MODEL_PATH
    model_url:  str  = MODEL_URL
    # Camera
    camera_index:  int = 0
    frame_width:   int = 1280
    frame_height:  int = 720
    camera_fps:    int = 60
    # OSC
    osc_host: str = "127.0.0.1"
    osc_port: int = 7000
    # Tracking
    max_hands:       int  = 2
    preview:         bool = True
    mirror:          bool = True
    send_landmarks:  bool = False
    virtual_cam:     bool = False
    # Smoothing
    position_smoothing:       float = 0.28
    pinch_smoothing:          float = 0.24
    velocity_smoothing:       float = 0.2
    pinch_close_threshold:    float = 0.055
    pinch_open_threshold:     float = 0.075
    velocity_burst_threshold: float = 0.45
    idle_timeout_ms:          int   = 180
    # MediaPipe confidence
    min_detection_confidence: float = 0.55
    min_presence_confidence:  float = 0.45
    min_tracking_confidence:  float = 0.45
    max_seconds: float | None = None
    # Finger counting
    finger_count_window:    int = 6
    finger_hand_timeout_ms: int = 300
    # Audio pipeline
    mic_device_index: int | None = None
    audio_block_size: int        = 512
    # Speech
    speech_enabled:   bool = True
    vosk_model_path:  Path = DEFAULT_VOSK_PATH
    # Letters
    letter_display_duration: float = 3.5
    letter_fade_duration:    float = 1.0
    letter_max_visible:      int   = 8
    # Animals
    animal_cooldown:         float = 4.0
    animal_display_duration: float = 6.0
    # Assets
    assets_dir:         Path           = DEFAULT_ASSETS_DIR
    image_display_size: tuple[int,int] = (320, 320)
    highlight_style:    str            = "glow"
    # Pitch detection
    pitch_enabled:           bool  = True
    pitch_confidence_thresh: float = 0.50
    pitch_smoothing_alpha:   float = 0.35
    pitch_weight:            float = 0.60   # 0=gesture-only 1=pitch-only
    vocal_low_hz:            float = 80.0
    vocal_high_hz:           float = 1100.0
    # Atmosphere
    atmosphere_enabled: bool = True


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Hand Galaxy v2.1")
    p.add_argument("--model-path",            type=Path,  default=DEFAULT_MODEL_PATH)
    p.add_argument("--camera-index",          type=int,   default=0)
    p.add_argument("--frame-width",           type=int,   default=1280)
    p.add_argument("--frame-height",          type=int,   default=720)
    p.add_argument("--camera-fps",            type=int,   default=60)
    p.add_argument("--osc-host",              default="127.0.0.1")
    p.add_argument("--osc-port",              type=int,   default=7000)
    p.add_argument("--max-hands",             type=int,   default=2)
    p.add_argument("--send-landmarks",        action="store_true")
    p.add_argument("--virtual-cam",           action="store_true")
    p.add_argument("--no-preview",            action="store_true")
    p.add_argument("--no-mirror",             action="store_true")
    p.add_argument("--position-smoothing",    type=float, default=0.28)
    p.add_argument("--pinch-smoothing",       type=float, default=0.24)
    p.add_argument("--velocity-smoothing",    type=float, default=0.20)
    p.add_argument("--pinch-close-threshold", type=float, default=0.055)
    p.add_argument("--pinch-open-threshold",  type=float, default=0.075)
    p.add_argument("--velocity-burst-threshold", type=float, default=0.45)
    p.add_argument("--idle-timeout-ms",       type=int,   default=180)
    p.add_argument("--min-detection-confidence", type=float, default=0.55)
    p.add_argument("--min-presence-confidence",  type=float, default=0.45)
    p.add_argument("--min-tracking-confidence",  type=float, default=0.45)
    p.add_argument("--max-seconds",           type=float, default=None)
    p.add_argument("--vosk-model-path",       type=Path,  default=DEFAULT_VOSK_PATH)
    p.add_argument("--mic-device-index",      type=int,   default=None)
    p.add_argument("--no-speech",             action="store_true")
    p.add_argument("--animal-cooldown",       type=float, default=4.0)
    p.add_argument("--animal-display-duration", type=float, default=6.0)
    p.add_argument("--assets-dir",            type=Path,  default=DEFAULT_ASSETS_DIR)
    p.add_argument("--highlight-style",       default="glow",
                   choices=["glow","rim","aura","tint"])
    p.add_argument("--no-pitch",              action="store_true")
    p.add_argument("--pitch-confidence-thresh", type=float, default=0.50)
    p.add_argument("--pitch-weight",          type=float, default=0.60)
    p.add_argument("--no-atmosphere",         action="store_true")
    return p


def config_from_args(argv=None) -> AppConfig:
    args = build_arg_parser().parse_args(argv)
    return AppConfig(
        model_path=args.model_path,
        camera_index=args.camera_index,
        frame_width=args.frame_width,
        frame_height=args.frame_height,
        camera_fps=args.camera_fps,
        osc_host=args.osc_host,
        osc_port=args.osc_port,
        max_hands=args.max_hands,
        preview=not args.no_preview,
        mirror=not args.no_mirror,
        send_landmarks=args.send_landmarks,
        virtual_cam=args.virtual_cam,
        position_smoothing=args.position_smoothing,
        pinch_smoothing=args.pinch_smoothing,
        velocity_smoothing=args.velocity_smoothing,
        pinch_close_threshold=args.pinch_close_threshold,
        pinch_open_threshold=args.pinch_open_threshold,
        velocity_burst_threshold=args.velocity_burst_threshold,
        idle_timeout_ms=args.idle_timeout_ms,
        min_detection_confidence=args.min_detection_confidence,
        min_presence_confidence=args.min_presence_confidence,
        min_tracking_confidence=args.min_tracking_confidence,
        max_seconds=args.max_seconds,
        speech_enabled=not args.no_speech,
        vosk_model_path=args.vosk_model_path,
        mic_device_index=args.mic_device_index,
        animal_cooldown=args.animal_cooldown,
        animal_display_duration=args.animal_display_duration,
        assets_dir=args.assets_dir,
        highlight_style=args.highlight_style,
        pitch_enabled=not args.no_pitch,
        pitch_confidence_thresh=args.pitch_confidence_thresh,
        pitch_weight=args.pitch_weight,
        atmosphere_enabled=not args.no_atmosphere,
    )


def ensure_model_file(config: AppConfig) -> Path:
    config.model_path.parent.mkdir(parents=True, exist_ok=True)
    if config.model_path.exists():
        return config.model_path
    urllib.request.urlretrieve(config.model_url, config.model_path)
    return config.model_path
