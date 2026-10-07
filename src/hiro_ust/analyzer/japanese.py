"""Japanese tokenization and reading analysis.

SudachiPy is used when available. The analyzer deliberately returns a small,
stable token model so the rest of Hiro does not depend on a specific NLP
library.
"""
from __future__ import annotations

from dataclasses import dataclass
import unicodedata

KANJI_RANGES = (
    ("\u3400", "\u4dbf"),
    ("\u4e00", "\u9fff"),
)


def contains_kanji(text: str) -> bool:
    return any(any(start <= char <= end for start, end in KANJI_RANGES) for char in text)


def _is_kana(text: str) -> bool:
    return bool(text) and all(
        "\u3040" <= char <= "\u309f" or "\u30a0" <= char <= "\u30ff" or char == "ー"
        for char in text
    )


@dataclass(frozen=True)
class AnalyzerToken:
    surface: str
    reading: str
    lemma: str
    normalized: str
    pos: str
    pos_detail: str
    start: int
    end: int
    kanji: bool
    kana: bool
    punctuation: bool

    @property
    def reading_hiragana(self) -> str:
        return "".join(
            chr(ord(char) - 0x60) if "\u30a1" <= char <= "\u30f6" else char
            for char in self.reading
        )


class JapaneseAnalyzer:
    """Small adapter around SudachiPy with a deterministic fallback."""

    def __init__(self, split_mode: str = "C"):
        self.split_mode = split_mode.upper()
        self._tokenizer = None
        self.backend = "fallback"
        try:
            from sudachipy import Dictionary, SplitMode

            mode_map = {"A": SplitMode.A, "B": SplitMode.B, "C": SplitMode.C}
            self._tokenizer = Dictionary(dict="small").create(mode_map[self.split_mode])
            self.backend = "sudachi"
        except Exception:
            self._tokenizer = None

    @property
    def available(self) -> bool:
        return self._tokenizer is not None

    def analyze(self, text: str) -> list[AnalyzerToken]:
        if not text:
            return []
        if self._tokenizer is None:
            return self._fallback(text)

        result: list[AnalyzerToken] = []
        cursor = 0
        for morpheme in self._tokenizer.tokenize(text):
            surface = morpheme.surface()
            reading = morpheme.reading_form() or surface
            pos = morpheme.part_of_speech()
            punctuation = bool(pos and pos[0] in {"補助記号"})
            start = text.find(surface, cursor)
            if start < 0:
                start = cursor
            end = start + len(surface)
            result.append(
                AnalyzerToken(
                    surface=surface,
                    reading=reading,
                    lemma=morpheme.dictionary_form() or surface,
                    normalized=morpheme.normalized_form() or surface,
                    pos=pos[0] if pos else "",
                    pos_detail="/".join(pos[1:4]) if pos else "",
                    start=start,
                    end=end,
                    kanji=contains_kanji(surface),
                    kana=_is_kana(surface),
                    punctuation=punctuation,
                )
            )
            cursor = end
        return result

    def _fallback(self, text: str) -> list[AnalyzerToken]:
        """Keep the application usable when the optional NLP stack is absent."""
        result: list[AnalyzerToken] = []
        cursor = 0
        for part in text.split():
            start = text.find(part, cursor)
            start = cursor if start < 0 else start
            end = start + len(part)
            if all(unicodedata.category(c).startswith("P") for c in part):
                pos = "補助記号"
            elif _is_kana(part):
                pos = "記号" if all(unicodedata.category(c).startswith("S") for c in part) else "名詞"
            else:
                pos = "名詞"
            reading = part if _is_kana(part) else ""
            result.append(
                AnalyzerToken(
                    surface=part,
                    reading=reading,
                    lemma=part,
                    normalized=part,
                    pos=pos,
                    pos_detail="fallback",
                    start=start,
                    end=end,
                    kanji=contains_kanji(part),
                    kana=_is_kana(part),
                    punctuation=pos == "補助記号",
                )
            )
            cursor = end
        return result


__all__ = ["AnalyzerToken", "JapaneseAnalyzer", "contains_kanji"]
