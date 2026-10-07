"""Japanese linguistic analysis backed by vendored Kuroshiro/Kuromoji."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import unicodedata

KANJI_RANGES = (("\u3400", "\u4dbf"), ("\u4e00", "\u9fff"))


def contains_kanji(text: str) -> bool:
    return any(any(a <= ch <= b for a, b in KANJI_RANGES) for ch in text)


def _is_kana(text: str) -> bool:
    return bool(text) and all(
        "\u3040" <= ch <= "\u309f" or "\u30a0" <= ch <= "\u30ff" or ch == "ー"
        for ch in text
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
        value = self.reading or self.surface
        return "".join(
            chr(ord(ch) - 0x60) if "\u30a1" <= ch <= "\u30f6" else ch
            for ch in value
        )


class JapaneseAnalyzer:
    """Run the vendored Kuromoji analyzer through a tiny Node bridge."""

    def __init__(self, node_executable: str = "node"):
        self.node_executable = node_executable
        self.bridge = Path(__file__).resolve().parents[3] / "vendor" / "kuroshiro_bridge.js"
        self.backend = "kuroshiro-kuromoji"
        self._available: bool | None = None

    @property
    def available(self) -> bool:
        if self._available is None:
            if not self.bridge.exists():
                self._available = False
            else:
                try:
                    p = subprocess.run(
                        [self.node_executable, str(self.bridge)],
                        input=json.dumps(""),
                        text=True,
                        capture_output=True,
                        timeout=20,
                        check=False,
                    )
                    self._available = p.returncode == 0
                except (OSError, subprocess.SubprocessError):
                    self._available = False
        return self._available

    def analyze(self, text: str) -> list[AnalyzerToken]:
        if not text:
            return []
        if not self.available:
            return self._fallback(text)

        try:
            p = subprocess.run(
                [self.node_executable, str(self.bridge)],
                input=json.dumps(text, ensure_ascii=False),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=max(20, min(120, 20 + len(text))),
                check=False,
            )
            if p.returncode != 0:
                return self._fallback(text)
            raw = json.loads(p.stdout or "[]")
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return self._fallback(text)

        result: list[AnalyzerToken] = []
        for token in raw:
            surface = str(token.get("surface", ""))
            if not surface:
                continue
            start = max(0, int(token.get("word_position", 1)) - 1)
            end = min(len(text), start + len(surface))
            pos = str(token.get("pos", ""))
            result.append(
                AnalyzerToken(
                    surface=surface,
                    reading=str(token.get("reading", "")) or surface,
                    lemma=str(token.get("lemma", "")) or surface,
                    normalized=surface,
                    pos=pos,
                    pos_detail=str(token.get("pos_detail", "")),
                    start=start,
                    end=end,
                    kanji=contains_kanji(surface),
                    kana=_is_kana(surface),
                    punctuation=pos in {"記号", "補助記号"},
                )
            )
        return result

    @staticmethod
    def _fallback(text: str) -> list[AnalyzerToken]:
        result: list[AnalyzerToken] = []
        cursor = 0
        for part in text.split():
            start = text.find(part, cursor)
            start = cursor if start < 0 else start
            end = start + len(part)
            punctuation = all(unicodedata.category(ch).startswith("P") for ch in part)
            result.append(
                AnalyzerToken(
                    surface=part,
                    reading=part if _is_kana(part) else "",
                    lemma=part,
                    normalized=part,
                    pos="記号" if punctuation else "名詞",
                    pos_detail="fallback",
                    start=start,
                    end=end,
                    kanji=contains_kanji(part),
                    kana=_is_kana(part),
                    punctuation=punctuation,
                )
            )
            cursor = end
        return result


__all__ = ["AnalyzerToken", "JapaneseAnalyzer", "contains_kanji"]
