"""
launcher_gui.py
---------------
Tkinter-based GUI launcher for Hand Galaxy v2.2.
No external dependencies beyond Python's standard library.

Run:
    python installer/launcher_gui.py
or via  Launcher.bat
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

# ── paths ─────────────────────────────────────────────────────────────────────
_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_PYTHON       = (_PROJECT_ROOT / ".venv" / "Scripts" / "python.exe") if os.name == "nt" else (_PROJECT_ROOT / ".venv" / "bin" / "python")
_SRC_PATH     = _PROJECT_ROOT / "src"


def _venv_can_import(module_name: str) -> bool:
    if not _PYTHON.exists():
        return False
    try:
        result = subprocess.run(
            [str(_PYTHON), "-c", f"import {module_name}"],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=12,
        )
        return result.returncode == 0
    except Exception:
        return False

# ── palette ───────────────────────────────────────────────────────────────────
BG       = "#0a0a12"
BG2      = "#11111e"
ACCENT   = "#3de0c8"
ACCENT2  = "#7b5cff"
TEXT     = "#d0d0e0"
DIM      = "#555570"
RED      = "#e05050"
GREEN    = "#40d080"
FONT_LG  = ("Consolas", 22, "bold")
FONT_MD  = ("Consolas", 12)
FONT_SM  = ("Consolas", 10)
FONT_BTN = ("Consolas", 13, "bold")


class LauncherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hand Galaxy v2.2.0 — Launcher")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("640x580")
        self._process: subprocess.Popen | None = None
        self._running = False
        self._build_ui()
        self._check_installation()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Header
        hdr = tk.Frame(self, bg=BG, pady=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text="✦  HAND GALAXY  ✦", font=FONT_LG,
                 fg=ACCENT, bg=BG).pack()
        tk.Label(hdr, text="v2.2.0  │  Real-Time Audiovisual Interaction",
                 font=FONT_SM, fg=DIM, bg=BG).pack()

        # ── Divider
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20)

        # ── Options frame
        opts = tk.LabelFrame(self, text=" Launch Options ", font=FONT_SM,
                             fg=ACCENT, bg=BG2, bd=1, relief="flat", pady=10, padx=20)
        opts.pack(fill="x", padx=24, pady=(12, 4))

        self._var_speech     = tk.BooleanVar(value=True)
        self._var_pitch      = tk.BooleanVar(value=True)
        self._var_atm        = tk.BooleanVar(value=True)
        self._var_virtualcam = tk.BooleanVar(value=False)
        self._var_midi       = tk.BooleanVar(value=False)
        self._var_mirror     = tk.BooleanVar(value=True)
        self._var_preview    = tk.BooleanVar(value=True)

        checks = [
            (self._var_speech,     "🎙  Speech recognition  (letters + animals)",  True),
            (self._var_pitch,      "🎵  Pitch detection  (voice → colour effects)", True),
            (self._var_atm,        "🌌  Atmospheric overlay effects",               True),
            (self._var_virtualcam, "📷  Virtual camera output  (for TouchDesigner)", False),
            (self._var_midi,       "🎹  MIDI output  (pitch + gesture control)",    False),
            (self._var_mirror,     "🪞  Mirror webcam",                             True),
            (self._var_preview,    "🖥  Show preview window",                       True),
        ]
        for var, label, default in checks:
            cb = tk.Checkbutton(
                opts, text=label, variable=var,
                fg=TEXT, bg=BG2, selectcolor=BG,
                activeforeground=ACCENT, activebackground=BG2,
                font=FONT_SM, anchor="w",
            )
            cb.pack(fill="x", pady=1)

        # Highlight style
        style_row = tk.Frame(opts, bg=BG2)
        style_row.pack(fill="x", pady=(6, 0))
        tk.Label(style_row, text="🎨  Highlight style:", font=FONT_SM,
                 fg=TEXT, bg=BG2).pack(side="left")
        self._style_var = tk.StringVar(value="glow")
        style_menu = ttk.Combobox(
            style_row, textvariable=self._style_var,
            values=["glow", "rim", "aura", "tint"],
            state="readonly", width=8, font=FONT_SM,
        )
        style_menu.pack(side="left", padx=8)

        # ── Status bar
        status_frame = tk.Frame(self, bg=BG2, pady=6)
        status_frame.pack(fill="x", padx=24, pady=(4, 0))
        self._status_var = tk.StringVar(value="Ready")
        self._status_lbl = tk.Label(
            status_frame, textvariable=self._status_var,
            font=FONT_SM, fg=GREEN, bg=BG2, anchor="w",
        )
        self._status_lbl.pack(fill="x", padx=8)

        # ── Log box
        log_frame = tk.Frame(self, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=24, pady=4)
        self._log = tk.Text(
            log_frame, height=7, bg=BG2, fg=DIM,
            font=FONT_SM, relief="flat", state="disabled",
            insertbackground=ACCENT,
        )
        scrollbar = tk.Scrollbar(log_frame, command=self._log.yview)
        self._log.configure(yscrollcommand=scrollbar.set)
        self._log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ── Buttons
        btn_frame = tk.Frame(self, bg=BG, pady=12)
        btn_frame.pack(fill="x", padx=24)

        self._launch_btn = tk.Button(
            btn_frame, text="▶  LAUNCH", font=FONT_BTN,
            bg=ACCENT2, fg="white", activebackground=ACCENT,
            relief="flat", padx=24, pady=8, cursor="hand2",
            command=self._launch,
        )
        self._launch_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = tk.Button(
            btn_frame, text="■  STOP", font=FONT_BTN,
            bg=RED, fg="white", activebackground="#ff6060",
            relief="flat", padx=16, pady=8, cursor="hand2",
            state="disabled", command=self._stop,
        )
        self._stop_btn.pack(side="left", padx=(0, 8))

        tk.Button(
            btn_frame, text="⚙  RUN SETUP", font=FONT_BTN,
            bg=BG2, fg=DIM, activebackground=BG,
            relief="flat", padx=12, pady=8, cursor="hand2",
            command=self._run_setup,
        ).pack(side="right")

    # ── Installation check ────────────────────────────────────────────────────

    def _check_installation(self) -> None:
        if not _PYTHON.exists():
            self._set_status("⚠  Not installed — click 'RUN SETUP' first", RED)
            self._launch_btn.config(state="disabled")
            self._log_write("Hand Galaxy is not set up yet.\n"
                            "Click 'RUN SETUP' to install.\n")
            return

        self._log_write(f"✓ Python venv found: {_PYTHON}\n")

        core_modules = {
            "mediapipe": "mediapipe",
            "opencv": "cv2",
            "python-osc": "pythonosc",
            "numpy": "numpy",
        }
        missing = [
            label for label, module_name in core_modules.items()
            if not _venv_can_import(module_name)
        ]

        model_ok = (_PROJECT_ROOT / "models" / "hand_landmarker.task").exists()
        vosk_ok  = (_PROJECT_ROOT / "models" / "vosk" /
                    "vosk-model-small-en-us-0.15").exists()
        pya_ok   = _venv_can_import("pyaudio")
        aubio_ok = _venv_can_import("aubio")
        vcam_ok  = _venv_can_import("pyvirtualcam")
        midi_ok  = _venv_can_import("mido")
        midi_backend_ok = _venv_can_import("rtmidi")

        self._log_write(f"  Core packages: {'✓' if not missing else '✗ missing: ' + ', '.join(missing)}\n")
        self._log_write(f"  Hand model:    {'✓' if model_ok else '↻ will auto-download on first run'}\n")
        self._log_write(f"  Vosk model:    {'✓' if vosk_ok else '✗ missing (speech disabled until setup downloads it)'}\n")
        if pya_ok and aubio_ok:
            self._log_write("  Pitch backend: ✓ aubio high-precision mode\n")
        elif pya_ok:
            self._log_write("  Pitch backend: ✓ numpy fallback (aubio optional)\n")
        else:
            self._log_write("  Pitch backend: ✗ microphone bridge missing\n")
        self._log_write(f"  Virtual cam:   {'✓ optional package installed' if vcam_ok else '○ optional package not installed'}\n")
        self._log_write(f"  MIDI output:   {'✓ backend ready' if midi_ok and midi_backend_ok else '○ optional backend not installed'}\n")

        if missing:
            self._set_status("⚠  Incomplete install — run setup again", RED)
            self._launch_btn.config(state="disabled")
        else:
            self._set_status("Ready to launch", GREEN)

    # ── Launch ────────────────────────────────────────────────────────────────

    def _build_args(self) -> list[str]:
        args: list[str] = []
        if not self._var_speech.get():
            args += ["--no-speech"]
        if not self._var_pitch.get():
            args += ["--no-pitch"]
        if not self._var_atm.get():
            args += ["--no-atmosphere"]
        if self._var_virtualcam.get():
            args += ["--virtual-cam"]
        if self._var_midi.get():
            args += ["--midi"]
        if not self._var_mirror.get():
            args += ["--no-mirror"]
        if not self._var_preview.get():
            args += ["--no-preview"]
        args += ["--highlight-style", self._style_var.get()]
        return args

    def _launch(self) -> None:
        if self._running:
            return

        if not _PYTHON.exists():
            messagebox.showerror(
                "Not Installed",
                "Hand Galaxy is not installed.\nClick 'RUN SETUP' first.",
            )
            return

        if self._var_virtualcam.get() and not _venv_can_import("pyvirtualcam"):
            messagebox.showerror(
                "Virtual Camera Not Installed",
                "The optional pyvirtualcam package is not installed in .venv.\n"
                "Run setup again, or install requirements-virtualcam.txt into the venv first.",
            )
            return
        if self._var_midi.get() and not (_venv_can_import("mido") and _venv_can_import("rtmidi")):
            messagebox.showerror(
                "MIDI Backend Not Installed",
                "MIDI output needs mido plus a backend such as python-rtmidi.\n"
                "Run setup again, or install python-rtmidi into the venv first.",
            )
            return

        args = self._build_args()

        pya_ok = _venv_can_import("pyaudio")
        aubio_ok = _venv_can_import("aubio")
        vosk_pkg_ok = _venv_can_import("vosk")
        vosk_model_ok = (_PROJECT_ROOT / "models" / "vosk" / "vosk-model-small-en-us-0.15").exists()

        if self._var_speech.get() and not (pya_ok and vosk_pkg_ok and vosk_model_ok):
            self._log_write("[INFO] Speech dependencies missing; launching with --no-speech\n")
            if "--no-speech" not in args:
                args.append("--no-speech")

        if self._var_pitch.get() and pya_ok and not aubio_ok:
            self._log_write("[INFO] aubio not installed; using built-in numpy pitch fallback\n")

        if self._var_pitch.get() and not pya_ok:
            self._log_write("[INFO] Microphone dependency missing; launching with --no-pitch\n")
            if "--no-pitch" not in args:
                args.append("--no-pitch")

        args = [str(_PYTHON), "-m", "hand_galaxy.main"] + args
        env  = os.environ.copy()
        env["PYTHONPATH"] = str(_SRC_PATH)

        self._log_write(f"\n▶ Starting: {' '.join(args)}\n")

        try:
            self._process = subprocess.Popen(
                args, env=env, cwd=str(_PROJECT_ROOT),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
        except Exception as exc:
            messagebox.showerror("Launch Error", str(exc))
            return

        self._running = True
        self._launch_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._set_status("▶  Running…", ACCENT)

        threading.Thread(target=self._read_output, daemon=True).start()
        threading.Thread(target=self._wait_process, daemon=True).start()

    def _read_output(self) -> None:
        if not self._process or not self._process.stdout:
            return
        for line in self._process.stdout:
            self._log_write(line)

    def _wait_process(self) -> None:
        if not self._process:
            return
        self._process.wait()
        self._running = False
        self.after(0, self._on_process_done)

    def _on_process_done(self) -> None:
        code = self._process.returncode if self._process else -1
        self._launch_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        colour = GREEN if code == 0 else RED
        self._set_status(f"Stopped (exit code {code})", colour)
        self._log_write(f"\n■ Process exited with code {code}\n")

    def _stop(self) -> None:
        if self._process and self._running:
            self._process.terminate()
            self._log_write("\n■ Stop requested.\n")

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _run_setup(self) -> None:
        setup_bat = _PROJECT_ROOT / "setup.bat"
        if setup_bat.exists():
            subprocess.Popen(
                ["cmd", "/c", "start", "", str(setup_bat)],
                cwd=str(_PROJECT_ROOT),
            )
            self._log_write("\n⚙ Launched setup.bat in a new window.\n")
        else:
            messagebox.showerror("Not Found", f"setup.bat not found at {setup_bat}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, text: str, colour: str = GREEN) -> None:
        self._status_var.set(text)
        self._status_lbl.config(fg=colour)

    def _log_write(self, text: str) -> None:
        self._log.config(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.config(state="disabled")

    def _on_close(self) -> None:
        if self._running:
            if messagebox.askyesno("Quit", "Hand Galaxy is running. Stop and quit?"):
                self._stop()
        self.destroy()


# ── entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = LauncherApp()
    app.mainloop()
