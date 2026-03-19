"""
setup_wizard.py
---------------
Hand Galaxy v2.1 — Comprehensive Windows Setup Wizard.

Compiles to a single HandGalaxySetup.exe via PyInstaller.
Runs entirely from Python's standard library — tkinter, urllib, zipfile, subprocess.

Pages:
  0  Welcome
  1  Licence / info
  2  Install path selection
  3  Component selection
  4  Python detection / install
  5  Installation progress (venv, pip, models)
  6  Finish

Also handles:
  - Registering an uninstaller in Windows Add/Remove Programs
  - Start Menu shortcut creation
  - Desktop shortcut creation
  - Writing an uninstall.bat companion
  - Graceful resume if partially installed
"""
from __future__ import annotations

import ctypes
import json
import os
import pathlib
import platform
import queue
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import urllib.request
import zipfile
from typing import Callable, Optional

# ── Tkinter (stdlib) ──────────────────────────────────────────────────────────
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ── Constants ─────────────────────────────────────────────────────────────────
APP_NAME    = "Hand Galaxy"
APP_VER     = "2.1.3"
APP_SLUG    = "HandGalaxy"
PUBLISHER   = "Hand Galaxy Project"
HELP_URL    = "https://github.com/hand-galaxy"
UPDATE_URL  = "https://github.com/hand-galaxy"

# Default install root — user's home / Hand Galaxy
DEFAULT_INSTALL = pathlib.Path.home() / "Hand Galaxy"

# URLs
PYTHON_WIN64_URL = (
    "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
)
MEDIAPIPE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
VOSK_MODEL_URL = (
    "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
)

# Minimum Python version
MIN_PY = (3, 10)
MAX_PY = (3, 12)

# ── Palette ───────────────────────────────────────────────────────────────────
BG         = "#0b0b14"
BG2        = "#13131f"
BG3        = "#1a1a28"
ACCENT     = "#3de0c8"
ACCENT2    = "#7b5cff"
TEXT       = "#d4d4e8"
DIM        = "#55556a"
RED        = "#e05050"
GREEN      = "#40d490"
ORANGE     = "#e09040"
WHITE      = "#f0f0f8"
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SUB   = ("Segoe UI", 11)
FONT_BODY  = ("Consolas", 10)
FONT_BTN   = ("Segoe UI", 11, "bold")
FONT_SMALL = ("Consolas", 9)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_windows() -> bool:
    return platform.system() == "Windows"


