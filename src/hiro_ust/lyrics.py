"""Structured Japanese lyric representation.

This module keeps text parsing separate from phonemization and melody.
It is intentionally small so a future Kuromoji-backed analyzer can replace
or enrich the parser without changing the melody engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LyricWord:
    text: str
    phonemes: list[str] = field(default_factory=list)


@dataclass
class LyricLine:
    words: list[LyricWord] = field(default_factory=list)
    punctuation: str = ""
    section: str = "Main"


@dataclass
class LyricSection:
    name: str
    lines: list[LyricLine] = field(default_factory=list)


@dataclass
class LyricDocument:
    sections: list[LyricSection] = field(default_factory=list)


class LyricParser:
    """Parse simple section/line structure without assuming Japanese semantics."""

    def parse(self, text: str, phonemizer) -> LyricDocument:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("lyrics must be a non-empty string")

        sections: list[LyricSection] = []
        current = LyricSection("Main")
        sections.append(current)

        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]") and len(line) > 2:
                current = LyricSection(line[1:-1].strip())
                sections.append(current)
                continue

            tokens = []
            for word in line.split():
                phonemes = phonemizer.text_to_phonemes(word)
                if phonemes:
                    tokens.append(LyricWord(word, phonemes))
            if tokens:
                current.lines.append(LyricLine(tokens, section=current.name))

        return LyricDocument(sections)


__all__ = ["LyricDocument", "LyricLine", "LyricSection", "LyricWord", "LyricParser"]
