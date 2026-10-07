"""Compatibility wrapper for the PySide6 UI."""
from .ui.main_window import HiroMainWindow, run_app

USTGeneratorApp = HiroMainWindow

__all__ = ["HiroMainWindow", "USTGeneratorApp", "run_app"]
