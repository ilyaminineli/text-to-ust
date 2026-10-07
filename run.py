"""Repository-root launcher for Hiro UST.

Usage:
    python run.py
    python run.py --lyrics "きょうも..."
    python run.py --lyrics-file lyrics.txt --output song.ustx
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hiro_ust.cli import main as gui_main
from hiro_ust.core import HiroUSTProcessor
from hiro_ust.config import GeneratorConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Hiro UST Generator")
    parser.add_argument("--lyrics")
    parser.add_argument("--lyrics-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=("ust", "ustx"), default="ustx")
    parser.add_argument("--tempo", type=float, default=120.0)
    parser.add_argument("--root", type=int, default=60)
    parser.add_argument("--scale", default="Major Pentatonic")
    parser.add_argument("--seed", type=int, default=1234)
    args = parser.parse_args()

    if args.lyrics is None and args.lyrics_file is None and args.output is None:
        gui_main()
        return 0

    if bool(args.lyrics) == bool(args.lyrics_file):
        parser.error("provide exactly one of --lyrics or --lyrics-file")

    lyrics = args.lyrics if args.lyrics is not None else args.lyrics_file.read_text(encoding="utf-8")
    name = args.output.stem if args.output else "hiro_output"
    processor = HiroUSTProcessor(
        GeneratorConfig(
            tempo=args.tempo,
            root_key=args.root,
            scale=args.scale,
            seed=args.seed,
        )
    )
    content = processor.process_lyrics(lyrics, project_name=name, output_format=args.format)
    output = args.output or Path(f"{name}.{args.format}")
    output.write_text(content, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
