from __future__ import annotations

import colorsys
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


def fract(value: float) -> float:
    return value % 1.0


def circular_distance(a: float, b: float) -> float:
    delta = abs(a - b) % 1.0
    return min(delta, 1.0 - delta)


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


def hsv_to_rgb(hue: float, saturation: float, value: float) -> tuple[float, float, float]:
    red, green, blue = colorsys.hsv_to_rgb(fract(hue), clamp(saturation, 0.0, 1.0), clamp(value, 0.0, 1.0))
    return red, green, blue


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
    hue: float
    accent_hue: float
    saturation: float
    value: float
    color_r: float
    color_g: float
    color_b: float
    palette: float
    shimmer: float
    ribbon: float
    flare: float
    vortex: float
    turbulence: float
    halo: float
    pulse: float
    pinch_active: bool
    open_state: bool
    just_pinched: bool
    just_released: bool
    trail: tuple[tuple[float, float], ...] = ()
    landmarks: tuple[tuple[float, float, float], ...] = ()


@dataclass(slots=True)
class FusionTelemetry:
    active: bool
    x: float
    y: float
    distance: float
    angle: float
    converge: float
    symmetry: float
    bridge: float
    bloom: float
    vortex: float
    chaos: float
    pulse: float
    hue: float
    accent_hue: float
    color_r: float
    color_g: float
    color_b: float


@dataclass(slots=True)
class GestureFrame:
    timestamp_ms: int
    frame_width: int
    frame_height: int
    active_hands: int
    primary: HandTelemetry
    secondary: HandTelemetry
    fusion: FusionTelemetry


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
    hue: float = 0.0
    accent_hue: float = 0.18
    saturation: float = 0.55
    value: float = 0.2
    color_r: float = 0.2
    color_g: float = 0.2
    color_b: float = 0.2
    palette: float = 0.0
    shimmer: float = 0.0
    ribbon: float = 0.0
    flare: float = 0.0
    vortex: float = 0.0
    turbulence: float = 0.0
    halo: float = 0.0
    pulse: float = 0.0
    pinch_active: bool = False
    open_state: bool = True
    just_pinched: bool = False
    just_released: bool = False
    trail: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=18))
    landmarks: tuple[tuple[float, float, float], ...] = ()


