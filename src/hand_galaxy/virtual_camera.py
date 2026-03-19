from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class VirtualCameraPublisher:
    width: int
    height: int
    fps: int
    enabled: bool = False
    _camera: object | None = field(default=None, init=False, repr=False)
    _module: object | None = field(default=None, init=False, repr=False)

    def start(self) -> None:
        if not self.enabled:
            return

        import pyvirtualcam  # type: ignore

        self._module = pyvirtualcam
        self._camera = pyvirtualcam.Camera(
            width=self.width,
            height=self.height,
            fps=self.fps,
            fmt=pyvirtualcam.PixelFormat.BGR,
        )

    def send(self, frame) -> None:
        if not self._camera:
            return
        self._camera.send(frame)
        self._camera.sleep_until_next_frame()

    def close(self) -> None:
        if self._camera:
            self._camera.close()
            self._camera = None
