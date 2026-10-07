"""Centralized monochrome Qt theme for Hiro UST."""
from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

PALETTE = {
    "bg": "#101010",
    "surface": "#171717",
    "surface2": "#202020",
    "border": "#303030",
    "text": "#f2efe5",
    "muted": "#989898",
    "accent": "#f2efe5",
    "accent_text": "#101010",
}


def choose_font() -> str:
    families = set(QFontDatabase.families())
    for name in ("Noto Sans CJK JP", "Yu Gothic UI", "Yu Gothic", "Meiryo UI", "Meiryo", "Segoe UI"):
        if name in families:
            return name
    return QApplication.font().family()


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    font = choose_font()
    app.setFont(QFont(font, 10))

    app.setStyleSheet(
        f"""
        QWidget {{
            color: {PALETTE["text"]};
            background: {PALETTE["bg"]};
            font-family: "{font}";
            font-size: 10pt;
        }}
        QMainWindow, QDialog {{ background: {PALETTE["bg"]}; }}
        QMenuBar {{
            background: {PALETTE["surface"]};
            border-bottom: 1px solid {PALETTE["border"]};
            padding: 3px 6px;
        }}
        QMenuBar::item {{ padding: 6px 9px; border-radius: 4px; }}
        QMenuBar::item:selected, QMenu::item:selected {{
            background: {PALETTE["surface2"]};
        }}
        QMenu {{
            background: {PALETTE["surface"]};
            border: 1px solid {PALETTE["border"]};
            padding: 4px;
        }}
        QToolBar {{
            background: {PALETTE["surface"]};
            border: none;
            spacing: 6px;
            padding: 6px;
        }}
        QStatusBar {{
            background: {PALETTE["surface"]};
            border-top: 1px solid {PALETTE["border"]};
            color: {PALETTE["muted"]};
        }}
        QFrame#panel {{
            background: {PALETTE["surface"]};
            border: 1px solid {PALETTE["border"]};
            border-radius: 8px;
        }}
        QLabel#eyebrow {{ color: {PALETTE["muted"]}; font-size: 9pt; }}
        QLabel#title {{ font-size: 17pt; font-weight: 700; }}
        QLabel#section {{ font-size: 10pt; font-weight: 700; }}
        QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTableWidget {{
            background: {PALETTE["bg"]};
            border: 1px solid {PALETTE["border"]};
            border-radius: 6px;
            padding: 7px;
            selection-background-color: {PALETTE["surface2"]};
            selection-color: {PALETTE["text"]};
        }}
        QPlainTextEdit:focus, QLineEdit:focus, QSpinBox:focus,
        QDoubleSpinBox:focus, QComboBox:focus {{
            border: 1px solid #575757;
        }}
        QPushButton, QToolButton {{
            background: {PALETTE["surface2"]};
            border: 1px solid {PALETTE["border"]};
            border-radius: 6px;
            padding: 7px 11px;
        }}
        QPushButton:hover, QToolButton:hover {{ border-color: #575757; }}
        QPushButton#primary {{
            background: {PALETTE["accent"]};
            color: {PALETTE["accent_text"]};
            border-color: {PALETTE["accent"]};
            font-weight: 700;
        }}
        QCheckBox {{ spacing: 8px; }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid #525252;
            border-radius: 4px;
            background: {PALETTE["bg"]};
        }}
        QCheckBox::indicator:checked {{
            background: {PALETTE["accent"]};
            border-color: {PALETTE["accent"]};
        }}
        QSplitter::handle {{ background: {PALETTE["border"]}; }}
        QHeaderView::section {{
            background: {PALETTE["surface2"]};
            border: none;
            border-right: 1px solid {PALETTE["border"]};
            border-bottom: 1px solid {PALETTE["border"]};
            padding: 6px;
        }}
        """
    )
