from __future__ import annotations

import argparse
import hashlib
import math
import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hand_galaxy.animal_insect_parser import ALL_KEYWORDS, ANIMALS, INSECTS


CANVAS = 640
CENTER = CANVAS // 2
IMAGE_EXT = ".png"


MAMMALS = {
    "cat", "dog", "horse", "cow", "pig", "sheep", "goat", "rabbit", "fox",
    "wolf", "bear", "deer", "lion", "tiger", "leopard", "cheetah", "elephant",
    "giraffe", "zebra", "hippo", "rhino", "gorilla", "monkey", "orangutan",
    "chimp", "panda", "koala", "kangaroo", "whale", "dolphin", "seal", "otter",
    "beaver", "squirrel", "rat", "mouse", "hamster",
}

BIRDS = {
    "bird", "eagle", "hawk", "owl", "parrot", "penguin", "pelican", "flamingo",
    "ostrich", "peacock", "crow", "raven", "duck", "swan", "sparrow", "robin",
    "hummingbird",
}

REPTILES = {
    "snake", "lizard", "gecko", "iguana", "crocodile", "alligator", "turtle",
    "tortoise",
}

AMPHIBIANS = {"frog", "toad", "salamander", "newt"}
FISH = {"fish", "shark", "salmon", "tuna", "goldfish", "clownfish"}
CEPHALOPODS = {"octopus", "squid", "jellyfish"}
CRUSTACEANS = {"crab", "lobster", "shrimp"}
ARACHNIDS = {"spider", "scorpion", "tick"}
MYRIAPODS = {"centipede", "millipede"}


PROFILE_STYLES = {
    "mammal": ((42, 28, 86), (255, 171, 106), (255, 233, 191)),
    "bird": ((20, 52, 94), (109, 211, 255), (208, 249, 255)),
    "reptile": ((22, 70, 54), (112, 222, 152), (225, 255, 219)),
    "amphibian": ((31, 88, 67), (115, 247, 177), (215, 255, 240)),
    "fish": ((16, 58, 108), (86, 176, 255), (217, 241, 255)),
    "cephalopod": ((74, 35, 94), (203, 130, 255), (245, 224, 255)),
    "crustacean": ((99, 42, 31), (255, 148, 107), (255, 230, 207)),
    "insect": ((84, 58, 16), (255, 213, 92), (255, 247, 206)),
    "arachnid": ((66, 28, 32), (255, 127, 140), (255, 218, 222)),
    "myriapod": ((70, 63, 21), (216, 222, 95), (247, 255, 216)),
}


def _clamp_channel(v: int) -> int:
    return max(0, min(255, int(v)))


def _tint(colour: tuple[int, int, int], delta: int) -> tuple[int, int, int]:
    return tuple(_clamp_channel(c + delta) for c in colour)


def profile_for(word: str) -> str:
    if word in MAMMALS:
        return "mammal"
    if word in BIRDS:
        return "bird"
    if word in REPTILES:
        return "reptile"
    if word in AMPHIBIANS:
        return "amphibian"
    if word in FISH:
        return "fish"
    if word in CEPHALOPODS:
        return "cephalopod"
    if word in CRUSTACEANS:
        return "crustacean"
    if word in ARACHNIDS:
        return "arachnid"
    if word in MYRIAPODS:
        return "myriapod"
    if word in INSECTS:
        return "insect"
    return "mammal"


def _rng_for(word: str) -> np.random.Generator:
    seed = int(hashlib.sha256(word.encode("utf-8")).hexdigest()[:16], 16)
    return np.random.default_rng(seed)


def _gradient_background(base: tuple[int, int, int], accent: tuple[int, int, int]) -> np.ndarray:
    yy = np.linspace(0.0, 1.0, CANVAS, dtype=np.float32)[:, None]
    xx = np.linspace(0.0, 1.0, CANVAS, dtype=np.float32)[None, :]
    diagonal = (xx + yy) * 0.5

    bg = np.zeros((CANVAS, CANVAS, 3), dtype=np.float32)
    for idx, (b, a) in enumerate(zip(base, accent)):
        bg[:, :, idx] = (b * (1.0 - diagonal) + a * diagonal)

    cx = xx - 0.5
    cy = yy - 0.46
    radial = np.sqrt((cx * cx) + (cy * cy))
    glow = np.clip(1.0 - radial * 1.8, 0.0, 1.0)
    for idx in range(3):
        bg[:, :, idx] += glow * 20.0

    return np.clip(bg, 0.0, 255.0).astype(np.uint8)


