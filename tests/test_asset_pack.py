from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hand_galaxy.animal_insect_parser import ALL_KEYWORDS


ASSET_DIR = ROOT / "assets" / "animals"
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


class AssetPackTests(unittest.TestCase):
    def test_every_keyword_has_an_asset_file(self) -> None:
        available = {
            file.stem.lower()
            for file in ASSET_DIR.iterdir()
            if file.is_file() and file.suffix.lower() in EXTENSIONS
        }
        missing = sorted(word for word in ALL_KEYWORDS if word not in available)
        self.assertEqual(missing, [], f"Missing assets for: {', '.join(missing)}")


if __name__ == "__main__":
    unittest.main()
