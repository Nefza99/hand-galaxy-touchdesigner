"""
letter_parser.py
----------------
Detects spoken letters (A–Z) from Vosk-recognised word sequences.

Handles:
  - Direct letter names:    "a", "b", "c" …
  - NATO phonetic alphabet: "alpha", "bravo", "charlie" …
  - Common English homophones: "bee" → B, "see" → C, "dee" → D …
  - Double-word forms:      "double you" → W
  - Digit-like short words:  anything that is exactly one character a–z
"""
from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

# Maps spoken word/phrase → letter
_WORD_TO_LETTER: dict[str, str] = {
    # --- plain letters ---
    "a": "A", "b": "B", "c": "C", "d": "D", "e": "E",
    "f": "F", "g": "G", "h": "H", "i": "I", "j": "J",
    "k": "K", "l": "L", "m": "M", "n": "N", "o": "O",
    "p": "P", "q": "Q", "r": "R", "s": "S", "t": "T",
    "u": "U", "v": "V", "w": "W", "x": "X", "y": "Y",
    "z": "Z",
    # --- common phonetic reads ---
    "ay": "A",
    "bee": "B",
    "see": "C", "sea": "C",
    "dee": "D",
    "ee": "E",
    "ef": "F",
    "gee": "G", "ji": "G",
    "aitch": "H", "ache": "H",
    "eye": "I", "aye": "I",
    "jay": "J", "jaye": "J",
    "kay": "K",
    "el": "L", "elle": "L",
    "em": "M",
    "en": "N",
    "oh": "O", "owe": "O",
    "pee": "P",
    "queue": "Q", "cue": "Q", "kew": "Q",
    "ar": "R", "are": "R",
    "es": "S", "ess": "S",
    "tee": "T", "tea": "T",
    "you": "U", "yew": "U",
    "vee": "V",
    "ex": "X",
    "why": "Y", "wye": "Y",
    "zee": "Z", "zed": "Z",
    # --- NATO phonetic ---
    "alpha": "A", "alfa": "A",
    "bravo": "B",
    "charlie": "C",
    "delta": "D",
    "echo": "E",
    "foxtrot": "F",
    "golf": "G",
    "hotel": "H",
    "india": "I",
    "juliet": "J", "juliett": "J",
    "kilo": "K",
    "lima": "L",
    "mike": "M",
    "november": "N",
    "oscar": "O",
    "papa": "P",
    "quebec": "Q",
    "romeo": "R",
    "sierra": "S",
    "tango": "T",
    "uniform": "U",
    "victor": "V",
    "whiskey": "W", "whisky": "W",
    "x-ray": "X", "xray": "X",
    "yankee": "Y",
    "zulu": "Z",
}

# Two-word phrases that map to a single letter
_TWO_WORD_TO_LETTER: dict[str, str] = {
    "double you": "W",
    "double u": "W",
}

_VALID_SINGLE_CHARS = set("abcdefghijklmnopqrstuvwxyz")


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z ]", "", text.lower()).strip()


def parse_letters(text: str) -> list[str]:
    """
    Extract a list of uppercase letters (A–Z) from recognised speech text.

    Args:
        text: final or partial ASR result string.

    Returns:
        List of uppercase letters in the order they were spoken.

    Example::
        >>> parse_letters("alpha bravo see")
        ['A', 'B', 'C']
    """
    text = _normalise(text)
    if not text:
        return []

    words = text.split()
    result: list[str] = []
    i = 0
    while i < len(words):
        # Try two-word match first
        if i + 1 < len(words):
            two = words[i] + " " + words[i + 1]
            if two in _TWO_WORD_TO_LETTER:
                result.append(_TWO_WORD_TO_LETTER[two])
                i += 2
                continue

        word = words[i]
        if word in _WORD_TO_LETTER:
            result.append(_WORD_TO_LETTER[word])
        elif len(word) == 1 and word in _VALID_SINGLE_CHARS:
            result.append(word.upper())
        i += 1

    return result


# ---------------------------------------------------------------------------
# Rolling display state
# ---------------------------------------------------------------------------

@dataclass
class LetterMemory:
    """
    Rolling window of recently spoken letters with fade timing.
    """
    max_letters: int = 8
    display_duration: float = 3.5      # seconds each letter stays fully visible
    fade_duration: float = 1.0         # seconds to fade out

    _letters: deque = field(default_factory=deque)
    _timestamps: deque = field(default_factory=deque)

    def add(self, letter: str) -> None:
        if len(self._letters) >= self.max_letters:
            self._letters.popleft()
            self._timestamps.popleft()
        self._letters.append(letter.upper())
        self._timestamps.append(time.monotonic())

    def add_many(self, letters: list[str]) -> None:
        for letter in letters:
            self.add(letter)

    def visible(self) -> list[tuple[str, float]]:
        """
        Returns [(letter, alpha)] for all letters still within display window.
        alpha is 1.0 while fully visible, fading to 0.0 over fade_duration.
        Expired letters are pruned.
        """
        now = time.monotonic()
        result: list[tuple[str, float]] = []
        keep_letters: deque = deque()
        keep_times: deque = deque()

        for letter, ts in zip(self._letters, self._timestamps):
            age = now - ts
            total = self.display_duration + self.fade_duration
            if age > total:
                continue  # expired, drop
            keep_letters.append(letter)
            keep_times.append(ts)
            if age < self.display_duration:
                alpha = 1.0
            else:
                fade_progress = (age - self.display_duration) / self.fade_duration
                alpha = max(0.0, 1.0 - fade_progress)
            result.append((letter, alpha))

        self._letters = keep_letters
        self._timestamps = keep_times
        return result

    def latest(self) -> Optional[str]:
        return self._letters[-1] if self._letters else None

    def clear(self) -> None:
        self._letters.clear()
        self._timestamps.clear()