def _draw_stars(image: np.ndarray, rng: np.random.Generator, colour: tuple[int, int, int]) -> None:
    for _ in range(38):
        x = int(rng.integers(30, CANVAS - 30))
        y = int(rng.integers(24, CANVAS - 180))
        radius = int(rng.integers(1, 4))
        alpha = float(rng.uniform(0.18, 0.55))
        overlay = image.copy()
        cv2.circle(overlay, (x, y), radius, colour, -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, alpha, image, 1.0 - alpha, 0.0, image)


def _draw_panel(image: np.ndarray, accent: tuple[int, int, int], light: tuple[int, int, int]) -> None:
    cv2.rectangle(image, (22, 22), (CANVAS - 22, CANVAS - 22), _tint(accent, -35), 2, cv2.LINE_AA)
    cv2.rectangle(image, (42, 42), (CANVAS - 42, CANVAS - 42), _tint(light, -70), 1, cv2.LINE_AA)
    overlay = image.copy()
    cv2.circle(overlay, (CENTER, 270), 170, _tint(accent, -18), -1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.18, image, 0.82, 0.0, image)
    cv2.circle(image, (CENTER, 270), 175, _tint(light, -20), 4, cv2.LINE_AA)
    cv2.circle(image, (CENTER, 270), 138, _tint(light, -72), 2, cv2.LINE_AA)


def _draw_mammal(canvas: np.ndarray, line: tuple[int, int, int], fill: tuple[int, int, int]) -> None:
    cv2.ellipse(canvas, (CENTER, 290), (105, 74), 0, 0, 360, fill, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 92, 236), 50, fill, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 122, 184), 17, fill, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 72, 180), 15, fill, -1, cv2.LINE_AA)
    cv2.ellipse(canvas, (CENTER + 134, 248), (18, 10), 10, 0, 360, _tint(fill, -25), -1, cv2.LINE_AA)
    for x in (CENTER - 58, CENTER - 10, CENTER + 28, CENTER + 72):
        cv2.rectangle(canvas, (x, 340), (x + 18, 410), fill, -1)
    cv2.line(canvas, (CENTER - 104, 270), (CENTER - 146, 222), fill, 12, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 108, 225), 6, line, -1, cv2.LINE_AA)
    cv2.ellipse(canvas, (CENTER, 290), (105, 74), 0, 0, 360, line, 5, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 92, 236), 50, line, 5, cv2.LINE_AA)


def _draw_bird(canvas: np.ndarray, line: tuple[int, int, int], fill: tuple[int, int, int]) -> None:
    cv2.ellipse(canvas, (CENTER - 12, 288), (116, 78), -8, 0, 360, fill, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 84, 225), 40, fill, -1, cv2.LINE_AA)
    wing = np.array([[CENTER - 16, 264], [CENTER - 118, 236], [CENTER - 90, 328]], np.int32)
    cv2.fillConvexPoly(canvas, wing, _tint(fill, -22), cv2.LINE_AA)
    beak = np.array([[CENTER + 118, 230], [CENTER + 162, 246], [CENTER + 116, 260]], np.int32)
    cv2.fillConvexPoly(canvas, beak, _tint(fill, 18), cv2.LINE_AA)
    tail = np.array([[CENTER - 122, 284], [CENTER - 182, 250], [CENTER - 172, 314]], np.int32)
    cv2.fillConvexPoly(canvas, tail, _tint(fill, -28), cv2.LINE_AA)
    cv2.line(canvas, (CENTER + 8, 350), (CENTER + 2, 414), line, 5, cv2.LINE_AA)
    cv2.line(canvas, (CENTER + 40, 346), (CENTER + 34, 414), line, 5, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 96, 220), 5, line, -1, cv2.LINE_AA)
    cv2.ellipse(canvas, (CENTER - 12, 288), (116, 78), -8, 0, 360, line, 5, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 84, 225), 40, line, 5, cv2.LINE_AA)


