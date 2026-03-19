from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field


_CLEAN_RE = re.compile(r"[^a-z ]+")
_PHONEME_MAP: tuple[tuple[str, str, str], ...] = (
    ("tion", "SHN", "fricative"),
    ("ch", "CH", "affricate"),
    ("sh", "SH", "fricative"),
    ("th", "TH", "fricative"),
    ("ph", "F", "fricative"),
    ("ng", "NG", "nasal"),
    ("oo", "OO", "vowel"),
    ("ee", "EE", "vowel"),
    ("ai", "AI", "vowel"),
    ("ay", "AY", "vowel"),
    ("ow", "OW", "vowel"),
    ("ou", "OU", "vowel"),
)
_LETTER_GROUPS: dict[str, tuple[str, str]] = {
    "a": ("A", "vowel"),
    "e": ("E", "vowel"),
    "i": ("I", "vowel"),
    "o": ("O", "vowel"),
    "u": ("U", "vowel"),
    "p": ("P", "plosive"),
    "b": ("B", "plosive"),
    "t": ("T", "plosive"),
    "d": ("D", "plosive"),
    "k": ("K", "plosive"),
    "c": ("K", "plosive"),
    "g": ("G", "plosive"),
    "f": ("F", "fricative"),
    "v": ("V", "fricative"),
    "s": ("S", "fricative"),
    "z": ("Z", "fricative"),
    "x": ("KS", "fricative"),
    "m": ("M", "nasal"),
    "n": ("N", "nasal"),
    "l": ("L", "liquid"),
    "r": ("R", "liquid"),
    "w": ("W", "glide"),
    "y": ("Y", "glide"),
    "h": ("H", "breath"),
    "j": ("J", "affricate"),
    "q": ("K", "plosive"),
}
_FAMILY_ORDER = ("vowel", "plosive", "fricative", "nasal", "liquid", "glide", "breath", "affricate")


@dataclass(frozen=True)
class PhonemeToken:
    symbol: str
    family: str
    strength: float
    timestamp: float


@dataclass
class PhonemeState:
    raw_text: str = ""
    tokens: tuple[PhonemeToken, ...] = ()
    family_levels: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class BannerItem:
    text: str
    timestamp: float


class SentenceBanner:
    def __init__(self, max_items: int = 8, lifetime: float = 12.0):
        self.max_items = max_items
        self.lifetime = lifetime
        self._items: deque[BannerItem] = deque(maxlen=max_items)

    def push(self, text: str) -> None:
        clean = text.strip()
        if clean:
            self._items.append(BannerItem(text=clean, timestamp=time.monotonic()))

    def items(self) -> list[BannerItem]:
        now = time.monotonic()
        live = [item for item in self._items if (now - item.timestamp) <= self.lifetime]
        self._items = deque(live, maxlen=self.max_items)
        return list(self._items)


class PhonemeTracker:
    def __init__(self, max_tokens: int = 10):
        self.max_tokens = max_tokens
        self._tokens: deque[PhonemeToken] = deque(maxlen=max_tokens)
        self._latest = PhonemeState(family_levels={family: 0.0 for family in _FAMILY_ORDER})

    @property
    def latest(self) -> PhonemeState:
        return self._latest

    def update(self, text: str) -> PhonemeState:
        clean = _CLEAN_RE.sub("", text.lower()).strip()
        if not clean:
            self._latest = PhonemeState(raw_text="", tokens=(), family_levels={family: 0.0 for family in _FAMILY_ORDER})
            return self._latest
        symbols = self._extract_tokens(clean)
        now = time.monotonic()
        for idx, (symbol, family) in enumerate(symbols[-4:]):
            strength = 0.55 + 0.45 * ((idx + 1) / max(1, min(4, len(symbols))))
            self._tokens.append(PhonemeToken(symbol=symbol, family=family, strength=strength, timestamp=now))
        family_levels = {family: 0.0 for family in _FAMILY_ORDER}
        decay_cutoff = now - 2.0
        live_tokens = [token for token in self._tokens if token.timestamp >= decay_cutoff]
        self._tokens = deque(live_tokens, maxlen=self.max_tokens)
        for token in self._tokens:
            age = now - token.timestamp
            intensity = token.strength * max(0.0, 1.0 - age / 2.0)
            family_levels[token.family] = max(family_levels.get(token.family, 0.0), intensity)
        self._latest = PhonemeState(
            raw_text=clean,
            tokens=tuple(self._tokens),
            family_levels=family_levels,
        )
        return self._latest

    def _extract_tokens(self, text: str) -> list[tuple[str, str]]:
        words = text.split()
        target = " ".join(words[-2:])
        target = target.replace(" ", "")
        tokens: list[tuple[str, str]] = []
        i = 0
        while i < len(target):
            matched = False
            for fragment, symbol, family in _PHONEME_MAP:
                if target.startswith(fragment, i):
                    tokens.append((symbol, family))
                    i += len(fragment)
                    matched = True
                    break
            if matched:
                continue
            letter = target[i]
            symbol, family = _LETTER_GROUPS.get(letter, (letter.upper(), "fricative"))
            tokens.append((symbol, family))
            i += 1
        return tokens[-self.max_tokens:]
