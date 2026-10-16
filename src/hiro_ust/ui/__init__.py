"""Lazy exports for the PySide6 user interface.

Importing a UI submodule should not eagerly construct the whole main-window
dependency tree. Public names remain available via lazy attribute lookup.
"""

from __future__ import annotations

from typing import Any

__all__ = ["HiroMainWindow", "run_app", "apply_theme"]


def __getattr__(name: str) -> Any:
    if name in {"HiroMainWindow", "run_app"}:
        from .main_window import HiroMainWindow, run_app

        return {"HiroMainWindow": HiroMainWindow, "run_app": run_app}[name]
    if name == "apply_theme":
        from .theme import apply_theme

        return apply_theme
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
