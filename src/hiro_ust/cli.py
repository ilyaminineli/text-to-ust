"""Canonical CLI and GUI entry point for Hiro UST."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import GeneratorConfig
from .core import HiroUSTProcessor
from .melody.scales import SCALES


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hiro-ust",
        description="Generate UTAU UST/USTX from Japanese lyrics, or open the editor.",
    )
    parser.add_argument("--lyrics", help="Lyrics supplied directly on the command line.")
    parser.add_argument("--lyrics-file", type=Path, help="Read lyrics from a UTF-8 text file.")
    parser.add_argument("--output", type=Path, help="Destination .ust/.ustx path.")
    parser.add_argument("--format", choices=("ust", "ustx"), default="ustx")
    parser.add_argument("--tempo", type=float, default=120.0)
    parser.add_argument("--root", type=int, default=60, help="Root MIDI note / register anchor.")
    parser.add_argument("--scale", choices=tuple(SCALES), default="Major Pentatonic")
    parser.add_argument("--seed", type=int, default=1234)
    return parser


def main(argv=None, debug: bool = False):
    """Run generation from CLI arguments or open the PySide6 editor.

    argv follows the sys.argv convention and includes the executable name.
    With debug=True the GUI is created but its event loop is not entered.
    """
    args = list(sys.argv if argv is None else argv)
    if not args:
        args = ["hiro-ust"]

    if debug:
        from PySide6.QtWidgets import QApplication
        from .ui.main_window import HiroMainWindow
        from .ui.theme import apply_theme

        app = QApplication.instance() or QApplication(args)
        apply_theme(app)
        window = HiroMainWindow()
        window.show()
        return app, window

    parser = _build_parser()
    options = parser.parse_args(args[1:])
    generation_requested = (
        options.lyrics is not None
        or options.lyrics_file is not None
        or options.output is not None
    )
    if not generation_requested:
        from .ui.main_window import run_app

        # Do not forward CLI-only options (such as --tempo) to Qt's argument parser.
        return run_app([args[0]])

    if (options.lyrics is None) == (options.lyrics_file is None):
        parser.error("provide exactly one of --lyrics or --lyrics-file")

    try:
        lyrics = (
            options.lyrics
            if options.lyrics is not None
            else options.lyrics_file.read_text(encoding="utf-8")
        )
    except OSError as exc:
        parser.error(f"could not read lyrics file: {exc}")

    if not lyrics.strip():
        parser.error("lyrics must not be empty")

    project_name = options.output.stem if options.output else "hiro_output"
    output_path = options.output or Path(f"{project_name}.{options.format}")
    try:
        config = GeneratorConfig(
            tempo=options.tempo,
            root_key=options.root,
            scale=options.scale,
            seed=options.seed,
        )
        processor = HiroUSTProcessor(config)
        content = processor.process_lyrics(
            lyrics,
            project_name=project_name,
            output_format=options.format,
        )
        output_path.write_text(content, encoding="utf-8")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    print(output_path)
    return 0


def __getattr__(name: str):
    """Keep the old lazy import path without loading Qt for CLI-only runs."""
    if name == "HiroMainWindow":
        from .ui.main_window import HiroMainWindow

        return HiroMainWindow
    raise AttributeError(name)


__all__ = ["main", "HiroMainWindow"]

if __name__ == "__main__":
    raise SystemExit(main())
