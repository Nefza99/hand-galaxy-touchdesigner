from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path


ANIMALS: frozenset[str] = frozenset({
    "cat", "dog", "horse", "cow", "pig", "sheep", "goat", "rabbit",
    "fox", "wolf", "bear", "deer", "lion", "tiger", "leopard", "cheetah",
    "elephant", "giraffe", "zebra", "hippo", "rhino", "gorilla", "monkey",
    "orangutan", "chimp", "panda", "koala", "kangaroo", "whale", "dolphin",
    "seal", "otter", "beaver", "squirrel", "rat", "mouse", "hamster",
    "bird", "eagle", "hawk", "owl", "parrot", "penguin", "pelican",
    "flamingo", "ostrich", "peacock", "crow", "raven", "duck", "swan",
    "sparrow", "robin", "hummingbird",
    "snake", "lizard", "gecko", "iguana", "crocodile", "alligator",
    "turtle", "tortoise", "frog", "toad", "salamander", "newt",
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
    "spider", "scorpion",
    "mantis", "cockroach", "firefly",
    "tick", "flea", "louse",
    "centipede", "millipede",
})

ALL_KEYWORDS: frozenset[str] = ANIMALS | INSECTS

_WORD_SPLIT_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class KeywordTheme:
    category: str
    hue: float
    accent_hue: float
    saturation: float = 0.88
    value: float = 0.95
    midi_note: int = 60


@dataclass(frozen=True)
class KeywordEntry:
    word: str
    category: str
    asset_name: str
    aliases: tuple[str, ...]
    theme: KeywordTheme


@dataclass
class DetectionEvent:
    word: str
    category: str
    asset_name: str
    theme: KeywordTheme
    timestamp: float = field(default_factory=time.monotonic)

    @property
    def is_animal(self) -> bool:
        return self.category == "animal"

    @property
    def is_insect(self) -> bool:
        return self.category == "insect"


DEFAULT_THEMES: dict[str, KeywordTheme] = {
    "animal": KeywordTheme(
        category="animal",
        hue=0.08,
        accent_hue=0.14,
        saturation=0.86,
        value=0.98,
        midi_note=60,
    ),
    "insect": KeywordTheme(
        category="insect",
        hue=0.30,
        accent_hue=0.47,
        saturation=0.93,
        value=0.90,
        midi_note=67,
    ),
}


def _normalise_word(word: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "", word.lower().strip())


def _fallback_theme(category: str) -> KeywordTheme:
    seed = sum(ord(ch) for ch in category) % 360
    hue = (seed / 360.0) % 1.0
    accent = (hue + 0.18) % 1.0
    return KeywordTheme(category=category, hue=hue, accent_hue=accent, midi_note=72)


def _theme_from_dict(category: str, raw: object) -> KeywordTheme:
    if isinstance(raw, dict):
        base = DEFAULT_THEMES.get(category, _fallback_theme(category))
        return KeywordTheme(
            category=category,
            hue=float(raw.get("hue", base.hue)),
            accent_hue=float(raw.get("accent_hue", base.accent_hue)),
            saturation=float(raw.get("saturation", base.saturation)),
            value=float(raw.get("value", base.value)),
            midi_note=int(raw.get("midi_note", base.midi_note)),
        )
    return DEFAULT_THEMES.get(category, _fallback_theme(category))


