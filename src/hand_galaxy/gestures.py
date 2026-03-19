from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Any


THUMB_TIP = 4
INDEX_TIP = 8
WRIST = 0


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def smooth(current: float, target: float, alpha: float) -> float:
    return current + (target - current) * clamp(alpha, 0.0, 1.0)


def remap(value: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    if abs(in_max - in_min) < 1e-9:
        return out_min
    t = clamp((value - in_min) / (in_max - in_min), 0.0, 1.0)
    return out_min + (out_max - out_min) * t


def angle_delta(current: float, previous: float) -> float:
    return (current - previous + math.pi) % (math.tau) - math.pi


def category_label(category: Any) -> str:
    return (
        getattr(category, "category_name", None)
        or getattr(category, "categoryName", None)
        or getattr(category, "display_name", None)
        or getattr(category, "displayName", None)
        or "Unknown"
    )


def category_score(category: Any) -> float:
    try:
        return float(getattr(category, "score", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


@dataclass(slots=True)
class HandTelemetry:
    slot: str
    label: str
    handedness_value: float
    score: float
    active: bool
    x: float
    y: float
    x_raw: float
    y_raw: float
    thumb_x: float
    thumb_y: float
    index_x: float
    index_y: float
    wrist_x: float
    wrist_y: float
    world_x: float
    world_y: float
    world_z: float
    pinch_raw: float
    pinch_norm: float
    radius: float
    velocity: float
    dx: float
    dy: float
    spin: float
    burst: float
    energy: float
    depth: float
    angle: float
    pinch_active: bool
    open_state: bool
    just_pinched: bool
    just_released: bool
    trail: tuple[tuple[float, float], ...] = ()
    landmarks: tuple[tuple[float, float, float], ...] = ()


@dataclass(slots=True)
class GestureFrame:
    timestamp_ms: int
    frame_width: int
    frame_height: int
    active_hands: int
    primary: HandTelemetry
    secondary: HandTelemetry


@dataclass(slots=True)
class HandState:
    label: str
    score: float = 0.0
    active: bool = False
    last_seen_ms: int = 0
    x: float = 0.5
    y: float = 0.5
    x_raw: float = 0.5
    y_raw: float = 0.5
    thumb_x: float = 0.5
    thumb_y: float = 0.5
    index_x: float = 0.5
    index_y: float = 0.5
    wrist_x: float = 0.5
    wrist_y: float = 0.5
    world_x: float = 0.0
    world_y: float = 0.0
    world_z: float = 0.0
    pinch_raw: float = 0.0
    pinch_norm: float = 0.0
    radius: float = 0.1
    velocity: float = 0.0
    dx: float = 0.0
    dy: float = 0.0
    spin: float = 0.0
    burst: float = 0.0
    energy: float = 0.0
    depth: float = 0.0
    angle: float = 0.0
    pinch_active: bool = False
    open_state: bool = True
    just_pinched: bool = False
    just_released: bool = False
    trail: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=18))
    landmarks: tuple[tuple[float, float, float], ...] = ()


class GestureEngine:
    def __init__(self, config: Any):
        self.position_alpha = config.position_smoothing
        self.pinch_alpha = config.pinch_smoothing
        self.velocity_alpha = config.velocity_smoothing
        self.pinch_close_threshold = config.pinch_close_threshold
        self.pinch_open_threshold = config.pinch_open_threshold
        self.velocity_burst_threshold = config.velocity_burst_threshold
        self.idle_timeout_ms = config.idle_timeout_ms
        self._states = {
            "Left": HandState(label="Left"),
            "Right": HandState(label="Right"),
        }

    def process(self, result: Any, frame_width: int, frame_height: int, timestamp_ms: int) -> GestureFrame:
        seen = set()
        hand_landmarks = list(getattr(result, "hand_landmarks", []) or [])
        world_landmarks = list(getattr(result, "hand_world_landmarks", []) or [])
        handedness = list(getattr(result, "handedness", []) or [])

        for idx, landmarks in enumerate(hand_landmarks):
            categories = handedness[idx] if idx < len(handedness) else []
            category = categories[0] if categories else None
            label = category_label(category)
            if label not in self._states:
                self._states[label] = HandState(label=label)

            world = world_landmarks[idx] if idx < len(world_landmarks) else []
            self._update_state(
                self._states[label],
                landmarks=landmarks,
                world_landmarks=world,
                score=category_score(category),
                timestamp_ms=timestamp_ms,
            )
            seen.add(label)

        for label, state in self._states.items():
            if label not in seen:
                self._decay_state(state, timestamp_ms)

        active = [self._to_telemetry(name, state) for name, state in self._states.items()]
        active.sort(
            key=lambda hand: (
                1 if hand.active else 0,
                hand.energy,
                hand.score,
                hand.pinch_active,
            ),
            reverse=True,
        )

        primary = active[0] if active else self._inactive_telemetry("primary")
        secondary = active[1] if len(active) > 1 else self._inactive_telemetry("secondary")
        primary = self._replace_slot(primary, "primary")
        secondary = self._replace_slot(secondary, "secondary")

        active_hands = sum(1 for state in self._states.values() if state.active)
        return GestureFrame(
            timestamp_ms=timestamp_ms,
            frame_width=frame_width,
            frame_height=frame_height,
            active_hands=active_hands,
            primary=primary,
            secondary=secondary,
        )

    def _update_state(
        self,
        state: HandState,
        landmarks: list[Any],
        world_landmarks: list[Any],
        score: float,
        timestamp_ms: int,
    ) -> None:
        thumb = landmarks[THUMB_TIP]
        index = landmarks[INDEX_TIP]
        wrist = landmarks[WRIST]

        x_raw = (float(thumb.x) + float(index.x)) * 0.5
        y_raw = (float(thumb.y) + float(index.y)) * 0.5
        pinch_raw = math.hypot(float(index.x) - float(thumb.x), float(index.y) - float(thumb.y))
        pinch_norm_target = 1.0 - remap(pinch_raw, self.pinch_close_threshold, 0.28, 0.0, 1.0)
        radius_target = remap(pinch_raw, self.pinch_close_threshold * 0.75, 0.23, 0.08, 0.6)
        angle = math.atan2(float(index.y) - float(thumb.y), float(index.x) - float(thumb.x))

        dt = max((timestamp_ms - state.last_seen_ms) / 1000.0, 1.0 / 120.0) if state.last_seen_ms else 1.0 / 60.0
        velocity_raw = math.hypot(x_raw - state.x_raw, y_raw - state.y_raw) / dt
        dx_raw = (x_raw - state.x_raw) / dt
        dy_raw = (y_raw - state.y_raw) / dt
        angular_velocity = angle_delta(angle, state.angle) / dt if state.last_seen_ms else 0.0

        state.x = smooth(state.x, x_raw, self.position_alpha)
        state.y = smooth(state.y, y_raw, self.position_alpha)
        state.x_raw = x_raw
        state.y_raw = y_raw
        state.thumb_x = float(thumb.x)
        state.thumb_y = float(thumb.y)
        state.index_x = float(index.x)
        state.index_y = float(index.y)
        state.wrist_x = float(wrist.x)
        state.wrist_y = float(wrist.y)
        state.landmarks = tuple(
            (
                float(getattr(point, "x", 0.0)),
                float(getattr(point, "y", 0.0)),
                float(getattr(point, "z", 0.0)),
            )
            for point in landmarks
        )
        state.velocity = smooth(state.velocity, velocity_raw, self.velocity_alpha)
        state.dx = smooth(state.dx, dx_raw, self.velocity_alpha)
        state.dy = smooth(state.dy, dy_raw, self.velocity_alpha)
        state.spin = smooth(state.spin, clamp(angular_velocity / math.pi, -6.0, 6.0), self.velocity_alpha)
        state.pinch_raw = smooth(state.pinch_raw, pinch_raw, self.pinch_alpha)
        state.pinch_norm = smooth(state.pinch_norm, pinch_norm_target, self.pinch_alpha)
        state.radius = smooth(state.radius, radius_target, self.pinch_alpha)
        state.angle = angle

        if world_landmarks:
            world_thumb = world_landmarks[THUMB_TIP]
            world_index = world_landmarks[INDEX_TIP]
            state.world_x = smooth(state.world_x, (float(world_thumb.x) + float(world_index.x)) * 0.5, 0.2)
            state.world_y = smooth(state.world_y, (float(world_thumb.y) + float(world_index.y)) * 0.5, 0.2)
            state.world_z = smooth(state.world_z, (float(world_thumb.z) + float(world_index.z)) * 0.5, 0.2)

        state.depth = smooth(state.depth, clamp(-0.5 * (float(thumb.z) + float(index.z)), -1.0, 1.0), 0.2)

        was_pinching = state.pinch_active
        state.pinch_active = (
            pinch_raw <= self.pinch_open_threshold if was_pinching else pinch_raw <= self.pinch_close_threshold
        )
        state.open_state = pinch_raw >= self.pinch_open_threshold
        state.just_pinched = state.pinch_active and not was_pinching
        state.just_released = (not state.pinch_active) and was_pinching

        burst_velocity = remap(state.velocity, self.velocity_burst_threshold, self.velocity_burst_threshold * 3.0, 0.0, 1.0)
        burst_release = 1.0 if state.just_released else 0.0
        burst_target = max(burst_velocity * (0.55 + 0.45 * state.pinch_norm), burst_release)
        state.burst = max(burst_target, state.burst * 0.82)

        energy_target = clamp(
            state.pinch_norm * 0.55
            + remap(state.velocity, 0.0, 2.2, 0.0, 1.0) * 0.3
            + remap(abs(state.spin), 0.0, 3.5, 0.0, 1.0) * 0.15,
            0.0,
            1.0,
        )
        state.energy = smooth(state.energy, energy_target, 0.22)
        state.score = score
        state.active = True
        state.last_seen_ms = timestamp_ms
        state.trail.append((state.x, state.y))

    def _decay_state(self, state: HandState, timestamp_ms: int) -> None:
        missing_ms = timestamp_ms - state.last_seen_ms if state.last_seen_ms else self.idle_timeout_ms + 1
        state.just_pinched = False
        state.just_released = False
        if missing_ms <= self.idle_timeout_ms:
            return

        state.active = False
        state.velocity *= 0.8
        state.dx *= 0.8
        state.dy *= 0.8
        state.spin *= 0.8
        state.burst *= 0.75
        state.energy *= 0.84
        state.pinch_norm *= 0.88
        state.radius = smooth(state.radius, 0.1, 0.12)
        if missing_ms > self.idle_timeout_ms * 4:
            state.trail.clear()

    def _to_telemetry(self, slot: str, state: HandState) -> HandTelemetry:
        label = state.label or "Unknown"
        handedness_value = 0.0 if label.lower().startswith("left") else 1.0
        return HandTelemetry(
            slot=slot,
            label=label,
            handedness_value=handedness_value,
            score=state.score,
            active=state.active,
            x=state.x,
            y=state.y,
            x_raw=state.x_raw,
            y_raw=state.y_raw,
            thumb_x=state.thumb_x,
            thumb_y=state.thumb_y,
            index_x=state.index_x,
            index_y=state.index_y,
            wrist_x=state.wrist_x,
            wrist_y=state.wrist_y,
            world_x=state.world_x,
            world_y=state.world_y,
            world_z=state.world_z,
            pinch_raw=state.pinch_raw,
            pinch_norm=state.pinch_norm,
            radius=state.radius,
            velocity=state.velocity,
            dx=state.dx,
            dy=state.dy,
            spin=state.spin,
            burst=state.burst,
            energy=state.energy,
            depth=state.depth,
            angle=state.angle,
            pinch_active=state.pinch_active,
            open_state=state.open_state,
            just_pinched=state.just_pinched,
            just_released=state.just_released,
            trail=tuple(state.trail),
            landmarks=state.landmarks,
        )

    def _inactive_telemetry(self, slot: str) -> HandTelemetry:
        return HandTelemetry(
            slot=slot,
            label="None",
            handedness_value=0.0,
            score=0.0,
            active=False,
            x=0.5,
            y=0.5,
            x_raw=0.5,
            y_raw=0.5,
            thumb_x=0.5,
            thumb_y=0.5,
            index_x=0.5,
            index_y=0.5,
            wrist_x=0.5,
            wrist_y=0.5,
            world_x=0.0,
            world_y=0.0,
            world_z=0.0,
            pinch_raw=0.0,
            pinch_norm=0.0,
            radius=0.1,
            velocity=0.0,
            dx=0.0,
            dy=0.0,
            spin=0.0,
            burst=0.0,
            energy=0.0,
            depth=0.0,
            angle=0.0,
            pinch_active=False,
            open_state=False,
            just_pinched=False,
            just_released=False,
            trail=(),
            landmarks=(),
        )

    def _replace_slot(self, hand: HandTelemetry, slot: str) -> HandTelemetry:
        return replace(hand, slot=slot)