def _draw_reptile(canvas: np.ndarray, line: tuple[int, int, int], fill: tuple[int, int, int]) -> None:
    body = np.array([
        [CENTER - 150, 292], [CENTER - 48, 234], [CENTER + 78, 230],
        [CENTER + 168, 258], [CENTER + 142, 314], [CENTER + 28, 334],
        [CENTER - 114, 332],
    ], np.int32)
    cv2.fillPoly(canvas, [body], fill, cv2.LINE_AA)
    head = np.array([[CENTER + 132, 248], [CENTER + 196, 270], [CENTER + 142, 300]], np.int32)
    cv2.fillConvexPoly(canvas, head, _tint(fill, 14), cv2.LINE_AA)
    tail = np.array([[CENTER - 150, 292], [CENTER - 236, 248], [CENTER - 214, 318]], np.int32)
    cv2.fillConvexPoly(canvas, tail, _tint(fill, -18), cv2.LINE_AA)
    for start_x, sign in ((CENTER - 54, -1), (CENTER + 26, 1)):
        cv2.line(canvas, (start_x, 324), (start_x - 34, 374), line, 5, cv2.LINE_AA)
        cv2.line(canvas, (start_x + 34, 322), (start_x + 64, 372), line, 5, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 162, 268), 5, line, -1, cv2.LINE_AA)
    cv2.polylines(canvas, [body], True, line, 5, cv2.LINE_AA)
    cv2.polylines(canvas, [head], True, line, 5, cv2.LINE_AA)


def _draw_amphibian(canvas: np.ndarray, line: tuple[int, int, int], fill: tuple[int, int, int]) -> None:
    cv2.ellipse(canvas, (CENTER, 294), (118, 82), 0, 0, 360, fill, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER - 54, 206), 28, fill, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 54, 206), 28, fill, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER - 54, 200), 10, _tint(fill, 38), -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 54, 200), 10, _tint(fill, 38), -1, cv2.LINE_AA)
    limbs = [
        ((CENTER - 84, 328), (CENTER - 168, 384)),
        ((CENTER + 84, 328), (CENTER + 168, 384)),
        ((CENTER - 70, 350), (CENTER - 136, 424)),
        ((CENTER + 70, 350), (CENTER + 136, 424)),
    ]
    for start, end in limbs:
        cv2.line(canvas, start, end, fill, 16, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER - 54, 200), 4, line, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 54, 200), 4, line, -1, cv2.LINE_AA)
    cv2.ellipse(canvas, (CENTER, 294), (118, 82), 0, 0, 360, line, 5, cv2.LINE_AA)


def _draw_fish(canvas: np.ndarray, line: tuple[int, int, int], fill: tuple[int, int, int]) -> None:
    cv2.ellipse(canvas, (CENTER - 16, 290), (132, 84), 0, 0, 360, fill, -1, cv2.LINE_AA)
    tail = np.array([[CENTER + 84, 288], [CENTER + 198, 216], [CENTER + 198, 362]], np.int32)
    fin_top = np.array([[CENTER - 8, 202], [CENTER + 54, 160], [CENTER + 78, 236]], np.int32)
    fin_bottom = np.array([[CENTER - 20, 354], [CENTER + 54, 414], [CENTER + 92, 332]], np.int32)
    cv2.fillConvexPoly(canvas, tail, _tint(fill, -18), cv2.LINE_AA)
    cv2.fillConvexPoly(canvas, fin_top, _tint(fill, 18), cv2.LINE_AA)
    cv2.fillConvexPoly(canvas, fin_bottom, _tint(fill, 10), cv2.LINE_AA)
    cv2.circle(canvas, (CENTER - 86, 272), 6, line, -1, cv2.LINE_AA)
    cv2.ellipse(canvas, (CENTER - 16, 290), (132, 84), 0, 0, 360, line, 5, cv2.LINE_AA)
    cv2.polylines(canvas, [tail], True, line, 5, cv2.LINE_AA)


def _draw_cephalopod(canvas: np.ndarray, line: tuple[int, int, int], fill: tuple[int, int, int]) -> None:
    cv2.ellipse(canvas, (CENTER, 246), (88, 116), 0, 0, 360, fill, -1, cv2.LINE_AA)
    for idx, x in enumerate(range(CENTER - 90, CENTER + 91, 26)):
        sway = int(math.sin(idx * 0.6) * 12)
        cv2.line(canvas, (x, 334), (x + sway, 438), fill, 16, cv2.LINE_AA)
        cv2.line(canvas, (x + sway, 438), (x + sway + 8, 500), fill, 12, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER - 28, 228), 10, _tint(fill, 36), -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 28, 228), 10, _tint(fill, 36), -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER - 28, 228), 4, line, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 28, 228), 4, line, -1, cv2.LINE_AA)
    cv2.ellipse(canvas, (CENTER, 246), (88, 116), 0, 0, 360, line, 5, cv2.LINE_AA)


