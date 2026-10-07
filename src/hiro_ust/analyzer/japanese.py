"""Japanese linguistic analysis backed by vendored Kuroshiro/Kuromoji."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unicodedata

KANJI_RANGES = (("\u3400", "\u4dbf"), ("\u4e00", "\u9fff"))


def contains_kanji(text: str) -> bool:
    return any(any(a <= ch <= b for a, b in KANJI_RANGES) for ch in text)


_VOWEL_BY_HIRAGANA = {
    **dict.fromkeys("あかがさざただなはばぱまゃやらわぁ", "あ"),
    **dict.fromkeys("いきぎしじちぢにひびぴみりぃ", "い"),
    **dict.fromkeys("うくぐすずつづぬふぶぷむゅゆるぅ", "う"),
    **dict.fromkeys("えけげせぜてでねへべぺめれぇ", "え"),
    **dict.fromkeys("おこごそぞとどのほぼぽもょよろをぉ", "お"),
}


def normalize_japanese_reading(text: str) -> str:
    """Normalize kana reading for singing-friendly UTAU phonemization."""
    if not text:
        return ""
    value = "".join(
        chr(ord(ch) - 0x60) if "\u30a1" <= ch <= "\u30f6" else ch
        for ch in text
    )
    result: list[str] = []
    last_vowel = ""
    for ch in value:
        if ch == "ー":
            result.append(last_vowel or ch)
            continue
        result.append(ch)
        vowel = _VOWEL_BY_HIRAGANA.get(ch)
        if vowel:
            last_vowel = vowel
    return "".join(result)


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
        return normalize_japanese_reading(self.reading or self.surface)


class JapaneseAnalyzer:
    """Run the vendored Kuromoji analyzer through a tiny Node bridge."""

    def __init__(self, node_executable: str = "node"):
        self.node_executable = node_executable
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
        self.bridge = bundle_root / "vendor" / "kuroshiro_bridge.js"
        self.backend = "kuroshiro-kuromoji"
        self._available: bool | None = None

    @property
    def available(self) -> bool:
        if self._available is None:
            self._available = self.bridge.exists() and shutil.which(self.node_executable) is not None
        return self._available

    def analyze(self, text: str) -> list[AnalyzerToken]:
        batches = self.analyze_many([text])
        return batches[0] if batches else []

    def analyze_many(self, texts: list[str]) -> list[list[AnalyzerToken]]:
        if not texts:
            return []
        if not self.available:
            return [self._fallback(text) for text in texts]

        try:
            p = subprocess.run(
                [self.node_executable, str(self.bridge)],
                input=json.dumps(texts, ensure_ascii=False),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=max(30, min(180, 25 + sum(len(text) for text in texts) // 2)),
                check=False,
            )
            if p.returncode != 0:
                return [self._fallback(text) for text in texts]
            raw_batches = json.loads(p.stdout or "[]")
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return [self._fallback(text) for text in texts]

        if not isinstance(raw_batches, list):
            return [self._fallback(text) for text in texts]

        result: list[list[AnalyzerToken]] = []
        for text, raw_tokens in zip(texts, raw_batches):
            tokens: list[AnalyzerToken] = []
            for token in raw_tokens:
                surface = str(token.get("surface", ""))
                if not surface:
                    continue
                start = max(0, int(token.get("word_position", 1)) - 1)
                end = min(len(text), start + len(surface))
                pos = str(token.get("pos", ""))
                tokens.append(
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
            result.append(tokens)

        while len(result) < len(texts):
            result.append(self._fallback(texts[len(result)]))
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


__all__ = ["AnalyzerToken", "JapaneseAnalyzer", "contains_kanji", "normalize_japanese_reading"]
