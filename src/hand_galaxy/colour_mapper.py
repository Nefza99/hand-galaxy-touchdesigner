"""
colour_mapper.py
----------------
Applies a colour-aware highlight (glow, rim light, or tinted border) to an
animal/insect image based on the current active effect colour.

The highlight is layered UNDER the original image so the subject stays clear.
All images are processed as BGRA NumPy arrays (OpenCV format).

Supported highlight styles:
  - "glow"   : soft dilated halo (default)
  - "rim"    : thin sharp border with inner falloff
  - "aura"   : large diffuse bloom
  - "tint"   : subtle colour cast over the whole image

The style can be set globally or per call.
"""
from __future__ import annotations

import cv2
import numpy as np
from typing import Literal

HighlightStyle = Literal["glow", "rim", "aura", "tint"]


def _ensure_bgra(img: np.ndarray) -> np.ndarray:
    """Return a 4-channel BGRA copy."""
    if img is None:
        return np.zeros((256, 256, 4), dtype=np.uint8)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        img[:, :, 3] = 255
    return img.copy()


def _alpha_channel(img: np.ndarray) -> np.ndarray:
    """Extract or infer alpha channel."""
    if img.shape[2] == 4:
        return img[:, :, 3]
    h, w = img.shape[:2]
    return np.full((h, w), 255, dtype=np.uint8)


def apply_highlight(
    image: np.ndarray,
    bgr_colour: tuple[int, int, int],
    style: HighlightStyle = "glow",
    intensity: float = 1.0,
) -> np.ndarray:
    """
    Composite a colour highlight around / over ``image``.

    Args:
        image:       Input image (BGR or BGRA NumPy array).
        bgr_colour:  Highlight colour in OpenCV BGR order.
        style:       One of "glow", "rim", "aura", "tint".
        intensity:   0.0–1.0 strength multiplier.

    Returns:
        BGRA NumPy array with highlight applied.
    """
    intensity = max(0.0, min(1.0, intensity))
    if intensity < 0.01:
        return _ensure_bgra(image)

    img = _ensure_bgra(image)
    h, w = img.shape[:2]
    alpha = _alpha_channel(img)
    b, g, r = bgr_colour

    if style == "glow":
        result = _apply_glow(img, alpha, b, g, r, intensity, radius_factor=0.12)
    elif style == "rim":
        result = _apply_rim(img, alpha, b, g, r, intensity)
    elif style == "aura":
        result = _apply_glow(img, alpha, b, g, r, intensity, radius_factor=0.25)
    elif style == "tint":
        result = _apply_tint(img, b, g, r, intensity)
    else:
        result = _apply_glow(img, alpha, b, g, r, intensity, radius_factor=0.12)

    return result


def _apply_glow(
    img: np.ndarray,
    alpha: np.ndarray,
    b: int, g: int, r: int,
    intensity: float,
    radius_factor: float = 0.12,
) -> np.ndarray:
    h, w = img.shape[:2]
    radius = max(5, int(min(h, w) * radius_factor))
    # Make radius odd
    if radius % 2 == 0:
        radius += 1

    # Dilate the subject mask to create a halo region
    kernel_size = radius * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    halo_mask = cv2.dilate(alpha, kernel)

    # Subtract original alpha to get only the ring
    ring_mask = cv2.subtract(halo_mask, alpha)

    # Blur for softness
    blur_k = max(3, radius | 1)
    ring_mask = cv2.GaussianBlur(ring_mask.astype(np.float32), (blur_k * 2 + 1, blur_k * 2 + 1), 0)

    # Scale by intensity
    ring_mask = np.clip(ring_mask * intensity, 0, 255).astype(np.uint8)

    # Build glow layer
    glow = np.zeros((h, w, 4), dtype=np.uint8)
    glow[:, :, 0] = b
    glow[:, :, 1] = g
    glow[:, :, 2] = r
    glow[:, :, 3] = ring_mask

    # Composite: glow under original
    return _composite_under(glow, img)


