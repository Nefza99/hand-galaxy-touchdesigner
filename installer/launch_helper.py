from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / '.venv' / 'Scripts' / 'python.exe' if os.name == 'nt' else ROOT / '.venv' / 'bin' / 'python'
SRC = ROOT / 'src'

def can_import(mod: str) -> bool:
    try:
        r = subprocess.run([str(PYTHON), '-c', f'import {mod}'], cwd=str(ROOT), capture_output=True, text=True, timeout=12)
        return r.returncode == 0
    except Exception:
        return False

def main(argv: list[str]) -> int:
    args = list(argv)
    pya = can_import('pyaudio')
    vosk = can_import('vosk') and (ROOT / 'models' / 'vosk' / 'vosk-model-small-en-us-0.15').exists()
    aub = can_import('aubio')
    if (not pya or not vosk) and '--no-speech' not in args:
        print('[INFO] Speech dependencies missing; launching with --no-speech')
        args.append('--no-speech')
    if pya and not aub:
        print('[INFO] aubio not installed; using built-in numpy pitch fallback')
    if (not pya) and '--no-pitch' not in args:
        print('[INFO] Microphone dependency missing; launching with --no-pitch')
        args.append('--no-pitch')
    cmd = [str(PYTHON), '-m', 'hand_galaxy.main', *args]
    env = os.environ.copy()
    env['PYTHONPATH'] = str(SRC)
    return subprocess.call(cmd, cwd=str(ROOT), env=env)

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
