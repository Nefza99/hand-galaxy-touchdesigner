from __future__ import annotations

from dataclasses import dataclass, field


class VirtualCameraSetupError(RuntimeError):
    """Raised when virtual camera mode is requested but the backend is unavailable."""


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

        try:
            import pyvirtualcam  # type: ignore
        except ModuleNotFoundError as exc:
            raise VirtualCameraSetupError(
                "TouchDesigner mode needs the optional virtual camera package, but it is not installed."
            ) from exc

        self._module = pyvirtualcam
        try:
            self._camera = pyvirtualcam.Camera(
                width=self.width,
                height=self.height,
                fps=self.fps,
                fmt=pyvirtualcam.PixelFormat.BGR,
            )
        except RuntimeError as exc:
            raise VirtualCameraSetupError(
                "TouchDesigner mode needs a Windows virtual camera backend.\n"
                "Install OBS Virtual Camera or UnityCapture, then try again.\n"
                "If you only want hand tracking right now, launch the normal camera preview mode instead.\n\n"
                f"Backend details: {exc}"
            ) from exc

    def send(self, frame) -> None:
        if not self._camera:
            return
        self._camera.send(frame)
        self._camera.sleep_until_next_frame()

    def close(self) -> None:
        if self._camera:
            self._camera.close()
            self._camera = None
