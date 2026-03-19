"""
asset_loader.py
---------------
Loads and caches animal/insect images from the local assets folder.

Layout expected::

    assets/
      animals/
        cat.jpg   (or .png / .jpeg / .webp)
        dog.png
        ...
      placeholder.png   (auto-generated if missing)

All images are returned as BGRA NumPy arrays resized to a consistent display
size.  A fallback placeholder with the word label is generated for any
missing asset so the app never crashes on a missing file.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)

_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
_DEFAULT_DISPLAY_SIZE = (320, 320)  # (width, height) pixels


class AssetLoader:
    """
    Loads animal/insect images with LRU-style cache.

    Args:
        assets_dir: path to the assets root folder.
        display_size: (width, height) to which loaded images are resized.
    """

    def __init__(
        self,
        assets_dir: str | Path,
        display_size: tuple[int, int] = _DEFAULT_DISPLAY_SIZE,
    ):
        self.assets_dir = Path(assets_dir)
        self.display_size = display_size
        self._cache: dict[str, np.ndarray] = {}
        self._placeholder: Optional[np.ndarray] = None
        self._animal_dir = self.assets_dir / "animals"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_animal(self, name: str) -> np.ndarray:
        """
        Return a BGRA image for ``name``.

        Tries common filename variants (lowercase, titlecase, with/without
        spaces-as-underscores).  Falls back to a generated placeholder.
        """
        name = name.lower().strip()
        if name in self._cache:
            return self._cache[name]

        img = self._search(self._animal_dir, name)
        if img is None:
            log.warning("Asset not found for '%s', using placeholder.", name)
            img = self._make_placeholder(name)

        self._cache[name] = img
        return img

    def preload(self, names: list[str]) -> None:
        """Pre-load a list of animal names so the first display is instant."""
        for name in names:
            self.get_animal(name)

    def resize_display(self, img: np.ndarray, size: Optional[tuple[int, int]] = None) -> np.ndarray:
        """Resize a BGRA image to the display size (or a custom size)."""
        w, h = size or self.display_size
        return cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _search(self, directory: Path, name: str) -> Optional[np.ndarray]:
        if not directory.exists():
            return None

        candidates = [
            name,
            name.replace(" ", "_"),
            name.replace("_", " "),
            name.replace("-", "_"),
        ]

        for candidate in candidates:
            for ext in _EXTENSIONS:
                path = directory / f"{candidate}{ext}"
                if path.exists():
                    img = self._load_path(path)
                    if img is not None:
                        return img

        return None

    def _load_path(self, path: Path) -> Optional[np.ndarray]:
        try:
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img is None:
                return None

            # Normalise to BGRA
            if img.ndim == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            if img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
                img[:, :, 3] = 255

            # Resize to display size
            w, h = self.display_size
            img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
            return img
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to load '%s': %s", path, exc)
            return None

    def _make_placeholder(self, label: str) -> np.ndarray:
        w, h = self.display_size
        img = np.zeros((h, w, 4), dtype=np.uint8)

        # Background: dark rounded rectangle
        cv2.rectangle(img, (4, 4), (w - 4, h - 4), (40, 40, 40, 220), -1)
        cv2.rectangle(img, (4, 4), (w - 4, h - 4), (100, 100, 100, 255), 2)

        # Question mark icon
        cx, cy = w // 2, h // 2 - 20
        cv2.circle(img, (cx, cy), min(w, h) // 4, (80, 80, 80, 255), -1)
        cv2.putText(
            img, "?", (cx - 18, cy + 22),
            cv2.FONT_HERSHEY_DUPLEX, 2.0, (180, 180, 180, 255), 3, cv2.LINE_AA,
        )

        # Label at bottom
        text = label.upper()
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = min(0.8, 6.0 / max(len(text), 1))
        (tw, th), _ = cv2.getTextSize(text, font, font_scale, 1)
        tx = max(4, (w - tw) // 2)
        ty = h - 18
        cv2.putText(img, text, (tx, ty), font, font_scale, (200, 200, 200, 255), 1, cv2.LINE_AA)

        return img

    def clear_cache(self) -> None:
        self._cache.clear()