def _draw_crustacean(canvas: np.ndarray, line: tuple[int, int, int], fill: tuple[int, int, int]) -> None:
    cv2.ellipse(canvas, (CENTER, 286), (118, 82), 0, 0, 360, fill, -1, cv2.LINE_AA)
    for offset in (-86, -44, 0, 44, 86):
        cv2.line(canvas, (CENTER + offset, 338), (CENTER + offset - 38, 404), line, 5, cv2.LINE_AA)
        cv2.line(canvas, (CENTER + offset, 338), (CENTER + offset + 38, 404), line, 5, cv2.LINE_AA)
    left_arm = np.array([[CENTER - 104, 258], [CENTER - 192, 210], [CENTER - 232, 258], [CENTER - 176, 286]], np.int32)
    right_arm = np.array([[CENTER + 104, 258], [CENTER + 192, 210], [CENTER + 232, 258], [CENTER + 176, 286]], np.int32)
    cv2.fillConvexPoly(canvas, left_arm, _tint(fill, 12), cv2.LINE_AA)
    cv2.fillConvexPoly(canvas, right_arm, _tint(fill, 12), cv2.LINE_AA)
    cv2.circle(canvas, (CENTER - 42, 242), 5, line, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 42, 242), 5, line, -1, cv2.LINE_AA)
    cv2.ellipse(canvas, (CENTER, 286), (118, 82), 0, 0, 360, line, 5, cv2.LINE_AA)


def _draw_insect(canvas: np.ndarray, line: tuple[int, int, int], fill: tuple[int, int, int]) -> None:
    cv2.ellipse(canvas, (CENTER, 246), (34, 58), 0, 0, 360, fill, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER, 180), 32, fill, -1, cv2.LINE_AA)
    wing_left = np.array([[CENTER - 18, 212], [CENTER - 146, 170], [CENTER - 120, 288], [CENTER - 10, 256]], np.int32)
    wing_right = np.array([[CENTER + 18, 212], [CENTER + 146, 170], [CENTER + 120, 288], [CENTER + 10, 256]], np.int32)
    cv2.fillConvexPoly(canvas, wing_left, _tint(fill, 34), cv2.LINE_AA)
    cv2.fillConvexPoly(canvas, wing_right, _tint(fill, 34), cv2.LINE_AA)
    for y in (286, 318, 350):
        cv2.line(canvas, (CENTER - 18, y), (CENTER - 112, y + 26), line, 5, cv2.LINE_AA)
        cv2.line(canvas, (CENTER + 18, y), (CENTER + 112, y + 26), line, 5, cv2.LINE_AA)
    cv2.line(canvas, (CENTER - 8, 148), (CENTER - 36, 104), line, 4, cv2.LINE_AA)
    cv2.line(canvas, (CENTER + 8, 148), (CENTER + 36, 104), line, 4, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER - 12, 176), 4, line, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 12, 176), 4, line, -1, cv2.LINE_AA)


def _draw_arachnid(canvas: np.ndarray, line: tuple[int, int, int], fill: tuple[int, int, int]) -> None:
    cv2.circle(canvas, (CENTER, 302), 88, fill, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER, 212), 48, fill, -1, cv2.LINE_AA)
    for idx, y in enumerate((216, 242, 280, 322)):
        spread = 110 + idx * 14
        height = 150 + idx * 18
        cv2.line(canvas, (CENTER - 22, y), (CENTER - spread, height), line, 5, cv2.LINE_AA)
        cv2.line(canvas, (CENTER + 22, y), (CENTER + spread, height), line, 5, cv2.LINE_AA)
        cv2.line(canvas, (CENTER - 22, y + 30), (CENTER - spread, 436 + idx * 12), line, 5, cv2.LINE_AA)
        cv2.line(canvas, (CENTER + 22, y + 30), (CENTER + spread, 436 + idx * 12), line, 5, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER - 18, 200), 4, line, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER + 18, 200), 4, line, -1, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER, 302), 88, line, 5, cv2.LINE_AA)
    cv2.circle(canvas, (CENTER, 212), 48, line, 5, cv2.LINE_AA)