def _apply_rim(
    img: np.ndarray,
    alpha: np.ndarray,
    b: int, g: int, r: int,
    intensity: float,
) -> np.ndarray:
    h, w = img.shape[:2]
    rim_width = max(3, int(min(h, w) * 0.025))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (rim_width * 2 + 1, rim_width * 2 + 1))
    dilated = cv2.dilate(alpha, kernel)
    rim_mask = cv2.subtract(dilated, alpha)

    # Sharp + slight blur
    rim_mask = cv2.GaussianBlur(rim_mask, (5, 5), 0)
    rim_mask = np.clip(rim_mask.astype(np.float32) * intensity * 1.5, 0, 255).astype(np.uint8)

    rim = np.zeros((h, w, 4), dtype=np.uint8)
    rim[:, :, 0] = b
    rim[:, :, 1] = g
    rim[:, :, 2] = r
    rim[:, :, 3] = rim_mask

    return _composite_under(rim, img)


def _apply_tint(
    img: np.ndarray,
    b: int, g: int, r: int,
    intensity: float,
) -> np.ndarray:
    h, w = img.shape[:2]
    tint_layer = np.zeros((h, w, 4), dtype=np.uint8)
    tint_layer[:, :, 0] = b
    tint_layer[:, :, 1] = g
    tint_layer[:, :, 2] = r
    tint_strength = int(60 * intensity)
    if img.shape[2] == 4:
        tint_layer[:, :, 3] = (img[:, :, 3].astype(np.float32) * (tint_strength / 255.0)).astype(np.uint8)
    else:
        tint_layer[:, :, 3] = tint_strength

    return _composite_over(img, tint_layer)


def _composite_under(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    """Composite ``top`` over ``bottom``."""
    h, w = top.shape[:2]
    result = np.zeros((h, w, 4), dtype=np.float32)
    top_f = top.astype(np.float32) / 255.0
    bot_f = bottom.astype(np.float32) / 255.0

    top_a = top_f[:, :, 3:4]
    bot_a = bot_f[:, :, 3:4]

    out_a = top_a + bot_a * (1.0 - top_a)
    denom = np.where(out_a > 1e-6, out_a, 1.0)
    out_rgb = (top_f[:, :, :3] * top_a + bot_f[:, :, :3] * bot_a * (1.0 - top_a)) / denom

    result[:, :, :3] = out_rgb
    result[:, :, 3] = out_a[:, :, 0]
    return (np.clip(result, 0.0, 1.0) * 255).astype(np.uint8)


def _composite_over(base: np.ndarray, overlay: np.ndarray) -> np.ndarray:
    """Composite ``overlay`` over ``base``."""
    h, w = base.shape[:2]
    result = np.zeros((h, w, 4), dtype=np.float32)
    base_f = base.astype(np.float32) / 255.0
    over_f = overlay.astype(np.float32) / 255.0

    over_a = over_f[:, :, 3:4]
    base_a = base_f[:, :, 3:4]

    out_a = over_a + base_a * (1.0 - over_a)
    denom = np.where(out_a > 1e-6, out_a, 1.0)
    out_rgb = (over_f[:, :, :3] * over_a + base_f[:, :, :3] * base_a * (1.0 - over_a)) / denom

    result[:, :, :3] = out_rgb
    result[:, :, 3] = out_a[:, :, 0]
    return (np.clip(result, 0.0, 1.0) * 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Smooth colour interpolation for live colour transitions
# ---------------------------------------------------------------------------

class ColourTransition:
    """
    Smoothly interpolates the highlight colour between target values.
    Call ``update(target_bgr, dt)`` each frame.
    """

    def __init__(self, initial_bgr: tuple[int, int, int] = (255, 180, 0)):
        self._current = list(initial_bgr)

    def update(
        self,
        target_bgr: tuple[int, int, int],
        dt: float,
        speed: float = 4.0,
    ) -> tuple[int, int, int]:
        """
        Exponential ease toward ``target_bgr``.

        Args:
            target_bgr: desired colour.
            dt:         frame delta time in seconds.
            speed:      convergence speed (higher = faster).

        Returns:
            Current interpolated BGR colour.
        """
        alpha = 1.0 - math.exp(-speed * dt)
        for i in range(3):
            self._current[i] += (target_bgr[i] - self._current[i]) * alpha
        return (int(self._current[0]), int(self._current[1]), int(self._current[2]))


# math imported here because the method above needs it
import math  # noqa: E402