@dataclass(slots=True)
class FusionState:
    active: bool = False
    x: float = 0.5
    y: float = 0.5
    distance: float = 0.0
    angle: float = 0.0
    converge: float = 0.0
    symmetry: float = 0.0
    bridge: float = 0.0
    bloom: float = 0.0
    vortex: float = 0.0
    chaos: float = 0.0
    pulse: float = 0.0
    hue: float = 0.0
    accent_hue: float = 0.18
    color_r: float = 0.25
    color_g: float = 0.25
    color_b: float = 0.25


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
        self._fusion = FusionState()

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
        fusion = self._update_fusion(primary, secondary, timestamp_ms)

        active_hands = sum(1 for state in self._states.values() if state.active)
        return GestureFrame(
            timestamp_ms=timestamp_ms,
            frame_width=frame_width,
            frame_height=frame_height,
            active_hands=active_hands,
            primary=primary,
            secondary=secondary,
            fusion=fusion,
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

        burst_velocity = remap(
            state.velocity,
            self.velocity_burst_threshold,
            self.velocity_burst_threshold * 3.0,
            0.0,
            1.0,
        )
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

        hand_anchor = self._hand_anchor(state.label)
        palette_target = clamp(
            (0.55 if state.label.lower().startswith("left") else 3.05)
            + remap(state.pinch_norm, 0.0, 1.0, 0.0, 1.1)
            + remap(state.burst, 0.0, 1.0, 0.0, 0.7)
            + remap(abs(state.depth), 0.0, 0.8, 0.0, 0.45),
            0.0,
            5.0,
        )
        hue_target = fract(
            hand_anchor
            + (state.angle / math.tau) * 0.34
            + state.depth * 0.16
            + state.pinch_norm * 0.09
            + remap(state.velocity, 0.0, 2.2, 0.0, 0.09)
        )
        accent_target = fract(
            hue_target
            + 0.18
            + remap(abs(state.spin), 0.0, 3.2, 0.0, 0.10)
            + remap(state.burst, 0.0, 1.0, 0.0, 0.08)
        )
        saturation_target = clamp(
            0.42
            + state.pinch_norm * 0.22
            + remap(state.velocity, 0.0, 2.2, 0.0, 0.2)
            + state.burst * 0.18,
            0.18,
            1.0,
        )
        value_target = clamp(
            0.22
            + state.energy * 0.55
            + state.burst * 0.25
            + remap(abs(state.depth), 0.0, 0.8, 0.0, 0.08),
            0.08,
            1.0,
        )
        trail_ratio = len(state.trail) / float(state.trail.maxlen or 1)
        shimmer_target = clamp(
            remap(abs(state.spin), 0.0, 2.8, 0.0, 0.45)
            + remap(state.velocity, 0.15, 2.2, 0.0, 0.35)
            + state.burst * 0.2,
            0.0,
            1.0,
        )
        ribbon_target = clamp(
            remap(state.velocity, 0.08, 1.4, 0.0, 0.55)
            + trail_ratio * 0.25
            + state.energy * 0.2,
            0.0,
            1.0,
        )
        flare_target = clamp(
            state.burst * 0.65
            + state.energy * 0.25
            + (0.18 if state.just_pinched else 0.0),
            0.0,
            1.0,
        )
        vortex_target = clamp(
            remap(abs(state.spin), 0.0, 2.6, 0.0, 0.55)
            + state.pinch_norm * 0.25
            + remap(state.radius, 0.08, 0.6, 0.0, 0.22),
            0.0,
            1.0,
        )
        turbulence_target = clamp(
            remap(state.velocity, 0.05, 2.4, 0.0, 0.6)
            + remap(abs(state.depth), 0.0, 0.8, 0.0, 0.2)
            + remap(abs(state.dx - state.dy), 0.0, 2.2, 0.0, 0.2),
            0.0,
            1.0,
        )
        halo_target = clamp(
            remap(state.radius, 0.08, 0.6, 0.18, 1.0) * 0.55
            + (1.0 - state.pinch_norm) * 0.25
            + state.energy * 0.2,
            0.0,
            1.0,
        )
        pulse_wave = 0.5 + 0.5 * math.sin(timestamp_ms * 0.0018 + state.angle * 2.2 + hand_anchor * math.tau)
        pulse_target = clamp((0.18 + pulse_wave * 0.82) * (0.3 + state.energy * 0.7), 0.0, 1.0)

        state.palette = smooth(state.palette, palette_target, 0.16)
        state.hue = smooth(state.hue, hue_target, 0.22)
        state.accent_hue = smooth(state.accent_hue, accent_target, 0.22)
        state.saturation = smooth(state.saturation, saturation_target, 0.22)
        state.value = smooth(state.value, value_target, 0.24)
        state.shimmer = smooth(state.shimmer, shimmer_target, 0.24)
        state.ribbon = smooth(state.ribbon, ribbon_target, 0.22)
        state.flare = max(flare_target, state.flare * 0.84)
        state.vortex = smooth(state.vortex, vortex_target, 0.22)
        state.turbulence = smooth(state.turbulence, turbulence_target, 0.22)
        state.halo = smooth(state.halo, halo_target, 0.2)
        state.pulse = smooth(state.pulse, pulse_target, 0.24)

        color_r, color_g, color_b = hsv_to_rgb(state.hue, state.saturation, state.value)
        state.color_r = smooth(state.color_r, color_r, 0.24)
        state.color_g = smooth(state.color_g, color_g, 0.24)
        state.color_b = smooth(state.color_b, color_b, 0.24)

        state.score = score
        state.active = True
        state.last_seen_ms = timestamp_ms
        state.trail.append((state.x, state.y))

    def _update_fusion(self, primary: HandTelemetry, secondary: HandTelemetry, timestamp_ms: int) -> FusionTelemetry:
        state = self._fusion
        both_active = primary.active and secondary.active

        if both_active:
            dx = secondary.x - primary.x
            dy = secondary.y - primary.y
            distance_target = math.hypot(dx, dy)
            angle_target = math.atan2(dy, dx)
            converge_target = 1.0 - remap(distance_target, 0.08, 0.82, 0.0, 1.0)
            mirror_gap = abs(primary.x - (1.0 - secondary.x))
            height_gap = abs(primary.y - secondary.y)
            radius_gap = abs(primary.radius - secondary.radius)
            symmetry_target = clamp(1.0 - mirror_gap * 1.4 - height_gap * 0.8 - radius_gap * 0.9, 0.0, 1.0)
            bridge_target = clamp(
                (primary.energy + secondary.energy) * 0.3
                + converge_target * 0.35
                + (primary.ribbon + secondary.ribbon) * 0.18
                + 0.12,
                0.0,
                1.0,
            )
            bloom_target = clamp(
                (primary.flare + secondary.flare) * 0.4
                + max(primary.burst, secondary.burst) * 0.25
                + converge_target * 0.2
                + (primary.energy + secondary.energy) * 0.15,
                0.0,
                1.0,
            )
            vortex_target = clamp(
                (primary.vortex + secondary.vortex) * 0.38
                + remap(abs(primary.spin - secondary.spin), 0.0, 3.0, 0.0, 0.18)
                + converge_target * 0.24
                + symmetry_target * 0.1,
                0.0,
                1.0,
            )
            chaos_target = clamp(
                remap(abs(primary.velocity - secondary.velocity), 0.0, 1.4, 0.0, 0.45)
                + remap(abs(primary.spin - secondary.spin), 0.0, 2.4, 0.0, 0.35)
                + remap(circular_distance(primary.hue, secondary.hue), 0.0, 0.5, 0.0, 0.2),
                0.0,
                1.0,
            )
            pulse_wave = 0.5 + 0.5 * math.sin(timestamp_ms * 0.0026 + angle_target * 2.0 + (primary.palette + secondary.palette) * 0.4)
            pulse_target = clamp((0.25 + pulse_wave * 0.75) * (0.3 + bridge_target * 0.7), 0.0, 1.0)
            hue_target = fract(
                primary.hue * (0.45 + converge_target * 0.1)
                + secondary.hue * (0.55 - converge_target * 0.1)
                + chaos_target * 0.08
            )
            accent_target = fract((primary.accent_hue + secondary.accent_hue) * 0.5 + converge_target * 0.08)

            state.active = True
            state.x = smooth(state.x, (primary.x + secondary.x) * 0.5, 0.18)
            state.y = smooth(state.y, (primary.y + secondary.y) * 0.5, 0.18)
            state.distance = smooth(state.distance, distance_target, 0.18)
            state.angle = smooth(state.angle, angle_target, 0.18)
            state.converge = smooth(state.converge, converge_target, 0.22)
            state.symmetry = smooth(state.symmetry, symmetry_target, 0.2)
            state.bridge = smooth(state.bridge, bridge_target, 0.22)
            state.bloom = max(bloom_target, state.bloom * 0.86)
            state.vortex = smooth(state.vortex, vortex_target, 0.22)
            state.chaos = smooth(state.chaos, chaos_target, 0.22)
            state.pulse = smooth(state.pulse, pulse_target, 0.22)
            state.hue = smooth(state.hue, hue_target, 0.18)
            state.accent_hue = smooth(state.accent_hue, accent_target, 0.18)

            color_r = clamp((primary.color_r + secondary.color_r) * 0.5 + state.bloom * 0.08, 0.0, 1.0)
            color_g = clamp((primary.color_g + secondary.color_g) * 0.5 + state.bridge * 0.05, 0.0, 1.0)
            color_b = clamp((primary.color_b + secondary.color_b) * 0.5 + state.pulse * 0.05, 0.0, 1.0)
            state.color_r = smooth(state.color_r, color_r, 0.24)
            state.color_g = smooth(state.color_g, color_g, 0.24)
            state.color_b = smooth(state.color_b, color_b, 0.24)
        else:
            state.active = False
            state.distance *= 0.86
            state.converge *= 0.82
            state.symmetry *= 0.84
            state.bridge *= 0.84
            state.bloom *= 0.8
            state.vortex *= 0.84
            state.chaos *= 0.88
            state.pulse *= 0.86
            state.color_r *= 0.92
            state.color_g *= 0.92
            state.color_b *= 0.92

        return FusionTelemetry(
            active=state.active,
            x=state.x,
            y=state.y,
            distance=state.distance,
            angle=state.angle,
            converge=state.converge,
            symmetry=state.symmetry,
            bridge=state.bridge,
            bloom=state.bloom,
            vortex=state.vortex,
            chaos=state.chaos,
            pulse=state.pulse,
            hue=state.hue,
            accent_hue=state.accent_hue,
            color_r=state.color_r,
            color_g=state.color_g,
            color_b=state.color_b,
        )

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
        state.shimmer *= 0.82
        state.ribbon *= 0.85
        state.flare *= 0.76
        state.vortex *= 0.82
        state.turbulence *= 0.84
        state.halo *= 0.86
        state.pulse *= 0.86
        state.value *= 0.92
        state.color_r *= 0.94
        state.color_g *= 0.94
        state.color_b *= 0.94
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
            hue=state.hue,
            accent_hue=state.accent_hue,
            saturation=state.saturation,
            value=state.value,
            color_r=state.color_r,
            color_g=state.color_g,
            color_b=state.color_b,
            palette=state.palette,
            shimmer=state.shimmer,
            ribbon=state.ribbon,
            flare=state.flare,
            vortex=state.vortex,
            turbulence=state.turbulence,
            halo=state.halo,
            pulse=state.pulse,
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
            hue=0.0,
            accent_hue=0.18,
            saturation=0.0,
            value=0.0,
            color_r=0.0,
            color_g=0.0,
            color_b=0.0,
            palette=0.0,
            shimmer=0.0,
            ribbon=0.0,
            flare=0.0,
            vortex=0.0,
            turbulence=0.0,
            halo=0.0,
            pulse=0.0,
            pinch_active=False,
            open_state=False,
            just_pinched=False,
            just_released=False,
            trail=(),
            landmarks=(),
        )

    def _replace_slot(self, hand: HandTelemetry, slot: str) -> HandTelemetry:
        return replace(hand, slot=slot)

    def _hand_anchor(self, label: str) -> float:
        return 0.14 if label.lower().startswith("left") else 0.62
