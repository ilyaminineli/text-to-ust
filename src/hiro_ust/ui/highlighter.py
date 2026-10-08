"""Syntax highlighting for Hiro lyric documents."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class LyricHighlighter(QSyntaxHighlighter):
    """Highlight section markers such as [Verse 1] in the lyric editor."""

    def __init__(self, document):
        super().__init__(document)
        self.section_format = QTextCharFormat()
        self.section_format.setForeground(QColor("#f2efe5"))
        self.section_format.setBackground(QColor("#252525"))
        self.section_format.setFontWeight(QFont.Weight.Bold)
        self.section_format.setProperty(QTextCharFormat.FullWidthSelection, True)

        self.bracket_format = QTextCharFormat()
        self.bracket_format.setForeground(QColor("#aaaaaa"))
        self.bracket_format.setFontWeight(QFont.Weight.Bold)

    def highlightBlock(self, text: str) -> None:
        stripped = text.strip()
        if len(stripped) >= 3 and stripped.startswith("[") and stripped.endswith("]"):
            start = text.index(stripped)
            self.setFormat(start, len(stripped), self.section_format)
            self.setFormat(start, 1, self.bracket_format)
            self.setFormat(start + len(stripped) - 1, 1, self.bracket_format)


__all__ = ["LyricHighlighter"]