class KeywordLibrary:
    def __init__(self, keywords_dir: str | Path | None = None):
        self.keywords_dir = Path(keywords_dir) if keywords_dir else None
        self._entries: dict[str, KeywordEntry] = {}
        self._phrase_entries: dict[tuple[str, ...], KeywordEntry] = {}
        self._load_defaults()
        self._load_custom_files()

    def _load_defaults(self) -> None:
        self._register_category(
            category="animal",
            words=sorted(ANIMALS),
            theme=DEFAULT_THEMES["animal"],
        )
        self._register_category(
            category="insect",
            words=sorted(INSECTS),
            theme=DEFAULT_THEMES["insect"],
        )

    def _load_custom_files(self) -> None:
        if not self.keywords_dir or not self.keywords_dir.exists():
            return
        for path in sorted(self.keywords_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for category in self._iter_categories(raw):
                self._register_custom_category(category)

    def _iter_categories(self, raw: object) -> list[dict]:
        if isinstance(raw, dict) and isinstance(raw.get("categories"), list):
            return [item for item in raw["categories"] if isinstance(item, dict)]
        if isinstance(raw, dict) and raw.get("name"):
            return [raw]
        return []

    def _register_custom_category(self, raw_category: dict) -> None:
        category = _normalise_word(str(raw_category.get("name", "")))
        if not category:
            return
        theme = _theme_from_dict(category, raw_category.get("theme"))
        entries = raw_category.get("entries")
        keywords = raw_category.get("keywords")
        if isinstance(entries, list):
            for item in entries:
                self._register_entry(raw=item, category=category, theme=theme)
            return
        if isinstance(keywords, list):
            for item in keywords:
                self._register_entry(raw=item, category=category, theme=theme)

    def _register_category(self, category: str, words: list[str], theme: KeywordTheme) -> None:
        for word in words:
            token = _normalise_word(word)
            if not token:
                continue
            entry = KeywordEntry(
                word=token,
                category=category,
                asset_name=token,
                aliases=(),
                theme=theme,
            )
            self._entries[token] = entry
            self._phrase_entries[(token,)] = entry

    def _register_entry(self, raw: object, category: str, theme: KeywordTheme) -> None:
        if isinstance(raw, str):
            raw_word = str(raw)
            word = _normalise_word(raw_word)
            aliases: tuple[str, ...] = ()
            asset_name = word
        elif isinstance(raw, dict):
            raw_word = str(raw.get("word", ""))
            word = _normalise_word(raw_word)
            asset_name = _normalise_word(str(raw.get("asset", word)))
            alias_list = raw.get("aliases", [])
            aliases = tuple(str(item) for item in alias_list if str(item).strip())
            if raw.get("theme"):
                theme = _theme_from_dict(category, raw.get("theme"))
        else:
            return
        if not word:
            return
        entry = KeywordEntry(
            word=word,
            category=category,
            asset_name=asset_name or word,
            aliases=aliases,
            theme=theme,
        )
        self._entries[word] = entry
        self._phrase_entries[self._phrase_key(raw_word)] = entry
        for alias in aliases:
            token = _normalise_word(alias)
            if token:
                self._entries[token] = entry
            self._phrase_entries[self._phrase_key(alias)] = entry

    @property
    def keyword_list(self) -> list[str]:
        canonical = {entry.word for entry in self._entries.values()}
        return sorted(canonical)

    @property
    def all_keywords(self) -> frozenset[str]:
        return frozenset(self.keyword_list)

    def lookup(self, token: str) -> KeywordEntry | None:
        return self._entries.get(_normalise_word(token))

    def find_matches(self, text: str, max_phrase: int = 4) -> list[KeywordEntry]:
        words = [token for token in _WORD_SPLIT_RE.split(text.lower()) if token]
        matches: list[KeywordEntry] = []
        i = 0
        while i < len(words):
            matched = None
            span = 0
            max_width = min(max_phrase, len(words) - i)
            for width in range(max_width, 0, -1):
                phrase = tuple(_normalise_word(token) for token in words[i:i + width])
                phrase = tuple(token for token in phrase if token)
                entry = self._phrase_entries.get(phrase)
                if entry is not None:
                    matched = entry
                    span = width
                    break
            if matched is not None:
                matches.append(matched)
                i += max(1, span)
            else:
                i += 1
        return matches

    def _phrase_key(self, text: str) -> tuple[str, ...]:
        parts = [token for token in _WORD_SPLIT_RE.split(text.lower()) if token]
        return tuple(_normalise_word(token) for token in parts if _normalise_word(token))


class KeywordParser:
    def __init__(
        self,
        cooldown: float = 4.0,
        keywords_dir: str | Path | None = None,
    ):
        self.cooldown = cooldown
        self.library = KeywordLibrary(keywords_dir=keywords_dir)
        self._last_trigger: dict[str, float] = {}

    @property
    def keyword_list(self) -> list[str]:
        return self.library.keyword_list

    @property
    def all_keywords(self) -> frozenset[str]:
        return self.library.all_keywords

    def parse(self, text: str) -> DetectionEvent | None:
        results = self.parse_all(text)
        return results[0] if results else None

    def parse_all(self, text: str) -> list[DetectionEvent]:
        now = time.monotonic()
        matches: list[DetectionEvent] = []
        for entry in self.library.find_matches(text):
            last = self._last_trigger.get(entry.word, 0.0)
            if (now - last) < self.cooldown:
                continue
            self._last_trigger[entry.word] = now
            matches.append(
                DetectionEvent(
                    word=entry.word,
                    category=entry.category,
                    asset_name=entry.asset_name,
                    theme=entry.theme,
                    timestamp=now,
                )
            )
        return matches

    def reset_cooldown(self, word: str) -> None:
        token = _normalise_word(word)
        if token:
            self._last_trigger.pop(token, None)

    def remaining_cooldown(self, word: str) -> float:
        token = _normalise_word(word)
        last = self._last_trigger.get(token, 0.0)
        return max(0.0, self.cooldown - (time.monotonic() - last))


def category_of(word: str) -> str:
    token = _normalise_word(word)
    if token in INSECTS:
        return "insect"
    if token in ANIMALS:
        return "animal"
    return "unknown"
