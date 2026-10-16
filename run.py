"""Repository-root compatibility launcher for Hiro UST.

Usage:
    python run.py
    python run.py --lyrics "きょうも..."
    python run.py --lyrics-file lyrics.txt --output song.ustx
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hiro_ust.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