def _is_admin() -> bool:
    if not _is_windows():
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def _find_python() -> Optional[str]:
    """Find a Python executable that meets the supported range."""
    candidates = [
        ["py", "-3.12"],
        ["py", "-3.11"],
        ["py", "-3.10"],
        ["python"],
        ["python3"],
    ]
    for cmd in candidates:
        try:
            result = subprocess.run(
                [*cmd, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            ver_str = result.stdout.strip() or result.stderr.strip()
            parts = ver_str.replace("Python ", "").split(".")
            major, minor = int(parts[0]), int(parts[1])
            if (major, minor) >= MIN_PY and (major, minor) <= MAX_PY:
                return " ".join(cmd)
        except Exception:
            continue
    return None


def _python_version_str(exe: str) -> str:
    try:
        cmd = exe.split() if isinstance(exe, str) else [exe]
        r = subprocess.run([*cmd, "--version"], capture_output=True, text=True, timeout=5)
        return (r.stdout or r.stderr).strip()
    except Exception:
        return "unknown"


def _disk_free_gb(path: pathlib.Path) -> float:
    try:
        stat = shutil.disk_usage(path.anchor)
        return stat.free / 1e9
    except Exception:
        return 99.0


# ── Download helpers ──────────────────────────────────────────────────────────

class DownloadError(Exception):
    pass


def _download(url: str, dest: pathlib.Path,
              progress_cb: Callable[[int, int], None] | None = None) -> None:
    """Download ``url`` to ``dest``, calling progress_cb(bytes_done, total)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.urlopen(url, timeout=60)
    except Exception as exc:
        raise DownloadError(f"Cannot reach {url}: {exc}") from exc

    total = int(req.getheader("Content-Length", 0) or 0)
    done  = 0
    chunk = 65_536

    with open(dest, "wb") as fh:
        while True:
            data = req.read(chunk)
            if not data:
                break
            fh.write(data)
            done += len(data)
            if progress_cb:
                progress_cb(done, total)

    req.close()


# ── Windows registry / shortcuts ─────────────────────────────────────────────

def _write_uninstall_registry(install_dir: pathlib.Path, uninstall_cmd: str) -> None:
    if not _is_windows():
        return
    try:
        import winreg
        key_path = (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\HandGalaxy"
        )
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValueEx(key, "DisplayName",         0, winreg.REG_SZ, f"{APP_NAME} {APP_VER}")
        winreg.SetValueEx(key, "DisplayVersion",      0, winreg.REG_SZ, APP_VER)
        winreg.SetValueEx(key, "Publisher",           0, winreg.REG_SZ, PUBLISHER)
        winreg.SetValueEx(key, "InstallLocation",     0, winreg.REG_SZ, str(install_dir))
        winreg.SetValueEx(key, "UninstallString",     0, winreg.REG_SZ, uninstall_cmd)
        winreg.SetValueEx(key, "NoModify",            0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair",            0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "URLInfoAbout",        0, winreg.REG_SZ, HELP_URL)
        winreg.CloseKey(key)
    except Exception:
        pass


def _remove_uninstall_registry() -> None:
    if not _is_windows():
        return
    try:
        import winreg
        winreg.DeleteKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\HandGalaxy",
        )
    except Exception:
        pass


def _create_shortcut_win(target: str, link_path: str,
                          description: str = "", work_dir: str = "") -> None:
    """Create a .lnk shortcut via PowerShell (no win32com needed)."""
    if not _is_windows():
        return
    ps = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$sc = $ws.CreateShortcut("{link_path}"); '
        f'$sc.TargetPath = "{target}"; '
        f'$sc.Description = "{description}"; '
        f'$sc.WorkingDirectory = "{work_dir}"; '
        f'$sc.Save()'
    )
    subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True,
    )


def _start_menu_dir() -> Optional[pathlib.Path]:
    if not _is_windows():
        return None
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        )
        path, _ = winreg.QueryValueEx(key, "Programs")
        winreg.CloseKey(key)
        return pathlib.Path(path) / APP_NAME
    except Exception:
        return pathlib.Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs" / APP_NAME


def _desktop_dir() -> pathlib.Path:
    if _is_windows():
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            path, _ = winreg.QueryValueEx(key, "Desktop")
            winreg.CloseKey(key)
            return pathlib.Path(path)
        except Exception:
            pass
    return pathlib.Path.home() / "Desktop"


# ── State object shared across wizard pages ───────────────────────────────────

class SetupState:
    install_dir:     pathlib.Path = DEFAULT_INSTALL
    python_exe:      str          = "python"
    comp_speech:     bool         = True
    comp_pitch:      bool         = True
    comp_atmosphere: bool         = True
    create_desktop:  bool         = True
    create_startmenu: bool        = True
    launch_after:    bool         = True
    status_msgs:     list[str]    = []
    error:           Optional[str] = None
    python_installed_by_us: bool  = False


# ── Base page ─────────────────────────────────────────────────────────────────

class Page(tk.Frame):
    def __init__(self, master, state: SetupState):
        super().__init__(master, bg=BG)
        self.state = state

    def on_enter(self) -> None:
        """Called when this page becomes active."""

    def on_leave(self) -> bool:
        """Called before leaving. Return False to block navigation."""
        return True

    def _label(self, parent, text, font=FONT_BODY, fg=TEXT, **kw) -> tk.Label:
        return tk.Label(parent, text=text, font=font, fg=fg, bg=BG, **kw)

    def _separator(self, parent) -> ttk.Separator:
        sep = ttk.Separator(parent, orient="horizontal")
        sep.pack(fill="x", pady=6)
        return sep


# ── Page 0 — Welcome ─────────────────────────────────────────────────────────

class WelcomePage(Page):
    def __init__(self, master, state):
        super().__init__(master, state)
        self._build()

    def _build(self):
        # Banner
        banner = tk.Frame(self, bg=ACCENT2, height=4)
        banner.pack(fill="x")

        body = tk.Frame(self, bg=BG, padx=40, pady=30)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="✦  HAND  GALAXY", font=("Segoe UI", 28, "bold"),
                 fg=ACCENT, bg=BG).pack(anchor="w")
        tk.Label(body, text=f"v{APP_VER} — Setup Wizard",
                 font=FONT_SUB, fg=DIM, bg=BG).pack(anchor="w", pady=(2, 20))

        intro = (
            "Welcome to the Hand Galaxy Setup Wizard.\n\n"
            "This wizard will install Hand Galaxy on your computer. "
            "Hand Galaxy combines real-time hand tracking, live speech "
            "recognition, and pitch-driven atmospheric effects.\n\n"
            "The setup will:\n"
            "   ✦  Verify or install Python 3.10+\n"
            "   ✦  Create an isolated Python virtual environment\n"
            "   ✦  Install MediaPipe, OpenCV, Vosk, audio bridge, and optional aubio\n"
            "   ✦  Download the hand landmark model (~9 MB)\n"
            "   ✦  Download the Vosk speech model (~40 MB)\n"
            "   ✦  Create Desktop and Start Menu shortcuts\n"
            "   ✦  Register the uninstaller\n\n"
            "Click Next to continue."
        )
        tk.Label(body, text=intro, font=FONT_SUB, fg=TEXT, bg=BG,
                 justify="left", wraplength=500).pack(anchor="w")

        # Disk space note
        free = _disk_free_gb(DEFAULT_INSTALL)
        colour = GREEN if free > 0.8 else RED
        tk.Label(body, text=f"Free disk space: {free:.1f} GB  (1 GB recommended)",
                 font=FONT_SMALL, fg=colour, bg=BG).pack(anchor="w", pady=(16, 0))


# ── Page 1 — Install path ─────────────────────────────────────────────────────

class InstallPathPage(Page):
    def __init__(self, master, state):
        super().__init__(master, state)
        self._path_var = tk.StringVar(value=str(state.install_dir))
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=BG, padx=40, pady=30)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Installation Folder",
                 font=("Segoe UI", 16, "bold"), fg=ACCENT, bg=BG).pack(anchor="w")
        tk.Label(body, text="Choose where Hand Galaxy will be installed.",
                 font=FONT_SUB, fg=DIM, bg=BG).pack(anchor="w", pady=(4, 20))

        # Path entry row
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x")
        tk.Label(row, text="Install to:", font=FONT_SUB, fg=TEXT, bg=BG,
                 width=10, anchor="w").pack(side="left")
        entry = tk.Entry(row, textvariable=self._path_var,
                         font=FONT_BODY, bg=BG3, fg=WHITE,
                         insertbackground=ACCENT, relief="flat",
                         highlightbackground=DIM, highlightthickness=1,
                         width=42)
        entry.pack(side="left", padx=(6, 6))
        tk.Button(row, text="Browse…", font=FONT_BODY,
                  bg=BG3, fg=TEXT, activebackground=BG2,
                  relief="flat", padx=10, cursor="hand2",
                  command=self._browse).pack(side="left")

        # Disk info
        self._disk_lbl = tk.Label(body, text="", font=FONT_SMALL, fg=DIM, bg=BG)
        self._disk_lbl.pack(anchor="w", pady=(8, 0))
        self._path_var.trace_add("write", self._update_disk)
        self._update_disk()

        # What goes here
        info = (
            "The following will be created inside this folder:\n\n"
            "    .venv/          Python virtual environment\n"
            "    models/         MediaPipe + Vosk model files\n"
            "    assets/         Animal and letter image assets\n"
            "    src/            Hand Galaxy Python source\n"
            "    touchdesigner/  TouchDesigner integration docs\n"
            "    Launcher.bat    Quick-launch shortcut\n"
            "    Uninstall.bat   Remove Hand Galaxy\n"
        )
        tk.Label(body, text=info, font=FONT_SMALL, fg=DIM, bg=BG,
                 justify="left").pack(anchor="w", pady=(20, 0))

    def _browse(self):
        chosen = filedialog.askdirectory(
            title="Choose install folder",
            initialdir=self._path_var.get(),
        )
        if chosen:
            self._path_var.set(chosen)

    def _update_disk(self, *_):
        try:
            p = pathlib.Path(self._path_var.get())
            free = _disk_free_gb(p)
            colour = GREEN if free > 0.8 else ORANGE if free > 0.3 else RED
            self._disk_lbl.config(
                text=f"Free space on drive: {free:.1f} GB", fg=colour,
            )
        except Exception:
            self._disk_lbl.config(text="", fg=DIM)

    def on_leave(self) -> bool:
        raw = self._path_var.get().strip()
        if not raw:
            messagebox.showerror("Invalid Path", "Please choose an installation folder.")
            return False
        self.state.install_dir = pathlib.Path(raw)
        return True


# ── Page 2 — Component selection ─────────────────────────────────────────────

class ComponentsPage(Page):
    def __init__(self, master, state):
        super().__init__(master, state)
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=BG, padx=40, pady=30)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Select Components",
                 font=("Segoe UI", 16, "bold"), fg=ACCENT, bg=BG).pack(anchor="w")
        tk.Label(body,
                 text="Choose which features to install.\n"
                      "Core hand tracking is always installed.",
                 font=FONT_SUB, fg=DIM, bg=BG).pack(anchor="w", pady=(4, 16))

        self._vars = {}
        components = [
            ("core",       "Core Hand Tracking",           True,  True,
             "MediaPipe hand tracking, OSC bridge, finger counter, TouchDesigner integration. Always required."),
            ("speech",     "Speech Recognition",           True,  False,
             "Vosk + pyaudio: live microphone input, letter detection (A-Z), and animal/insect keyword detection. Downloads 40 MB model."),
            ("pitch",      "Pitch Detection + Atmospheres",True,  False,
             "aubio YIN with built-in numpy fallback: real-time voice pitch drives colour, fog, aurora, corona bloom, and crystal sparkle effects."),
            ("assets",     "Sample Assets Folder",         True,  False,
             "Creates the animals/ image folder with README. Drop your own PNG/JPG images here after install."),
            ("shortcuts",  "Desktop Shortcut",             True,  False,
             "Adds a Hand Galaxy shortcut to your Desktop."),
            ("startmenu",  "Start Menu Shortcuts",         True,  False,
             "Adds Hand Galaxy, TouchDesigner Setup Guide, and Uninstall to the Start Menu."),
        ]

        for key, label, default, locked, desc in components:
            frame = tk.Frame(body, bg=BG2, pady=6, padx=12)
            frame.pack(fill="x", pady=2)

            var = tk.BooleanVar(value=default)
            self._vars[key] = var

            cb = tk.Checkbutton(
                frame, text=label, variable=var,
                fg=WHITE if not locked else DIM,
                bg=BG2, selectcolor=BG,
                activeforeground=ACCENT, activebackground=BG2,
                font=("Segoe UI", 11, "bold"),
                anchor="w",
                state="disabled" if locked else "normal",
            )
            cb.pack(anchor="w")
            tk.Label(frame, text=desc, font=FONT_SMALL, fg=DIM,
                     bg=BG2, wraplength=520, justify="left").pack(anchor="w", padx=(20, 0))

        # Shortcut options
        self._var_desktop   = self._vars["shortcuts"]
        self._var_startmenu = self._vars["startmenu"]
        self._var_speech    = self._vars["speech"]
        self._var_pitch     = self._vars["pitch"]

    def on_leave(self) -> bool:
        self.state.comp_speech     = self._var_speech.get()
        self.state.comp_pitch      = self._var_pitch.get()
        self.state.comp_atmosphere = self._var_pitch.get()
        self.state.create_desktop  = self._var_desktop.get()
        self.state.create_startmenu = self._var_startmenu.get()
        return True


# ── Page 3 — Python check ─────────────────────────────────────────────────────

class PythonCheckPage(Page):
    def __init__(self, master, state):
        super().__init__(master, state)
        self._result_var = tk.StringVar(value="Checking…")
        self._python_var = tk.StringVar(value="")
        self._install_var = tk.BooleanVar(value=False)
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=BG, padx=40, pady=30)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Python Environment",
                 font=("Segoe UI", 16, "bold"), fg=ACCENT, bg=BG).pack(anchor="w")
        tk.Label(body, text="Hand Galaxy currently supports Python 3.10 to 3.12.",
                 font=FONT_SUB, fg=DIM, bg=BG).pack(anchor="w", pady=(4, 20))

        self._result_lbl = tk.Label(body, textvariable=self._result_var,
                                    font=("Segoe UI", 12, "bold"),
                                    fg=ORANGE, bg=BG)
        self._result_lbl.pack(anchor="w")

        self._ver_lbl = tk.Label(body, textvariable=self._python_var,
                                  font=FONT_BODY, fg=DIM, bg=BG)
        self._ver_lbl.pack(anchor="w", pady=(4, 16))

        # Auto-install checkbox (only shown if Python not found)
        self._install_frame = tk.Frame(body, bg=BG2, pady=10, padx=16)
        self._install_frame.pack(fill="x")
        tk.Label(self._install_frame,
                 text="Compatible Python (3.10-3.12) not found on your system.",
                 font=("Segoe UI", 11), fg=ORANGE, bg=BG2).pack(anchor="w")
        tk.Label(self._install_frame,
                 text="The installer can download and install Python 3.11.9 automatically.\n"
                      "This requires an internet connection and approximately 25 MB.\n"
                      "Python will be installed for your current user only (no admin required).",
                 font=FONT_SMALL, fg=DIM, bg=BG2,
                 justify="left").pack(anchor="w", pady=(4, 8))
        tk.Checkbutton(
            self._install_frame,
            text="Download and install Python 3.11.9 automatically",
            variable=self._install_var,
            fg=TEXT, bg=BG2, selectcolor=BG,
            activeforeground=ACCENT, activebackground=BG2,
            font=("Segoe UI", 11),
        ).pack(anchor="w")
        self._install_frame.pack_forget()  # hidden until needed

        notes = (
            "If you already have Python 3.10+ but it is not in PATH,\n"
            "add it to PATH and re-run the installer."
        )
        tk.Label(body, text=notes, font=FONT_SMALL, fg=DIM, bg=BG,
                 justify="left").pack(anchor="w", pady=(20, 0))

    def on_enter(self) -> None:
        self._check_python()

    def _check_python(self) -> None:
        exe = _find_python()
        if exe:
            ver = _python_version_str(exe)
            self.state.python_exe = exe
            self._result_var.set(f"✓  Python found")
            self._python_var.set(f"{ver}  ({exe})")
            self._result_lbl.config(fg=GREEN)
            self._install_frame.pack_forget()
        else:
            self._result_var.set("✗  Compatible Python 3.10-3.12 not found in PATH")
            self._python_var.set("")
            self._result_lbl.config(fg=RED)
            self._install_frame.pack(fill="x")

    def on_leave(self) -> bool:
        if _find_python() is None and not self._install_var.get():
            if not messagebox.askyesno(
                "Python Required",
                "Python 3.10+ was not found.\n\n"
                "You can install it manually from https://python.org, "
                "then re-run this installer.\n\n"
                "Proceed anyway (install may fail)?",
            ):
                return False
        self.state.python_installed_by_us = self._install_var.get()
        return True


# ── Page 4 — Confirm ─────────────────────────────────────────────────────────

class ConfirmPage(Page):
    def __init__(self, master, state):
        super().__init__(master, state)
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=BG, padx=40, pady=30)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Ready to Install",
                 font=("Segoe UI", 16, "bold"), fg=ACCENT, bg=BG).pack(anchor="w")
        tk.Label(body, text="Review your choices and click Install to begin.",
                 font=FONT_SUB, fg=DIM, bg=BG).pack(anchor="w", pady=(4, 16))

        self._summary = tk.Text(body, height=14, bg=BG3, fg=TEXT,
                                font=FONT_BODY, relief="flat",
                                state="disabled", wrap="word",
                                padx=12, pady=8)
        self._summary.pack(fill="both", expand=True)

    def on_enter(self) -> None:
        s = self.state
        comps = []
        if s.comp_speech:     comps.append("Speech Recognition (Vosk + pyaudio)")
        if s.comp_pitch:      comps.append("Pitch Detection (aubio or numpy fallback) + Atmospheric Effects")
        if s.create_desktop:  comps.append("Desktop shortcut")
        if s.create_startmenu: comps.append("Start Menu shortcuts")

        lines = [
            f"Install folder:  {s.install_dir}",
            f"Python:          {_python_version_str(s.python_exe)}",
            "",
            "Components:",
            "  ✦  Core hand tracking (always)",
        ]
        for c in comps:
            lines.append(f"  ✦  {c}")

        lines += [
            "",
            "Downloads during install:",
            "  ✦  MediaPipe hand landmark model  (~9 MB)",
        ]
        if s.comp_speech:
            lines.append("  ✦  Vosk speech model              (~40 MB)")
        lines += [
            "",
            "Click Install to begin.",
        ]

        self._summary.config(state="normal")
        self._summary.delete("1.0", "end")
        self._summary.insert("end", "\n".join(lines))
        self._summary.config(state="disabled")


# ── Page 5 — Install progress ────────────────────────────────────────────────

class InstallPage(Page):
    def __init__(self, master, state):
        super().__init__(master, state)
        self._q: queue.Queue = queue.Queue()
        self._done  = False
        self._error = False
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=BG, padx=40, pady=20)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Installing Hand Galaxy…",
                 font=("Segoe UI", 16, "bold"), fg=ACCENT, bg=BG).pack(anchor="w")

        self._step_lbl = tk.Label(body, text="Starting…",
                                   font=FONT_SUB, fg=DIM, bg=BG)
        self._step_lbl.pack(anchor="w", pady=(6, 4))

        # Overall progress
        self._overall_bar = ttk.Progressbar(body, orient="horizontal",
                                             length=560, mode="determinate",
                                             maximum=100)
        self._overall_bar.pack(fill="x", pady=(4, 2))
        self._overall_pct = tk.Label(body, text="0 %", font=FONT_SMALL,
                                      fg=DIM, bg=BG)
        self._overall_pct.pack(anchor="e")

        # Sub-task progress
        tk.Label(body, text="Current task:", font=FONT_SMALL, fg=DIM, bg=BG).pack(anchor="w", pady=(4, 0))
        self._sub_bar = ttk.Progressbar(body, orient="horizontal",
                                         length=560, mode="determinate",
                                         maximum=100)
        self._sub_bar.pack(fill="x", pady=(2, 8))

        # Log box
        log_frame = tk.Frame(body, bg=BG)
        log_frame.pack(fill="both", expand=True)
        self._log_text = tk.Text(log_frame, height=10, bg=BG3, fg=TEXT,
                             font=FONT_SMALL, relief="flat",
                             state="disabled", wrap="word",
                             padx=8, pady=4)
        sb = tk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=sb.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def on_enter(self) -> None:
        if not self._done:
            threading.Thread(target=self._run_install, daemon=True).start()
            self._poll_queue()

    # ── Queue polling ────────────────────────────────────────────────────────

    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self._q.get_nowait()
                self._handle_msg(msg)
        except queue.Empty:
            pass
        if not self._done:
            self.after(80, self._poll_queue)

    def _handle_msg(self, msg: dict) -> None:
        kind = msg.get("kind")
        if kind == "log":
            self._log_write(msg["text"])
        elif kind == "step":
            self._step_lbl.config(text=msg["text"], fg=ACCENT)
            self._log_write(f"\n  ▶ {msg['text']}\n")
        elif kind == "overall":
            pct = int(msg["pct"])
            self._overall_bar["value"] = pct
            self._overall_pct.config(text=f"{pct} %")
        elif kind == "sub":
            pct = int(msg.get("pct", 0))
            self._sub_bar["value"] = pct
            if msg.get("mode") == "indeterminate":
                self._sub_bar.config(mode="indeterminate")
                self._sub_bar.start(12)
            else:
                self._sub_bar.stop()
                self._sub_bar.config(mode="determinate")
                self._sub_bar["value"] = pct
        elif kind == "done":
            self._done = True
            self._error = msg.get("error", False)
            self._step_lbl.config(
                text="Installation complete!" if not self._error else "Installation failed.",
                fg=GREEN if not self._error else RED,
            )
            self._overall_bar["value"] = 100 if not self._error else self._overall_bar["value"]
            self._overall_pct.config(text="100 %" if not self._error else "Error")
            self._sub_bar.stop()
            # Signal parent wizard
            self.event_generate("<<InstallDone>>")

    def _log_write(self, text: str) -> None:
        self._log_text.config(state="normal")
        self._log_text.insert("end", text)
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    # ── Worker thread ────────────────────────────────────────────────────────

    def _emit(self, kind: str, **kw) -> None:
        self._q.put({"kind": kind, **kw})

    def _log(self, text: str) -> None:
        self._emit("log", text=text + "\n")

    def _step(self, text: str, overall_pct: int) -> None:
        self._emit("step", text=text)
        self._emit("overall", pct=overall_pct)

    def _run_install(self) -> None:
        s = self.state
        try:
            self._do_install(s)
            self._emit("done", error=False)
        except Exception as exc:  # noqa: BLE001
            self._log(f"\n  [ERROR] {exc}")
            s.error = str(exc)
            self._emit("done", error=True)

    def _do_install(self, s: SetupState) -> None:  # noqa: C901
        install_dir = s.install_dir
        install_dir.mkdir(parents=True, exist_ok=True)

        # ── Step 1: Install Python if requested ───────────────────────────
        if s.python_installed_by_us:
            self._step("Downloading Python 3.11.9…", 2)
            py_installer = install_dir / "python_setup.exe"
            self._download_with_progress(PYTHON_WIN64_URL, py_installer, 2, 8)
            self._step("Installing Python 3.11.9 (user-level)…", 8)
            self._emit("sub", mode="indeterminate")
            result = subprocess.run(
                [str(py_installer), "/quiet", "InstallAllUsers=0",
                 "PrependPath=1", "Include_test=0"],
                capture_output=True, text=True,
            )
            self._emit("sub", pct=100)
            py_installer.unlink(missing_ok=True)
            if result.returncode != 0:
                raise RuntimeError(f"Python install failed (code {result.returncode})")
            # Re-locate python
            new_exe = _find_python()
            if new_exe:
                s.python_exe = new_exe
            self._log(f"  Python installed: {_python_version_str(s.python_exe)}\n")

        # ── Step 2: Copy source files ─────────────────────────────────────
        self._step("Copying Hand Galaxy source files…", 12)
        self._emit("sub", mode="indeterminate")
        src_root = self._source_root()
        for item in ["src", "assets", "touchdesigner", "requirements.txt",
                     "requirements-virtualcam.txt", "VERSION.txt"]:
            src_path = src_root / item
            if src_path.exists():
                dst_path = install_dir / item
                if src_path.is_dir():
                    if dst_path.exists():
                        shutil.rmtree(dst_path)
                    shutil.copytree(src_path, dst_path)
                else:
                    shutil.copy2(src_path, dst_path)
        self._emit("sub", pct=100)
        self._log("  Source files copied.\n")

        # ── Step 3: Create virtual environment ───────────────────────────
        self._step("Creating Python virtual environment…", 18)
        venv_dir = install_dir / ".venv"
        self._emit("sub", mode="indeterminate")
        if not venv_dir.exists():
            result = subprocess.run(
                [s.python_exe, "-m", "venv", str(venv_dir)],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"venv creation failed:\n{result.stderr}")
        pip_exe    = venv_dir / "Scripts" / "pip.exe"
        python_exe = venv_dir / "Scripts" / "python.exe"
        # Fallback for non-Windows
        if not pip_exe.exists():
            pip_exe    = venv_dir / "bin" / "pip"
            python_exe = venv_dir / "bin" / "python"
        self._emit("sub", pct=100)
        self._log(f"  venv: {venv_dir}\n")

        # ── Step 4: Upgrade pip ──────────────────────────────────────────
        self._step("Upgrading pip…", 22)
        self._emit("sub", mode="indeterminate")
        subprocess.run([str(python_exe), "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
                       capture_output=True)
        self._emit("sub", pct=100)

        # ── Step 5: Core dependencies ────────────────────────────────────
        self._step("Installing core dependencies (mediapipe, opencv, osc, numpy)…", 28)
        core_pkgs = ["mediapipe>=0.10.9", "opencv-python>=4.9.0",
                     "python-osc>=1.8.3", "numpy>=1.26.0"]
        self._pip_install(python_exe, core_pkgs, pct_start=28, pct_end=45)

        # ── Step 6: Speech ───────────────────────────────────────────────
        if s.comp_speech:
            self._step("Installing Vosk speech recognition…", 46)
            self._pip_install(python_exe, ["vosk>=0.3.45"], pct_start=46, pct_end=50)

            self._step("Installing PyAudio microphone bridge…", 50)
            try:
                self._pip_install(python_exe, ["pyaudio>=0.2.14"], pct_start=50, pct_end=54)
            except Exception:
                self._log("  Direct PyAudio install failed. Trying pipwin wheel helper…\n")
                try:
                    self._pip_install(python_exe, ["pipwin"], pct_start=50, pct_end=52)
                    result = subprocess.run([str(python_exe), "-m", "pipwin", "install", "pyaudio"], capture_output=True, text=True)
                    if result.returncode != 0:
                        raise RuntimeError(result.stderr or result.stdout or "pipwin failed")
                    self._emit("overall", pct=54)
                    self._emit("sub", pct=100)
                    self._log("  PyAudio installed via pipwin.\n")
                except Exception as exc:
                    self._log(f"  WARNING: PyAudio could not be installed: {exc}\n")
                    self._log("  Speech/pitch microphone features will be auto-disabled if needed.\n")
                    self._emit("overall", pct=54)

        # ── Step 7: Pitch ────────────────────────────────────────────────
        if s.comp_pitch:
            self._step("Installing optional aubio pitch backend…", 55)
            try:
                self._pip_install(python_exe, ["aubio>=0.4.9"], pct_start=55, pct_end=60)
            except Exception as exc:
                self._log(f"  WARNING: aubio could not be installed: {exc}\n")
                self._log("  Hand Galaxy will use the built-in numpy pitch fallback instead.\n")
                self._emit("overall", pct=60)

        # ── Step 7b: Optional virtual camera support ────────────────────
        self._step("Installing optional virtual camera support…", 60)
        try:
            self._pip_install(python_exe, ["pyvirtualcam==0.14.0"], pct_start=60, pct_end=61)
        except Exception as exc:  # noqa: BLE001
            self._log(f"  Optional virtual camera package skipped: {exc}\n")
            self._emit("overall", pct=61)

        # ── Step 8: Hand model ───────────────────────────────────────────
        self._step("Downloading MediaPipe hand landmark model (~9 MB)…", 61)
        model_path = install_dir / "models" / "hand_landmarker.task"
        if not model_path.exists():
            self._download_with_progress(MEDIAPIPE_MODEL_URL, model_path, 61, 68)
        else:
            self._log("  Hand model already present, skipping.\n")
            self._emit("overall", pct=68)

        # ── Step 9: Vosk model ───────────────────────────────────────────
        if s.comp_speech:
            vosk_dir = install_dir / "models" / "vosk" / "vosk-model-small-en-us-0.15"
            if not vosk_dir.exists():
                self._step("Downloading Vosk speech model (~40 MB)…", 69)
                zip_path = install_dir / "models" / "vosk" / "model.zip"
                self._download_with_progress(VOSK_MODEL_URL, zip_path, 69, 82)
                self._step("Extracting Vosk model…", 82)
                self._emit("sub", mode="indeterminate")
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(install_dir / "models" / "vosk")
                zip_path.unlink(missing_ok=True)
                self._emit("sub", pct=100)
                self._log("  Vosk model extracted.\n")
            else:
                self._log("  Vosk model already present, skipping.\n")
                self._emit("overall", pct=82)

        # ── Step 10: Write launcher batch files ──────────────────────────
        self._step("Writing launcher files…", 86)
        self._write_launchers(install_dir, python_exe)

        # ── Step 11: Shortcuts ───────────────────────────────────────────
        self._step("Creating shortcuts…", 90)
        launcher_bat    = install_dir / "Launcher.bat"
        launch_auto_bat = install_dir / "Launch-Auto.bat"
        launch_bat      = install_dir / "Launch.bat"
        shortcut_target = (
            launcher_bat if launcher_bat.exists() else
            launch_auto_bat if launch_auto_bat.exists() else
            launch_bat
        )
        if s.create_desktop:
            dst = _desktop_dir() / "Hand Galaxy.lnk"
            _create_shortcut_win(str(shortcut_target), str(dst),
                                 f"Hand Galaxy v{APP_VER}", str(install_dir))
            self._log(f"  Desktop shortcut: {dst}\n")

        if s.create_startmenu:
            sm_dir = _start_menu_dir()
            if sm_dir:
                sm_dir.mkdir(parents=True, exist_ok=True)
                _create_shortcut_win(
                    str(shortcut_target),
                    str(sm_dir / "Hand Galaxy.lnk"),
                    f"Hand Galaxy v{APP_VER}", str(install_dir),
                )
                _create_shortcut_win(
                    str(launcher_bat),
                    str(sm_dir / "Hand Galaxy Launcher (GUI).lnk"),
                    "Hand Galaxy GUI Launcher", str(install_dir),
                )
                _create_shortcut_win(
                    str(install_dir / "Uninstall.bat"),
                    str(sm_dir / "Uninstall Hand Galaxy.lnk"),
                    "Uninstall Hand Galaxy", str(install_dir),
                )
                self._log(f"  Start Menu: {sm_dir}\n")

        # ── Step 12: Uninstaller ─────────────────────────────────────────
        self._step("Registering uninstaller…", 93)
        uninstall_bat = install_dir / "Uninstall.bat"
        self._write_uninstaller(install_dir, uninstall_bat)
        _write_uninstall_registry(install_dir, str(uninstall_bat))
        self._log("  Uninstaller registered in Add/Remove Programs.\n")

        # ── Step 13: Write install receipt ──────────────────────────────
        self._step("Finalising…", 97)
        receipt = {
            "version":    APP_VER,
            "install_dir": str(install_dir),
            "python_exe":  str(python_exe),
            "speech":      s.comp_speech,
            "pitch":       s.comp_pitch,
        }
        (install_dir / "install_receipt.json").write_text(
            json.dumps(receipt, indent=2)
        )
        self._emit("overall", pct=100)
        self._log("\n  ✦  Installation complete!\n")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _source_root(self) -> pathlib.Path:
        """Return the directory where the source files live."""
        # When compiled: _MEIPASS is the PyInstaller temp dir
        if hasattr(sys, "_MEIPASS"):
            return pathlib.Path(sys._MEIPASS)
        # When running from source: two levels up from this file
        return pathlib.Path(__file__).resolve().parents[1]

    def _pip_install(self, python_exe: pathlib.Path,
                     packages: list[str],
                     pct_start: int, pct_end: int) -> None:
        self._emit("sub", mode="indeterminate")
        for i, pkg in enumerate(packages):
            self._log(f"    pip install {pkg}\n")
            result = subprocess.run(
                [str(python_exe), "-m", "pip", "install", pkg, "--quiet"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                self._log(f"    [WARN] {result.stderr.strip()}\n")
            pct = pct_start + int((i + 1) / len(packages) * (pct_end - pct_start))
            self._emit("overall", pct=pct)
        self._emit("sub", pct=100)

    def _download_with_progress(self, url: str, dest: pathlib.Path,
                                  pct_start: int, pct_end: int) -> None:
        self._emit("sub", pct=0)
        dest.parent.mkdir(parents=True, exist_ok=True)

        def _progress(done: int, total: int) -> None:
            if total > 0:
                frac = done / total
                sub_pct = int(frac * 100)
                overall_pct = pct_start + int(frac * (pct_end - pct_start))
                self._emit("sub", pct=sub_pct)
                self._emit("overall", pct=overall_pct)
                mb_done  = done  / 1e6
                mb_total = total / 1e6
                self._log(f"\r    {mb_done:.1f} / {mb_total:.1f} MB")
            else:
                self._emit("sub", mode="indeterminate")

        try:
            _download(url, dest, progress_cb=_progress)
        except DownloadError as exc:
            self._log(f"\n    [ERROR] Download failed: {exc}\n")
            raise
        self._emit("sub", pct=100)
        self._emit("overall", pct=pct_end)
        self._log(f"\n    Saved: {dest}\n")

    def _write_launchers(self, install_dir: pathlib.Path,
                          python_exe: pathlib.Path) -> None:
        src = str(install_dir / "src")

        def bat(filename: str, args: str, title: str) -> None:
            (install_dir / filename).write_text(
                f'@echo off\n'
                f'title {title}\n'
                f'cd /d "{install_dir}"\n'
                f'set PYTHONPATH={src}\n'
                f'"{python_exe}" -m hand_galaxy.main {args}\n'
                f'if errorlevel 1 pause\n'
            )

        bat("Launch.bat",            "",                                        f"Hand Galaxy v{APP_VER}")
        bat("Launch-NoSpeech.bat",   "--no-speech --no-pitch",                  "Hand Galaxy (Hands Only)")
        bat("Launch-NoPitch.bat",    "--no-pitch",                               "Hand Galaxy (No Pitch)")
        bat("Launch-VirtualCam.bat", "--virtual-cam",                            "Hand Galaxy (Virtual Cam)")
        bat("Launch-Minimal.bat",    "--no-speech --no-pitch --no-atmosphere",   "Hand Galaxy (Minimal)")

        helper_py = install_dir / "installer" / "launch_helper.py"
        if helper_py.exists():
            (install_dir / "Launch-Auto.bat").write_text(
                f'@echo off\n'
                f'title Hand Galaxy v{APP_VER} - Auto Safe\n'
                f'cd /d "{install_dir}"\n'
                f'set PYTHONPATH={src}\n'
                f'"{python_exe}" "{helper_py}" %*\n'
                f'if errorlevel 1 pause\n'
            )

        # GUI Launcher
        gui_py = install_dir / "installer" / "launcher_gui.py"
        if gui_py.exists():
            (install_dir / "Launcher.bat").write_text(
                f'@echo off\ntitle Hand Galaxy Launcher\n'
                f'cd /d "{install_dir}"\n'
                f'set PYTHONPATH={src}\n'
                f'"{python_exe}" "{gui_py}"\n'
            )

        self._log("  Launcher .bat files written.\n")

    def _write_uninstaller(self, install_dir: pathlib.Path,
                            uninstall_bat: pathlib.Path) -> None:
        uninstall_bat.write_text(
            '@echo off\n'
            f'title Uninstall {APP_NAME}\n'
            'echo.\n'
            f'echo  Uninstalling {APP_NAME} v{APP_VER}...\n'
            'echo.\n'
            'choice /M "Remove all Hand Galaxy files and shortcuts?"\n'
            'if errorlevel 2 goto cancel\n'
            '\n'
            ':: Remove registry entry\n'
            'reg delete "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\HandGalaxy" /f >nul 2>&1\n'
            '\n'
            ':: Remove Start Menu\n'
            'rmdir /s /q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Hand Galaxy" >nul 2>&1\n'
            '\n'
            ':: Remove Desktop shortcut\n'
            'del /q "%USERPROFILE%\\Desktop\\Hand Galaxy.lnk" >nul 2>&1\n'
            '\n'
            ':: Remove install directory (self-delete trick)\n'
            f'cd /d "%TEMP%"\n'
            f'rmdir /s /q "{install_dir}" >nul 2>&1\n'
            '\n'
            'echo  Hand Galaxy has been uninstalled.\n'
            'echo.\n'
            'pause\n'
            'goto end\n'
            ':cancel\n'
            'echo  Uninstall cancelled.\n'
            'pause\n'
            ':end\n'
        )


# ── Page 6 — Finish ───────────────────────────────────────────────────────────

class FinishPage(Page):
    def __init__(self, master, state):
        super().__init__(master, state)
        self._launch_var = tk.BooleanVar(value=True)
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=BG, padx=40, pady=30)
        body.pack(fill="both", expand=True)

        self._title_lbl = tk.Label(body, text="",
                                    font=("Segoe UI", 18, "bold"), bg=BG)
        self._title_lbl.pack(anchor="w")

        self._msg_lbl = tk.Label(body, text="",
                                  font=FONT_SUB, fg=DIM, bg=BG,
                                  wraplength=520, justify="left")
        self._msg_lbl.pack(anchor="w", pady=(8, 20))

        launch_frame = tk.Frame(body, bg=BG2, pady=12, padx=16)
        launch_frame.pack(fill="x")
        tk.Checkbutton(
            launch_frame,
            text="Launch Hand Galaxy now",
            variable=self._launch_var,
            fg=TEXT, bg=BG2, selectcolor=BG,
            activeforeground=ACCENT, activebackground=BG2,
            font=("Segoe UI", 11),
        ).pack(anchor="w")

        next_steps = (
            "Next steps:\n\n"
            "  1.  Drop animal images in:  assets\\animals\\\n"
            "      (cat.png, bee.png, butterfly.png, etc.)\n\n"
            "  2.  Open TouchDesigner and follow:\n"
            "      touchdesigner\\NETWORK_SETUP.md\n\n"
            "  3.  Use Launch.bat for quick start, or\n"
            "      Launcher.bat for the GUI with all options.\n"
        )
        tk.Label(body, text=next_steps, font=FONT_SMALL, fg=DIM, bg=BG,
                 justify="left").pack(anchor="w", pady=(20, 0))

    def on_enter(self) -> None:
        s = self.state
        if s.error:
            self._title_lbl.config(text="Installation Failed", fg=RED)
            self._msg_lbl.config(
                text=f"An error occurred during installation:\n\n{s.error}\n\n"
                     "Please check your internet connection and try again."
            )
            self._launch_var.set(False)
        else:
            self._title_lbl.config(
                text=f"✦  {APP_NAME} v{APP_VER} Installed!", fg=GREEN,
            )
            self._msg_lbl.config(
                text=f"Hand Galaxy has been installed to:\n{s.install_dir}"
            )

    @property
    def launch_after(self) -> bool:
        return self._launch_var.get()


# ── Main wizard window ────────────────────────────────────────────────────────

class SetupWizard(tk.Tk):
    PAGES = [
        WelcomePage,
        InstallPathPage,
        ComponentsPage,
        PythonCheckPage,
        ConfirmPage,
        InstallPage,
        FinishPage,
    ]
    NEXT_LABELS = {
        0: "Next  →",
        1: "Next  →",
        2: "Next  →",
        3: "Next  →",
        4: "Install",
        5: "Next  →",
        6: "Finish",
    }

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VER} — Setup Wizard")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("640x580")

        self._state    = SetupState()
        self._page_idx = 0
        self._pages: list[Page] = []

        self._build_chrome()
        self._init_pages()
        self._show_page(0)
        self._center_window()

    # ── Chrome ────────────────────────────────────────────────────────────────

    def _build_chrome(self):
        # Top bar
        top = tk.Frame(self, bg=ACCENT2, height=3)
        top.pack(fill="x", side="top")

        # Header strip
        header = tk.Frame(self, bg=BG2, pady=10, padx=20)
        header.pack(fill="x")
        self._header_title = tk.Label(
            header, text="", font=("Segoe UI", 13, "bold"),
            fg=WHITE, bg=BG2,
        )
        self._header_title.pack(side="left")
        tk.Label(header, text=f"v{APP_VER}", font=FONT_SMALL,
                 fg=DIM, bg=BG2).pack(side="right")

        # Page area
        self._page_area = tk.Frame(self, bg=BG)
        self._page_area.pack(fill="both", expand=True)

        # Bottom button bar
        btm = tk.Frame(self, bg=BG2, pady=10, padx=20)
        btm.pack(fill="x", side="bottom")

        self._cancel_btn = tk.Button(
            btm, text="Cancel", font=FONT_BTN,
            bg=BG3, fg=DIM, activebackground=BG,
            relief="flat", padx=16, pady=6, cursor="hand2",
            command=self._on_cancel,
        )
        self._cancel_btn.pack(side="left")

        self._back_btn = tk.Button(
            btm, text="←  Back", font=FONT_BTN,
            bg=BG3, fg=TEXT, activebackground=BG,
            relief="flat", padx=16, pady=6, cursor="hand2",
            command=self._go_back,
        )
        self._back_btn.pack(side="left", padx=8)

        self._next_btn = tk.Button(
            btm, text="Next  →", font=FONT_BTN,
            bg=ACCENT2, fg=WHITE, activebackground=ACCENT,
            relief="flat", padx=20, pady=6, cursor="hand2",
            command=self._go_next,
        )
        self._next_btn.pack(side="right")

        # Step indicator
        self._step_indicator = tk.Label(
            btm, text="", font=FONT_SMALL, fg=DIM, bg=BG2,
        )
        self._step_indicator.pack(side="right", padx=20)

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _init_pages(self):
        for PageClass in self.PAGES:
            page = PageClass(self._page_area, self._state)
            page.place(relwidth=1, relheight=1)
            self._pages.append(page)

        # Listen for install-done event from InstallPage
        self._pages[5].bind("<<InstallDone>>", self._on_install_done)

    def _show_page(self, idx: int):
        for i, page in enumerate(self._pages):
            if i == idx:
                page.lift()
                page.on_enter()
            else:
                page.lower()

        self._page_idx = idx
        titles = [
            "Welcome",
            "Installation Folder",
            "Select Components",
            "Python Environment",
            "Ready to Install",
            "Installing…",
            "Setup Complete",
        ]
        self._header_title.config(text=titles[idx])
        self._step_indicator.config(text=f"Step {idx + 1} of {len(self.PAGES)}")
        self._next_btn.config(text=self.NEXT_LABELS.get(idx, "Next →"))

        on_install = (idx == 5)
        self._back_btn.config(state="disabled" if idx == 0 or on_install else "normal")
        self._cancel_btn.config(state="disabled" if on_install else "normal")
        self._next_btn.config(state="disabled" if on_install else "normal")

    def _go_next(self):
        current = self._pages[self._page_idx]
        if not current.on_leave():
            return

        next_idx = self._page_idx + 1
        if next_idx >= len(self.PAGES):
            self._finish()
            return

        self._show_page(next_idx)

    def _go_back(self):
        if self._page_idx > 0:
            self._show_page(self._page_idx - 1)

    def _on_install_done(self, _event=None):
        self._next_btn.config(state="normal")
        self._cancel_btn.config(state="normal")

    def _finish(self):
        finish_page: FinishPage = self._pages[6]
        if finish_page.launch_after and not self._state.error:
            self._launch_app()
        self.destroy()

    def _launch_app(self):
        launch_bat = self._state.install_dir / "Launch.bat"
        if launch_bat.exists():
            subprocess.Popen(["cmd", "/c", str(launch_bat)],
                              cwd=str(self._state.install_dir))

    def _on_cancel(self):
        if messagebox.askyesno("Cancel Setup",
                               "Are you sure you want to cancel installation?"):
            self.destroy()

    def _center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")


# ── Entry ─────────────────────────────────────────────────────────────────────

def main():
    app = SetupWizard()
    app.mainloop()


if __name__ == "__main__":
    main()