def _draw_myriapod(canvas: np.ndarray, line: tuple[int, int, int], fill: tuple[int, int, int]) -> None:
    points = []
    for idx in range(9):
        x = CENTER - 150 + idx * 36
        y = 292 + int(math.sin(idx * 0.55) * 28)
        points.append((x, y))
        cv2.circle(canvas, (x, y), 28 if idx == 0 else 24, fill, -1, cv2.LINE_AA)
        if idx:
            cv2.line(canvas, points[idx - 1], (x, y), fill, 18, cv2.LINE_AA)
        cv2.line(canvas, (x - 10, y + 20), (x - 34, y + 64), line, 4, cv2.LINE_AA)
        cv2.line(canvas, (x + 10, y + 20), (x + 34, y + 64), line, 4, cv2.LINE_AA)
    cv2.circle(canvas, (points[0][0] - 6, points[0][1] - 6), 4, line, -1, cv2.LINE_AA)
    cv2.circle(canvas, (points[0][0] + 6, points[0][1] - 6), 4, line, -1, cv2.LINE_AA)


DRAWERS = {
    "mammal": _draw_mammal,
    "bird": _draw_bird,
    "reptile": _draw_reptile,
    "amphibian": _draw_amphibian,
    "fish": _draw_fish,
    "cephalopod": _draw_cephalopod,
    "crustacean": _draw_crustacean,
    "insect": _draw_insect,
    "arachnid": _draw_arachnid,
    "myriapod": _draw_myriapod,
}


def _fit_text(word: str) -> tuple[float, int]:
    font = cv2.FONT_HERSHEY_DUPLEX
    thickness = 2
    scale = 1.5
    while scale > 0.62:
        (width, _height), _ = cv2.getTextSize(word.upper(), font, scale, thickness)
        if width <= CANVAS - 120:
            return scale, thickness
        scale -= 0.08
    return 0.62, 2


def render_card(word: str, out_dir: Path) -> Path:
    profile = profile_for(word)
    base, accent, light = PROFILE_STYLES[profile]
    rng = _rng_for(word)
    image = _gradient_background(base, accent)
    _draw_stars(image, rng, _tint(light, -10))
    _draw_panel(image, accent, light)

    art_fill = _tint(accent, 14)
    art_line = _tint(light, -55)
    DRAWERS[profile](image, art_line, art_fill)

    ribbon_top = 470
    overlay = image.copy()
    cv2.rectangle(overlay, (60, ribbon_top), (CANVAS - 60, CANVAS - 72), _tint(base, -6), -1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.82, image, 0.18, 0.0, image)
    cv2.rectangle(image, (60, ribbon_top), (CANVAS - 60, CANVAS - 72), _tint(light, -95), 2, cv2.LINE_AA)

    category = "INSECT" if word in INSECTS else "ANIMAL"
    scale, thickness = _fit_text(word)
    font = cv2.FONT_HERSHEY_DUPLEX
    word_text = word.upper()
    (tw, th), _ = cv2.getTextSize(word_text, font, scale, thickness)
    tx = (CANVAS - tw) // 2
    ty = ribbon_top + 72
    cv2.putText(image, word_text, (tx + 2, ty + 2), font, scale, (14, 18, 28), thickness + 2, cv2.LINE_AA)
    cv2.putText(image, word_text, (tx, ty), font, scale, light, thickness, cv2.LINE_AA)

    sub_scale = 0.7
    subtitle = f"{category} CARD"
    (sw, _), _ = cv2.getTextSize(subtitle, cv2.FONT_HERSHEY_SIMPLEX, sub_scale, 2)
    sx = (CANVAS - sw) // 2
    sy = ribbon_top + 116
    cv2.putText(image, subtitle, (sx, sy), cv2.FONT_HERSHEY_SIMPLEX, sub_scale, _tint(light, -42), 2, cv2.LINE_AA)

    tag = profile.upper()
    cv2.putText(image, tag, (76, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.74, light, 2, cv2.LINE_AA)
    cv2.putText(image, "HAND GALAXY STARTER PACK", (76, CANVAS - 34), cv2.FONT_HERSHEY_SIMPLEX, 0.52, _tint(light, -52), 1, cv2.LINE_AA)

    out_path = out_dir / f"{word}{IMAGE_EXT}"
    cv2.imwrite(str(out_path), image)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate starter animal/insect PNG assets.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "assets" / "animals",
        help="Where to write PNG files.",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for word in sorted(ALL_KEYWORDS):
        written.append(render_card(word, args.output_dir))

    print(f"Generated {len(written)} asset cards in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
