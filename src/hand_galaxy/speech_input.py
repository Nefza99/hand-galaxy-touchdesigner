"""
speech_input.py  (v2.1)
-----------------------
Vosk speech recognition consumer of the shared AudioPipeline.
No longer owns a pyaudio stream — registers as 'speech' consumer instead.
"""
from __future__ import annotations
import json, logging, queue, threading, time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

_SAMPLE_RATE = 16_000
_BLOCK_SIZE  = 512


@dataclass
class SpeechResult:
    text:      str
    is_final:  bool
    timestamp: float = 0.0
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.monotonic()


class SpeechInput:
    """
    Vosk ASR wired to a shared AudioPipeline.
    Call start() AFTER pipeline.start().
    """
    def __init__(
        self,
        model_path: str | Path,
        pipeline,
        on_result: Optional[Callable[[SpeechResult], None]] = None,
    ):
        self.model_path = Path(model_path)
        self._pipeline  = pipeline
        self.on_result  = on_result
        self._q: queue.Queue[SpeechResult] = queue.Queue(maxsize=64)
        self._ready     = threading.Event()
        self._mic_ok    = False
        self._error: Optional[str] = None
        self._rec       = None

    def start(self) -> bool:
        try:
            import vosk
            vosk.SetLogLevel(-1)
            if not self.model_path.exists():
                self._error = f"Vosk model not found: {self.model_path}"
                log.error(self._error)
                return False
            model    = vosk.Model(str(self.model_path))
            self._rec = vosk.KaldiRecognizer(model, _SAMPLE_RATE)
            self._rec.SetWords(True)
            self._pipeline.add_consumer("speech", self._on_audio)
            self._mic_ok = True
            log.info("SpeechInput: Vosk ready.")
            return True
        except ImportError as exc:
            self._error = f"vosk not installed: {exc}"
            log.warning(self._error)
            return False
        except Exception as exc:
            self._error = f"Vosk init error: {exc}"
            log.error(self._error)
            return False

    def stop(self) -> None:
        self._pipeline.remove_consumer("speech")
        self._mic_ok = False

    def drain(self) -> list[SpeechResult]:
        out: list[SpeechResult] = []
        while True:
            try: out.append(self._q.get_nowait())
            except queue.Empty: break
        return out

    @property
    def is_listening(self) -> bool:
        return self._mic_ok

    @property
    def error(self) -> Optional[str]:
        return self._error

    def _on_audio(self, pcm_bytes: bytes, frames: int) -> None:
        if self._rec is None:
            return
        try:
            if self._rec.AcceptWaveform(pcm_bytes):
                data = json.loads(self._rec.Result())
                text = data.get("text", "").strip()
                if text:
                    self._emit(SpeechResult(text=text, is_final=True))
            else:
                data = json.loads(self._rec.PartialResult())
                partial = data.get("partial", "").strip()
                if partial:
                    self._emit(SpeechResult(text=partial, is_final=False))
        except Exception: pass

    def _emit(self, result: SpeechResult) -> None:
        if self.on_result:
            try: self.on_result(result)
            except Exception: pass
        if not self._q.full():
            self._q.put_nowait(result)


class SpeechInputStub:
    def __init__(self, *_, **__):
        self._error = "SpeechInput disabled."
    def start(self) -> bool:
        return False
    def stop(self) -> None: pass
    def drain(self) -> list: return []
    @property
    def is_listening(self) -> bool: return False
    @property
    def error(self) -> Optional[str]: return self._error


def make_speech_input(model_path, pipeline, **kwargs):
    try:
        import vosk  # noqa: F401
        return SpeechInput(model_path, pipeline, **kwargs)
    except ImportError:
        return SpeechInputStub()
