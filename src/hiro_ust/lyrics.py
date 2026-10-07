"""Structured Japanese lyric representation.

The parser keeps three layers separate:
- source text units chosen by the lyricist (usually whitespace-separated)
- linguistic morphemes from the Japanese analyzer
- UTAU-ready phonemes produced from each morpheme reading
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .analyzer.japanese import AnalyzerToken, JapaneseAnalyzer


@dataclass
class LyricMorpheme:
    token: AnalyzerToken
    phonemes: list[str] = field(default_factory=list)

    @property
    def surface(self) -> str:
        return self.token.surface

    @property
    def reading(self) -> str:
        return self.token.reading_hiragana or self.token.reading

    @property
    def pos(self) -> str:
        return self.token.pos

    @property
    def is_kanji(self) -> bool:
        return self.token.kanji

    @property
    def is_punctuation(self) -> bool:
        return self.token.punctuation


@dataclass
class LyricWord:
    text: str
    morphemes: list[LyricMorpheme] = field(default_factory=list)

    @property
    def reading(self) -> str:
        return "".join(m.reading for m in self.morphemes)

    @property
    def phonemes(self) -> list[str]:
        result: list[str] = []
        for morpheme in self.morphemes:
            result.extend(morpheme.phonemes)
        return result

    @property
    def kanji_count(self) -> int:
        return sum(1 for morpheme in self.morphemes if morpheme.is_kanji)

    @property
    def structure(self) -> str:
        return " ".join(
            f"{m.surface}={m.reading or '?'}[{m.pos or '?'}]"
            for m in self.morphemes
            if not m.is_punctuation
        )


@dataclass
class LyricLine:
    words: list[LyricWord] = field(default_factory=list)
    punctuation: str = ""
    section: str = "Main"

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)


@dataclass
class LyricSection:
    name: str
    lines: list[LyricLine] = field(default_factory=list)


@dataclass
class LyricDocument:
    sections: list[LyricSection] = field(default_factory=list)
    analyzer_backend: str = "fallback"

    @property
    def word_count(self) -> int:
        return sum(len(line.words) for section in self.sections for line in section.lines)

    @property
    def morpheme_count(self) -> int:
        return sum(
            len(word.morphemes)
            for section in self.sections
            for line in section.lines
            for word in line.words
        )

    @property
    def kanji_word_count(self) -> int:
        return sum(
            word.kanji_count
            for section in self.sections
            for line in section.lines
            for word in line.words
        )


class LyricParser:
    """Parse sections, user-defined word boundaries, and Japanese morphemes."""

    def __init__(self, analyzer: JapaneseAnalyzer | None = None):
        self.analyzer = analyzer or JapaneseAnalyzer()

    @staticmethod
    def _split_units(line: str) -> list[str]:
        # Full-width spaces are especially common in Japanese lyric sheets.
        return [part for part in line.replace("\u3000", " ").split() if part]

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

            words: list[LyricWord] = []
            for unit in self._split_units(line):
                morphemes: list[LyricMorpheme] = []
                for token in self.analyzer.analyze(unit):
                    reading = token.reading_hiragana or token.surface
                    phonemes = phonemizer.text_to_phonemes(reading)
                    morphemes.append(LyricMorpheme(token=token, phonemes=phonemes))
                if morphemes:
                    words.append(LyricWord(text=unit, morphemes=morphemes))

            if words:
                punctuation = ""
                trailing = line.rstrip()
                if trailing and trailing[-1] in "。、！？!?…":
                    punctuation = trailing[-1]
                current.lines.append(
                    LyricLine(words=words, punctuation=punctuation, section=current.name)
                )

        return LyricDocument(sections=sections, analyzer_backend=self.analyzer.backend)


__all__ = [
    "LyricDocument",
    "LyricLine",
    "LyricMorpheme",
    "LyricSection",
    "LyricWord",
    "LyricParser",
]
