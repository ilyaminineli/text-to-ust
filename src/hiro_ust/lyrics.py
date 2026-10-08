"""Structured Japanese lyrics with Kuroshiro readings and UTAU phonemes."""
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
        return self.token.reading_hiragana or self.token.surface

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
    reading_override: str = ""

    @property
    def reading(self) -> str:
        return self.reading_override or "".join(m.reading for m in self.morphemes)

    @property
    def phonemes(self) -> list[str]:
        result: list[str] = []
        if self.reading_override:
            return result
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
        ) or f"{self.text}={self.reading or '?'}"


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
    """Preserve user grouping while using Kuroshiro's sentence reading."""

    def __init__(self, analyzer: JapaneseAnalyzer | None = None):
        self.analyzer = analyzer or JapaneseAnalyzer()

    @staticmethod
    def _split_units(line: str) -> list[str]:
        return [part for part in line.replace("\u3000", " ").split() if part]

    def parse(self, text: str, phonemizer) -> LyricDocument:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("lyrics must be a non-empty string")

        sections: list[LyricSection] = []
        current = LyricSection("Main")
        sections.append(current)
        pending: list[tuple[LyricSection, str, str]] = []

        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]") and len(line) > 2:
                current = LyricSection(line[1:-1].strip())
                sections.append(current)
                continue

            for unit in self._split_units(line):
                pending.append((current, unit, line))

        analyses = self.analyzer.analyze_detailed_many([item[1] for item in pending])

        for (section, unit, source_line), analysis in zip(pending, analyses):
            # Kuroshiro normal-mode reading is the one source of truth for
            # singing. Kuromoji token metadata is displayed separately.
            reading = analysis.reading or unit
            phonemes = phonemizer.text_to_phonemes(reading)

            morphemes: list[LyricMorpheme] = []
            for token in analysis.tokens:
                token_reading = token.reading_hiragana
                if token_reading and token_reading != token.surface:
                    morphemes.append(
                        LyricMorpheme(
                            token=token,
                            phonemes=phonemizer.text_to_phonemes(token_reading),
                        )
                    )

            # We intentionally keep the entire lyric unit as one musical word.
            # Its reading/phonemes come from Kuroshiro, not raw Kanji text.
            synthetic = AnalyzerToken(
                surface=unit,
                reading=reading,
                lemma=unit,
                normalized=unit,
                pos="",
                pos_detail="kuroshiro-reading",
                start=0,
                end=len(unit),
                kanji=contains_kanji(unit),
                kana=not contains_kanji(unit),
                punctuation=False,
            )
            word = LyricWord(
                text=unit,
                morphemes=[LyricMorpheme(token=synthetic, phonemes=phonemes)],
                reading_override=reading,
            )

            punctuation = source_line.rstrip()[-1:] if source_line.rstrip().endswith(tuple("。、！？!?…")) else ""
            section.lines.append(
                LyricLine(
                    words=[word],
                    punctuation=punctuation,
                    section=section.name,
                )
            )

        return LyricDocument(
            sections=sections,
            analyzer_backend=self.analyzer.backend,
        )


__all__ = [
    "LyricDocument",
    "LyricLine",
    "LyricMorpheme",
    "LyricSection",
    "LyricWord",
    "LyricParser",
]
