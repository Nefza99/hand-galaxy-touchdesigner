"""
audio_pipeline.py
-----------------
A single pyaudio capture stream that broadcasts raw PCM frames to multiple
registered consumer callbacks.

This prevents mic conflicts when both Vosk (speech) and aubio (pitch) need
the same hardware at the same time.

Usage::

    pipeline = AudioPipeline(sample_rate=16000, block_size=512)
    pipeline.add_consumer("speech", my_speech_callback)
    pipeline.add_consumer("pitch",  my_pitch_callback)
    pipeline.start()          # daemon thread
    ...
    pipeline.stop()

Each consumer callback receives ``(pcm_bytes: bytes, frames: int)``.
Callbacks are called in registration order from the capture thread —
keep them fast (< 1 ms).  Use queues to offload heavy work.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)

# ── defaults ────────────────────────────────────────────────────────────────
_SAMPLE_RATE = 16_000   # Hz  — matches Vosk + aubio requirement
_BLOCK_SIZE  = 512      # frames per read  (~32 ms at 16 kHz)
_FORMAT_INT16 = None    # resolved at runtime from pyaudio.paInt16


class AudioPipeline:
    """
    Manages one pyaudio input stream and fans raw PCM bytes out to N consumers.

    Parameters
    ----------
    sample_rate : int
        Microphone capture rate.  16 000 is optimal for both Vosk and aubio.
    block_size : int
        Frames read per pyaudio call.  512 gives ~32 ms latency.
    device_index : int | None
        System mic device index.  None = system default.
    """

    def __init__(
        self,
        sample_rate: int = _SAMPLE_RATE,
        block_size:  int = _BLOCK_SIZE,
        device_index: Optional[int] = None,
    ):
        self.sample_rate  = sample_rate
        self.block_size   = block_size
        self.device_index = device_index

        self._consumers: dict[str, Callable[[bytes, int], None]] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._ready      = threading.Event()
        self._ok         = False
        self._error: Optional[str] = None

    # ── public API ───────────────────────────────────────────────────────────

    def add_consumer(
        self,
        name: str,
        callback: Callable[[bytes, int], None],
    ) -> None:
        """Register a named consumer before calling start()."""
        self._consumers[name] = callback

    def remove_consumer(self, name: str) -> None:
        self._consumers.pop(name, None)

    def start(self) -> bool:
        """
        Open the microphone and begin streaming.
        Blocks up to 4 s waiting for hardware to open.
        Returns True on success.
        """
        self._stop_event.clear()
        self._ready.clear()
        self._ok = False
        self._error = None
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="AudioPipeline"
        )
        self._thread.start()
        self._ready.wait(timeout=4.0)
        if not self._ready.is_set() and not self._error:
            self._error = "Microphone open timed out."
        return self._ok

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    @property
    def is_running(self) -> bool:
        return self._ok and not self._stop_event.is_set()

    @property
    def error(self) -> Optional[str]:
        return self._error

    # ── internal ─────────────────────────────────────────────────────────────

    def _run(self) -> None:
        try:
            import pyaudio
            global _FORMAT_INT16
            _FORMAT_INT16 = pyaudio.paInt16
        except ImportError as exc:
            self._error = f"pyaudio not installed: {exc}"
            log.error(self._error)
            self._ready.set()
            return

        import pyaudio
        p = pyaudio.PyAudio()
        stream = None

        try:
            kw: dict = dict(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.block_size,
            )
            if self.device_index is not None:
                kw["input_device_index"] = self.device_index
            stream = p.open(**kw)
            stream.start_stream()
            self._ok = True
            log.info(
                "AudioPipeline: mic open  sr=%d  block=%d  consumers=%s",
                self.sample_rate, self.block_size, list(self._consumers),
            )
        except Exception as exc:                          # noqa: BLE001
            self._error = f"Mic open error: {exc}"
            log.error(self._error)
            self._ready.set()
            p.terminate()
            return
        finally:
            self._ready.set()

        try:
            while not self._stop_event.is_set():
                try:
                    pcm = stream.read(self.block_size, exception_on_overflow=False)
                except OSError:
                    continue
                for cb in list(self._consumers.values()):
                    try:
                        cb(pcm, self.block_size)
                    except Exception:                     # noqa: BLE001
                        pass
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            self._ok = False
            log.info("AudioPipeline: stopped.")
