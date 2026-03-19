from __future__ import annotations

import math
from dataclasses import dataclass


def _clamp_midi(value: float) -> int:
    return max(0, min(127, int(round(value))))


def _hz_to_midi(hz: float) -> int:
    if hz <= 0.0:
        return 0
    return _clamp_midi(69.0 + 12.0 * math.log2(hz / 440.0))


@dataclass(frozen=True)
class MidiStatus:
    enabled: bool
    port_name: str = ""
    error: str | None = None


class MidiBridge:
    def __init__(self, enabled: bool = False, port_name: str | None = None):
        self.enabled = enabled
        self.port_name = port_name
        self._mido = None
        self._port = None
        self._last_note = None
        self._last_cc: dict[tuple[int, int], int] = {}
        self._status = MidiStatus(enabled=False, error="MIDI disabled")
        if enabled:
            self._open()

    @property
    def status(self) -> MidiStatus:
        return self._status

    def _open(self) -> None:
        try:
            import mido
        except ImportError as exc:
            self._status = MidiStatus(enabled=False, error=f"mido not installed: {exc}")
            return
        self._mido = mido
        try:
            output_name = self.port_name
            if output_name:
                self._port = mido.open_output(output_name)
            else:
                names = mido.get_output_names()
                if not names:
                    self._status = MidiStatus(enabled=False, error="No MIDI output ports found")
                    return
                output_name = names[0]
                self._port = mido.open_output(output_name)
            self._status = MidiStatus(enabled=True, port_name=output_name or "")
        except Exception as exc:
            self._status = MidiStatus(enabled=False, error=str(exc))

    def close(self) -> None:
        if self._port is not None:
            if self._last_note is not None and self._mido is not None:
                try:
                    self._port.send(self._mido.Message("note_off", note=self._last_note, velocity=0, channel=0))
                except Exception:
                    pass
            try:
                self._port.close()
            except Exception:
                pass
        self._port = None
        self._last_note = None

    def update(self, frame, pitch_result, amplitude, hand_themes: dict[str, object]) -> None:
        if not self._status.enabled or self._port is None or self._mido is None:
            return
        amp = amplitude.amplitude if amplitude else 0.0
        if pitch_result and pitch_result.is_voiced:
            note = _hz_to_midi(pitch_result.hz)
            velocity = _clamp_midi(28 + amp * 72 + getattr(pitch_result, "confidence", 0.0) * 24)
            if note != self._last_note:
                if self._last_note is not None:
                    self._port.send(self._mido.Message("note_off", note=self._last_note, velocity=0, channel=0))
                self._port.send(self._mido.Message("note_on", note=note, velocity=velocity, channel=0))
                self._last_note = note
            self._send_cc(0, 1, amp * 127.0)
            self._send_cc(0, 2, pitch_result.normalised * 127.0)
            self._send_cc(0, 3, getattr(pitch_result, "velocity", 0.0) * 0.05 + 64.0)
        elif self._last_note is not None:
            self._port.send(self._mido.Message("note_off", note=self._last_note, velocity=0, channel=0))
            self._last_note = None

        for channel, hand in ((1, frame.left), (2, frame.right)):
            theme = hand_themes.get(hand.label) if hand else None
            theme_hue = getattr(theme, "hue", 0.0)
            pinch_val = hand.pinch_norm if hand else 0.0
            self._send_cc(channel, 16, pinch_val * 127.0)
            self._send_cc(channel, 17, hand.x * 127.0 if hand else 0.0)
            self._send_cc(channel, 18, hand.y * 127.0 if hand else 0.0)
            self._send_cc(channel, 19, (hand.energy if hand else 0.0) * 127.0)
            self._send_cc(channel, 20, theme_hue * 127.0)

    def _send_cc(self, channel: int, control: int, value: float) -> None:
        midi_value = _clamp_midi(value)
        key = (channel, control)
        if self._last_cc.get(key) == midi_value:
            return
        self._last_cc[key] = midi_value
        self._port.send(
            self._mido.Message(
                "control_change",
                channel=channel,
                control=control,
                value=midi_value,
            )
        )
