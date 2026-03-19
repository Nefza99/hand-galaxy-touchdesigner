"""
Media asset loader with support for static images, animated GIFs, and
sprite-sheet manifests.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)

_STATIC_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
_ANIMATED_EXTENSIONS = (".gif",)
_DEFAULT_DISPLAY_SIZE = (320, 320)


@dataclass(frozen=True)
class MediaClip:
    name: str
    frames: tuple[np.ndarray, ...]
    durations: tuple[float, ...]
    loop: bool = True
    kind: str = "static"

    def frame_at(self, now: float, started_at: float | None = None) -> np.ndarray:
        if len(self.frames) == 1:
            return self.frames[0]
        start = started_at if started_at is not None else now
        elapsed = max(0.0, now - start)
        total = sum(self.durations) or 1.0
        if self.loop:
            elapsed = elapsed % total
        else:
            elapsed = min(elapsed, total - 1e-6)
        cursor = 0.0
        for frame, duration in zip(self.frames, self.durations):
            cursor += duration
            if elapsed <= cursor:
                return frame
        return self.frames[-1]

    @property
    def still(self) -> np.ndarray:
        return self.frames[0]


class AssetLoader:
    def __init__(self, assets_dir: str | Path, display_size: tuple[int, int] = _DEFAULT_DISPLAY_SIZE):
        self.assets_dir = Path(assets_dir)
        self.display_size = display_size
        self._cache: dict[tuple[str, str], MediaClip] = {}
        self._placeholder: Optional[MediaClip] = None
        self._animal_dir = self.assets_dir / "animals"

    def get_animal(self, name: str, category: str | None = None) -> np.ndarray:
        return self.get_clip(name, category=category).still

    def get_clip(self, name: str, category: str | None = None) -> MediaClip:
        token = name.lower().strip()
        key = (category or "", token)
        if key in self._cache:
            return self._cache[key]

        clip = self._search(token, category=category)
        if clip is None:
            log.warning("Asset not found for '%s', using placeholder.", token)
            clip = self._make_placeholder(token)
        self._cache[key] = clip
        return clip

    def preload(self, names: list[str]) -> None:
        for name in names:
            self.get_clip(name)

    def resize_display(self, img: np.ndarray, size: Optional[tuple[int, int]] = None) -> np.ndarray:
        width, height = size or self.display_size
        return cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)

    def _candidate_dirs(self, category: str | None) -> list[Path]:
        dirs: list[Path] = []
        if category:
            dirs.append(self.assets_dir / category)
            dirs.append(self.assets_dir / f"{category}s")
        dirs.append(self._animal_dir)
        dirs.append(self.assets_dir)
        return [path for path in dirs if path.exists()]

    def _search(self, name: str, category: str | None = None) -> Optional[MediaClip]:
        candidates = [
            name,
            name.replace(" ", "_"),
            name.replace("_", " "),
            name.replace("-", "_"),
        ]
        for directory in self._candidate_dirs(category):
            for candidate in candidates:
                manifest = directory / f"{candidate}.json"
                if manifest.exists():
                    clip = self._load_manifest(manifest)
                    if clip is not None:
                        return clip
                for ext in (*_ANIMATED_EXTENSIONS, *_STATIC_EXTENSIONS):
                    path = directory / f"{candidate}{ext}"
                    if path.exists():
                        clip = self._load_path(path)
                        if clip is not None:
                            return clip
        return None

    def _load_path(self, path: Path) -> Optional[MediaClip]:
        suffix = path.suffix.lower()
        try:
            if suffix in _ANIMATED_EXTENSIONS:
                return self._load_gif(path)
            if suffix in _STATIC_EXTENSIONS:
                image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
                if image is None:
                    return None
                return MediaClip(
                    name=path.stem.lower(),
                    frames=(self._normalise_image(image),),
                    durations=(1.0,),
                    loop=True,
                    kind="static",
                )
        except Exception as exc:
            log.error("Failed to load '%s': %s", path, exc)
        return None

    def _load_gif(self, path: Path) -> Optional[MediaClip]:
        try:
            from PIL import Image, ImageSequence
        except ImportError as exc:
            log.warning("Pillow missing for GIF support: %s", exc)
            return None
        frames: list[np.ndarray] = []
        durations: list[float] = []
        with Image.open(path) as img:
            for frame in ImageSequence.Iterator(img):
                rgba = frame.convert("RGBA")
                array = np.array(rgba)
                bgra = cv2.cvtColor(array, cv2.COLOR_RGBA2BGRA)
                frames.append(self._normalise_image(bgra))
                duration_ms = frame.info.get("duration", img.info.get("duration", 90)) or 90
                durations.append(max(0.04, float(duration_ms) / 1000.0))
        if not frames:
            return None
        return MediaClip(
            name=path.stem.lower(),
            frames=tuple(frames),
            durations=tuple(durations),
            loop=True,
            kind="gif",
        )

    def _load_manifest(self, manifest_path: Path) -> Optional[MediaClip]:
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.error("Failed to read manifest '%s': %s", manifest_path, exc)
            return None
        if str(raw.get("type", "")).lower() != "spritesheet":
            return None
        image_name = raw.get("image")
        if not image_name:
            return None
        image_path = manifest_path.parent / str(image_name)
        image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if image is None:
            return None
        image = self._normalise_channels(image)
        frame_width = int(raw.get("frame_width", 0))
        frame_height = int(raw.get("frame_height", 0))
        if frame_width <= 0 or frame_height <= 0:
            return None
        columns = int(raw.get("columns", max(1, image.shape[1] // frame_width)))
        rows = int(raw.get("rows", max(1, image.shape[0] // frame_height)))
        frame_count = int(raw.get("frame_count", columns * rows))
        fps = max(1.0, float(raw.get("fps", 12.0)))
        loop = bool(raw.get("loop", True))
        frames: list[np.ndarray] = []
        for idx in range(frame_count):
            col = idx % columns
            row = idx // columns
            x0 = col * frame_width
            y0 = row * frame_height
            x1 = x0 + frame_width
            y1 = y0 + frame_height
            if y1 > image.shape[0] or x1 > image.shape[1]:
                break
            frame = image[y0:y1, x0:x1]
            frames.append(self._normalise_image(frame))
        if not frames:
            return None
        duration = 1.0 / fps
        return MediaClip(
            name=manifest_path.stem.lower(),
            frames=tuple(frames),
            durations=tuple(duration for _ in frames),
            loop=loop,
            kind="spritesheet",
        )

    def _normalise_channels(self, image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
            image[:, :, 3] = 255
        return image

    def _normalise_image(self, image: np.ndarray) -> np.ndarray:
        image = self._normalise_channels(image)
        width, height = self.display_size
        return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)

    def _make_placeholder(self, label: str) -> MediaClip:
        width, height = self.display_size
        image = np.zeros((height, width, 4), dtype=np.uint8)
        cv2.rectangle(image, (4, 4), (width - 4, height - 4), (40, 40, 40, 220), -1)
        cv2.rectangle(image, (4, 4), (width - 4, height - 4), (100, 100, 100, 255), 2)
        cx, cy = width // 2, height // 2 - 20
        cv2.circle(image, (cx, cy), min(width, height) // 4, (80, 80, 80, 255), -1)
        cv2.putText(
            image,
            "?",
            (cx - 18, cy + 22),
            cv2.FONT_HERSHEY_DUPLEX,
            2.0,
            (180, 180, 180, 255),
            3,
            cv2.LINE_AA,
        )
        text = label.upper()
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = min(0.8, 6.0 / max(len(text), 1))
        (tw, _), _ = cv2.getTextSize(text, font, font_scale, 1)
        tx = max(4, (width - tw) // 2)
        ty = height - 18
        cv2.putText(image, text, (tx, ty), font, font_scale, (200, 200, 200, 255), 1, cv2.LINE_AA)
        if self._placeholder is None:
            self._placeholder = MediaClip(
                name="placeholder",
                frames=(image,),
                durations=(1.0,),
                loop=True,
                kind="placeholder",
            )
        return MediaClip(
            name=label,
            frames=(image,),
            durations=(1.0,),
            loop=True,
            kind="placeholder",
        )

    def clear_cache(self) -> None:
        self._cache.clear()
