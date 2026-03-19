from __future__ import annotations

import argparse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "hand_landmarker.task"


@dataclass(slots=True)
class AppConfig:
    model_path: Path = DEFAULT_MODEL_PATH
    model_url: str = MODEL_URL
    camera_index: int = 0
    frame_width: int = 1280
    frame_height: int = 720
    camera_fps: int = 60
    osc_host: str = "127.0.0.1"
    osc_port: int = 7000
    max_hands: int = 2
    preview: bool = True
    mirror: bool = True
    send_landmarks: bool = False
    virtual_cam: bool = False
    position_smoothing: float = 0.28
    pinch_smoothing: float = 0.24
    velocity_smoothing: float = 0.2
    pinch_close_threshold: float = 0.055
    pinch_open_threshold: float = 0.075
    velocity_burst_threshold: float = 0.45
    idle_timeout_ms: int = 180
    min_detection_confidence: float = 0.55
    min_presence_confidence: float = 0.45
    min_tracking_confidence: float = 0.45
    max_seconds: float | None = None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MediaPipe hand tracker that drives a TouchDesigner galaxy effect over OSC."
    )
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--frame-width", type=int, default=1280)
    parser.add_argument("--frame-height", type=int, default=720)
    parser.add_argument("--camera-fps", type=int, default=60)
    parser.add_argument("--osc-host", default="127.0.0.1")
    parser.add_argument("--osc-port", type=int, default=7000)
    parser.add_argument("--max-hands", type=int, default=2)
    parser.add_argument("--send-landmarks", action="store_true")
    parser.add_argument("--virtual-cam", action="store_true")
    parser.add_argument("--no-preview", action="store_true")
    parser.add_argument("--no-mirror", action="store_true")
    parser.add_argument("--position-smoothing", type=float, default=0.28)
    parser.add_argument("--pinch-smoothing", type=float, default=0.24)
    parser.add_argument("--velocity-smoothing", type=float, default=0.20)
    parser.add_argument("--pinch-close-threshold", type=float, default=0.055)
    parser.add_argument("--pinch-open-threshold", type=float, default=0.075)
    parser.add_argument("--velocity-burst-threshold", type=float, default=0.45)
    parser.add_argument("--idle-timeout-ms", type=int, default=180)
    parser.add_argument("--min-detection-confidence", type=float, default=0.55)
    parser.add_argument("--min-presence-confidence", type=float, default=0.45)
    parser.add_argument("--min-tracking-confidence", type=float, default=0.45)
    parser.add_argument("--max-seconds", type=float, default=None)
    return parser


def config_from_args(argv: list[str] | None = None) -> AppConfig:
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
    )


def ensure_model_file(config: AppConfig) -> Path:
    config.model_path.parent.mkdir(parents=True, exist_ok=True)
    if config.model_path.exists():
        return config.model_path

    urllib.request.urlretrieve(config.model_url, config.model_path)
    return config.model_path
