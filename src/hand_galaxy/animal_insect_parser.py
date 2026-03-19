"""
Compatibility wrapper for the keyword parser.

The app started as an animal/insect trigger system, so other modules still
import ``AnimalInsectParser`` and ``ALL_KEYWORDS`` from here.  The underlying
implementation now supports custom JSON keyword categories and per-category
themes via ``keyword_library.py``.
"""
from __future__ import annotations

from .keyword_library import (
    ALL_KEYWORDS,
    ANIMALS,
    INSECTS,
    DetectionEvent,
    KeywordParser,
    category_of,
)


class AnimalInsectParser(KeywordParser):
    pass

