"""Compact monochrome Qt theme."""
from __future__ import annotations
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

PALETTE = {
    "bg": "#101010", "surface": "#171717", "surface2": "#202020",
    "border": "#303030", "text": "#f2efe5", "muted": "#898989",
    "accent": "#f2efe5", "accent_text": "#101010",
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
    app.setStyleSheet(f"""
    QWidget {{ color:{PALETTE['text']}; background:{PALETTE['bg']}; font-family:"{font}"; font-size:10pt; }}
    QMainWindow {{ background:{PALETTE['bg']}; }}
    QToolBar {{ background:{PALETTE['surface']}; border:0; spacing:5px; padding:5px; }}
    QToolButton, QPushButton {{ background:{PALETTE['surface2']}; border:1px solid {PALETTE['border']}; border-radius:5px; padding:6px 10px; }}
    QToolButton:hover, QPushButton:hover {{ border-color:#575757; }}
    QPushButton#primary {{ background:{PALETTE['accent']}; color:{PALETTE['accent_text']}; font-weight:700; }}
    QFrame#panel, QDockWidget {{ background:{PALETTE['surface']}; border:1px solid {PALETTE['border']}; }}
    QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTableWidget {{ background:{PALETTE['bg']}; border:1px solid {PALETTE['border']}; border-radius:5px; padding:6px; }}
    QPlainTextEdit:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color:#575757; }}
    QLabel#title {{ font-size:16pt; font-weight:700; }}
    QLabel#eyebrow {{ color:{PALETTE['muted']}; font-size:9pt; }}
    QMenu, QMenuBar {{ background:{PALETTE['surface']}; border:1px solid {PALETTE['border']}; }}
    QMenu::item:selected, QMenuBar::item:selected {{ background:{PALETTE['surface2']}; }}
    QTabBar::tab {{ background:{PALETTE['surface2']}; border:1px solid {PALETTE['border']}; padding:5px 9px; }}
    QTabBar::tab:selected {{ background:{PALETTE['bg']}; }}
    QSplitter::handle {{ background:{PALETTE['border']}; }}
    QHeaderView::section {{ background:{PALETTE['surface2']}; border:0; padding:5px; }}
    QDockWidget::title {{ background:{PALETTE['surface2']}; padding:5px; text-align:left; }}
    QScrollBar:horizontal, QScrollBar:vertical {{ background:{PALETTE['bg']}; }}
    """)
