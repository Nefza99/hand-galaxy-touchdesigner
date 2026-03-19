from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from .keyword_library import DetectionEvent, KeywordTheme


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _rect_contains(rect: tuple[float, float, float, float], x: float, y: float, margin: float = 0.04) -> bool:
    rx, ry, rw, rh = rect
    return (rx - margin) <= x <= (rx + rw + margin) and (ry - margin) <= y <= (ry + rh + margin)


@dataclass
class PromptMedia:
    event: DetectionEvent
    clip: object
    entered_at: float
    duration: float

    def is_alive(self, now: float) -> bool:
        return (now - self.entered_at) <= self.duration


@dataclass
class SpawnedMedia:
    clip: object
    event: DetectionEvent
    owner_label: str
    x: float
    y: float
    scale: float
    born_at: float
    ttl: float
    rotation: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    spin_velocity: float = 0.0
    following: bool = True
    spawned_at_hand: bool = True

    def is_alive(self, now: float) -> bool:
        return (now - self.born_at) <= self.ttl

    def alpha(self, now: float) -> float:
        age = now - self.born_at
        fade_start = max(0.5, self.ttl - 2.0)
        if age <= fade_start:
            return 1.0
        remaining = self.ttl - age
        return _clamp(remaining / max(self.ttl - fade_start, 1e-3), 0.0, 1.0)


class SpawnController:
    def __init__(self, max_spawns: int = 12, spawn_ttl: float = 10.0, prompt_duration: float = 6.0):
        self.max_spawns = max_spawns
        self.spawn_ttl = spawn_ttl
        self.prompt_duration = prompt_duration
        self._prompt: PromptMedia | None = None
        self._spawns: list[SpawnedMedia] = []

    @property
    def prompt(self) -> PromptMedia | None:
        return self._prompt

    @property
    def spawns(self) -> list[SpawnedMedia]:
        return list(self._spawns)

    def set_prompt(self, event: DetectionEvent, clip: object) -> None:
        self._prompt = PromptMedia(
            event=event,
            clip=clip,
            entered_at=time.monotonic(),
            duration=self.prompt_duration,
        )

    def active_hand_themes(self, frame) -> dict[str, KeywordTheme]:
        now = time.monotonic()
        themes: dict[str, KeywordTheme] = {}
        for spawn in reversed(self._spawns):
            if spawn.is_alive(now):
                themes.setdefault(spawn.owner_label, spawn.event.theme)
        if self._prompt and self._prompt.is_alive(now):
            if frame.left.active:
                themes.setdefault("Left", self._prompt.event.theme)
            if frame.right.active:
                themes.setdefault("Right", self._prompt.event.theme)
        return themes

    def update(
        self,
        frame,
        prompt_rect: tuple[float, float, float, float] | None,
    ) -> None:
        now = time.monotonic()
        if self._prompt and not self._prompt.is_alive(now):
            self._prompt = None

        hands = {"Left": frame.left, "Right": frame.right}
        if self._prompt and prompt_rect is not None:
            for label, hand in hands.items():
                if not hand.active or not hand.just_pinched:
                    continue
                if _rect_contains(prompt_rect, hand.x, hand.y):
                    self._spawns.append(
                        SpawnedMedia(
                            clip=self._prompt.clip,
                            event=self._prompt.event,
                            owner_label=label,
                            x=hand.x,
                            y=hand.y,
                            scale=_clamp(0.55 + hand.radius * 1.5, 0.30, 1.60),
                            born_at=now,
                            ttl=self.spawn_ttl,
                            rotation=hand.angle,
                        )
                    )

        updated: list[SpawnedMedia] = []
        for spawn in self._spawns[-self.max_spawns:]:
            hand = hands.get(spawn.owner_label)
            if hand and hand.active and (hand.pinch_active or hand.just_pinched):
                spawn.following = True
                follow_mix = 0.42
                spawn.x += (hand.x - spawn.x) * follow_mix
                spawn.y += (hand.y - spawn.y) * follow_mix
                target_scale = _clamp(0.45 + hand.radius * 1.8 + hand.pinch_norm * 0.35, 0.26, 1.8)
                spawn.scale += (target_scale - spawn.scale) * 0.30
                spawn.rotation += (hand.spin * 0.14)
                spawn.spin_velocity = hand.spin * 0.05
                spawn.vx = hand.dx * 0.015
                spawn.vy = hand.dy * 0.015
                spawn.ttl = max(spawn.ttl, self.spawn_ttl)
            else:
                if hand and spawn.following:
                    spawn.vx = hand.dx * 0.020 if hand else spawn.vx
                    spawn.vy = hand.dy * 0.020 if hand else spawn.vy
                spawn.following = False
                spawn.x = _clamp(spawn.x + spawn.vx, -0.10, 1.10)
                spawn.y = _clamp(spawn.y + spawn.vy, -0.10, 1.10)
                spawn.vx *= 0.94
                spawn.vy *= 0.94
                spawn.rotation += spawn.spin_velocity
                spawn.spin_velocity *= 0.94
                spawn.scale = _clamp(spawn.scale * 0.998, 0.22, 2.0)
            if spawn.is_alive(now):
                updated.append(spawn)
        self._spawns = updated[-self.max_spawns:]

    def spawn_count(self) -> int:
        now = time.monotonic()
        return sum(1 for spawn in self._spawns if spawn.is_alive(now))

