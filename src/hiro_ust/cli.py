"""Canonical application entry point for Hiro UST."""

from __future__ import annotations

import sys

from .ui.main_window import HiroMainWindow, run_app


def main(argv=None, debug: bool = False):
    """Start the PySide6 GUI.

    With debug=True the application/window is created without entering the event loop.
    """
    args = list(sys.argv if argv is None else argv)
    if debug:
        from PySide6.QtWidgets import QApplication
        from .ui.theme import apply_theme

        app = QApplication.instance() or QApplication(args)
        apply_theme(app)
        window = HiroMainWindow()
        window.show()
        return app, window
    return run_app(args)


__all__ = ["main", "HiroMainWindow"]

if __name__ == "__main__":
    raise SystemExit(main())
