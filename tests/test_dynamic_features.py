from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hand_galaxy.animal_insect_parser import AnimalInsectParser
from hand_galaxy.asset_loader import AssetLoader
from hand_galaxy.effect_colour_state import EffectColourState
from hand_galaxy.spawn_controller import SpawnController
from hand_galaxy.speech_analysis import PhonemeTracker, SentenceBanner


def _hand(label: str, **kwargs):
    base = {
        "label": label,
        "active": True,
        "x": 0.5,
        "y": 0.5,
        "thumb_x": 0.48,
        "thumb_y": 0.5,
        "index_x": 0.52,
        "index_y": 0.5,
        "radius": 0.25,
        "pinch_norm": 0.7,
        "velocity": 0.2,
        "dx": 0.02,
        "dy": -0.01,
        "spin": 0.4,
        "energy": 0.8,
        "angle": 0.1,
        "trail": (),
        "just_pinched": False,
        "pinch_active": True,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def _frame(left=None, right=None):
    left = left or _hand("Left", active=False, energy=0.0, pinch_active=False)
    right = right or _hand("Right", active=False, energy=0.0, pinch_active=False)
    active = int(bool(left.active)) + int(bool(right.active))
    return SimpleNamespace(
        timestamp_ms=1,
        frame_width=1280,
        frame_height=720,
        active_hands=active,
        left=left,
        right=right,
        primary=left,
        secondary=right,
    )


class DynamicFeatureTests(unittest.TestCase):
    def test_keyword_parser_loads_custom_phrase_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            keywords_dir = Path(tmpdir)
            (keywords_dir / "ocean.json").write_text(
                json.dumps(
                    {
                        "categories": [
                            {
                                "name": "ocean",
                                "theme": {"hue": 0.55, "accent_hue": 0.62, "midi_note": 74},
                                "entries": [
                                    {"word": "orca", "asset": "whale", "aliases": ["killer whale"]},
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            parser = AnimalInsectParser(cooldown=0.0, keywords_dir=keywords_dir)
            event = parser.parse("the killer whale is circling")
            self.assertIsNotNone(event)
            self.assertEqual(event.category, "ocean")
            self.assertEqual(event.asset_name, "whale")
            self.assertEqual(event.theme.midi_note, 74)

    def test_asset_loader_supports_gif_and_sprite_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            animal_dir = root / "animals"
            animal_dir.mkdir(parents=True)

            try:
                from PIL import Image
            except ImportError:  # pragma: no cover
                self.skipTest("Pillow not available")

            gif_a = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
            gif_b = Image.new("RGBA", (32, 32), (0, 255, 0, 255))
            gif_path = animal_dir / "bee.gif"
            gif_a.save(gif_path, save_all=True, append_images=[gif_b], duration=[60, 80], loop=0)

            sheet = np.zeros((32, 64, 4), dtype=np.uint8)
            sheet[:, :32] = (255, 0, 0, 255)
            sheet[:, 32:] = (0, 0, 255, 255)
            cv2.imwrite(str(animal_dir / "butterfly_sheet.png"), sheet)
            (animal_dir / "butterfly.json").write_text(
                json.dumps(
                    {
                        "type": "spritesheet",
                        "image": "butterfly_sheet.png",
                        "frame_width": 32,
                        "frame_height": 32,
                        "frame_count": 2,
                        "fps": 12,
                    }
                ),
                encoding="utf-8",
            )

            loader = AssetLoader(root, display_size=(64, 64))
            gif_clip = loader.get_clip("bee")
            sprite_clip = loader.get_clip("butterfly")

            self.assertEqual(gif_clip.kind, "gif")
            self.assertEqual(len(gif_clip.frames), 2)
            self.assertEqual(sprite_clip.kind, "spritesheet")
            self.assertEqual(len(sprite_clip.frames), 2)
            self.assertEqual(gif_clip.still.shape, (64, 64, 4))

    def test_spawn_controller_attaches_prompt_to_pinch(self) -> None:
        parser = AnimalInsectParser(cooldown=0.0)
        event = parser.parse("cat")
        self.assertIsNotNone(event)
        fake_clip = SimpleNamespace(still=np.zeros((64, 64, 4), dtype=np.uint8), frame_at=lambda now, started_at: np.zeros((64, 64, 4), dtype=np.uint8))
        controller = SpawnController(max_spawns=4, spawn_ttl=5.0, prompt_duration=5.0)
        controller.set_prompt(event, fake_clip)
        left = _hand("Left", x=0.50, y=0.50, just_pinched=True)
        frame = _frame(left=left, right=_hand("Right", active=False, energy=0.0, pinch_active=False))
        controller.update(frame, (0.35, 0.35, 0.30, 0.30))
        self.assertEqual(controller.spawn_count(), 1)
        self.assertEqual(controller.spawns[0].owner_label, "Left")

    def test_sentence_banner_and_phoneme_tracker_hold_recent_state(self) -> None:
        banner = SentenceBanner(max_items=4, lifetime=20.0)
        banner.push("glowing whale")
        banner.push("shimmering firefly")
        self.assertEqual(len(banner.items()), 2)

        tracker = PhonemeTracker(max_tokens=8)
        state = tracker.update("soft hush")
        self.assertGreater(len(state.tokens), 0)
        self.assertTrue(any(level > 0.0 for level in state.family_levels.values()))
        self.assertTrue(any(token.family == "fricative" for token in state.tokens))

    def test_effect_colour_state_generates_independent_zone_categories(self) -> None:
        parser = AnimalInsectParser(cooldown=0.0)
        left_theme = parser.parse("cat").theme
        right_theme = parser.parse("bee").theme
        state = EffectColourState(pitch_weight=0.0)
        colour = state.update(
            _frame(left=_hand("Left"), right=_hand("Right", x=0.7, y=0.4)),
            pitch_params=None,
            amplitude=SimpleNamespace(amplitude=0.4, pulse=0.2),
            hand_themes={"Left": left_theme, "Right": right_theme},
        )
        self.assertEqual(colour.left_zone.category, "animal")
        self.assertEqual(colour.right_zone.category, "insect")
        self.assertNotEqual(colour.left_zone.hue, colour.right_zone.hue)


if __name__ == "__main__":
    unittest.main()
