"""
animal_insect_parser.py
-----------------------
Keyword detection for animals and insects from ASR word sequences.

Design:
  - Simple keyword set lookup (O(1) per word).
  - Per-word cooldown prevents the same animal re-triggering every frame.
  - Easy to extend: add words to ANIMALS or INSECTS sets.
  - Returns a ``DetectionEvent`` dataclass on a new trigger.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Keyword databases
# ---------------------------------------------------------------------------

ANIMALS: frozenset[str] = frozenset({
    # Common mammals
    "cat", "dog", "horse", "cow", "pig", "sheep", "goat", "rabbit",
    "fox", "wolf", "bear", "deer", "lion", "tiger", "leopard", "cheetah",
    "elephant", "giraffe", "zebra", "hippo", "rhino", "gorilla", "monkey",
    "orangutan", "chimp", "panda", "koala", "kangaroo", "whale", "dolphin",
    "seal", "otter", "beaver", "squirrel", "rat", "mouse", "hamster",
    # Birds
    "bird", "eagle", "hawk", "owl", "parrot", "penguin", "pelican",
    "flamingo", "ostrich", "peacock", "crow", "raven", "duck", "swan",
    "sparrow", "robin", "hummingbird",
    # Reptiles / amphibians
    "snake", "lizard", "gecko", "iguana", "crocodile", "alligator",
    "turtle", "tortoise", "frog", "toad", "salamander", "newt",
    # Fish / aquatic
    "fish", "shark", "salmon", "tuna", "goldfish", "clownfish",
    "octopus", "squid", "jellyfish", "crab", "lobster", "shrimp",
})

INSECTS: frozenset[str] = frozenset({
    "bee", "wasp", "hornet", "ant", "termite",
    "butterfly", "moth", "caterpillar",
    "beetle", "ladybug", "ladybird",
    "fly", "mosquito", "gnat",
    "dragonfly", "damselfly",
    "grasshopper", "cricket", "locust",
    "spider", "scorpion",                 # arachnids, close enough
    "mantis", "cockroach", "firefly",
    "tick", "flea", "louse",
    "centipede", "millipede",
})

ALL_KEYWORDS: frozenset[str] = ANIMALS | INSECTS


def category_of(word: str) -> str:
    """Returns 'animal', 'insect', or 'unknown'."""
    w = word.lower()
    if w in INSECTS:
        return "insect"
    if w in ANIMALS:
        return "animal"
    return "unknown"


# ---------------------------------------------------------------------------
# Detection event
# ---------------------------------------------------------------------------

@dataclass
class DetectionEvent:
    word: str               # exact matched keyword
    category: str           # "animal" | "insect"
    timestamp: float = field(default_factory=time.monotonic)

    @property
    def is_animal(self) -> bool:
        return self.category == "animal"

    @property
    def is_insect(self) -> bool:
        return self.category == "insect"


# ---------------------------------------------------------------------------
# Parser with cooldown logic
# ---------------------------------------------------------------------------

_WORD_SPLIT_RE = re.compile(r"[^a-z]+")


class AnimalInsectParser:
    """
    Parses ASR text for animal/insect keywords with per-word cooldowns.

    Args:
        cooldown: seconds before the same word can trigger again.
    """

    def __init__(self, cooldown: float = 4.0):
        self.cooldown = cooldown
        self._last_trigger: dict[str, float] = {}

    def parse(self, text: str) -> Optional[DetectionEvent]:
        """
        Scan ``text`` for the first keyword that is not on cooldown.

        Returns a :class:`DetectionEvent` or ``None``.
        Only the *first* trigger is returned per call; call again each frame.
        """
        words = _WORD_SPLIT_RE.split(text.lower())
        now = time.monotonic()

        for word in words:
            if word not in ALL_KEYWORDS:
                continue
            last = self._last_trigger.get(word, 0.0)
            if (now - last) < self.cooldown:
                continue  # still in cooldown
            self._last_trigger[word] = now
            return DetectionEvent(word=word, category=category_of(word))

        return None

    def parse_all(self, text: str) -> list[DetectionEvent]:
        """
        Like ``parse`` but returns ALL matching keywords not in cooldown,
        in the order they appear in the text.
        """
        words = _WORD_SPLIT_RE.split(text.lower())
        now = time.monotonic()
        results: list[DetectionEvent] = []

        for word in words:
            if word not in ALL_KEYWORDS:
                continue
            last = self._last_trigger.get(word, 0.0)
            if (now - last) < self.cooldown:
                continue
            self._last_trigger[word] = now
            results.append(DetectionEvent(word=word, category=category_of(word)))

        return results

    def reset_cooldown(self, word: str) -> None:
        self._last_trigger.pop(word, None)

    def remaining_cooldown(self, word: str) -> float:
        last = self._last_trigger.get(word, 0.0)
        remaining = self.cooldown - (time.monotonic() - last)
        return max(0.0, remaining)
