"""Japanese reading analysis backed by vendored Kuroshiro/Kuromoji."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unicodedata

KANJI_RANGES = (("㐀", "䶿"), ("一", "鿿"), ("豈", "﫿"))


def contains_kanji(text: str) -> bool:
    return any(any(a <= ch <= b for a, b in KANJI_RANGES) for ch in text)


def normalize_reading(text: str) -> str:
    """Normalize Kuroshiro hiragana output for UTAU-style mora parsing."""
    if not text:
        return ""
    value = "".join(
        chr(ord(ch) - 0x60) if "ァ" <= ch <= "ヶ" else ch
        for ch in text
    )
    vowels = {
        **dict.fromkeys("あかがさざただなはばぱまゃやらわぁ", "あ"),
        **dict.fromkeys("いきぎしじちぢにひびぴみりぃ", "い"),
        **dict.fromkeys("うくぐすずつづぬふぶぷむゅゆるぅ", "う"),
        **dict.fromkeys("えけげせぜてでねへべぺめれぇ", "え"),
        **dict.fromkeys("おこごそぞとどのほぼぽもょよろをぉ", "お"),
    }
    result: list[str] = []
    last_vowel = ""
    for char in value:
        if char == "ー":
            result.append(last_vowel or char)
            continue
        result.append(char)
        if char in vowels:
            last_vowel = vowels[char]
    return "".join(result)


def _is_kana(text: str) -> bool:
    return bool(text) and all(
        "぀" <= ch <= "ゟ" or "゠" <= ch <= "ヿ" or ch == "ー"
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
        return normalize_reading(self.reading or self.surface)


@dataclass(frozen=True)
class JapaneseAnalysis:
    text: str
    reading: str
    spaced: str
    furigana: str
    tokens: tuple[AnalyzerToken, ...]


class JapaneseAnalyzer:
    """Use Kuroshiro for the canonical reading and Kuromoji for token metadata."""

    def __init__(self, node_executable: str = "node") -> None:
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
        return list(self.analyze_detailed_many([text])[0].tokens)

    def analyze_many(self, texts: list[str]) -> list[list[AnalyzerToken]]:
        return [list(item.tokens) for item in self.analyze_detailed_many(texts)]

    def analyze_with_reading(self, text: str) -> JapaneseAnalysis:
        return self.analyze_detailed_many([text])[0]

    def analyze_detailed_many(self, texts: list[str]) -> list[JapaneseAnalysis]:
        if not texts:
            return []
        if not self.available:
            return [self._fallback_analysis(text) for text in texts]

        try:
            process = subprocess.run(
                [self.node_executable, str(self.bridge)],
                input=json.dumps(texts, ensure_ascii=False),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=max(30, min(180, 25 + sum(len(text) for text in texts) // 2)),
                check=False,
            )
            if process.returncode != 0:
                return [self._fallback_analysis(text) for text in texts]
            raw_batches = json.loads(process.stdout or "[]")
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return [self._fallback_analysis(text) for text in texts]

        if not isinstance(raw_batches, list):
            return [self._fallback_analysis(text) for text in texts]

        result: list[JapaneseAnalysis] = []
        for text, payload in zip(texts, raw_batches):
            if not isinstance(payload, dict):
                result.append(self._fallback_analysis(text))
                continue

            raw_tokens = payload.get("tokens", [])
            tokens: list[AnalyzerToken] = []
            cursor = 0
            for raw in raw_tokens if isinstance(raw_tokens, list) else []:
                surface = str(raw.get("surface", ""))
                if not surface:
                    continue
                position = text.find(surface, cursor)
                if position < 0:
                    position = text.find(surface)
                start = max(0, position if position >= 0 else cursor)
                end = min(len(text), start + len(surface))
                cursor = end
                pos = str(raw.get("pos", ""))
                tokens.append(
                    AnalyzerToken(
                        surface=surface,
                        reading=str(raw.get("reading", "")) or surface,
                        lemma=str(raw.get("lemma", "")) or surface,
                        normalized=surface,
                        pos=pos,
                        pos_detail=str(raw.get("pos_detail", "")),
                        start=start,
                        end=end,
                        kanji=contains_kanji(surface),
                        kana=_is_kana(surface),
                        punctuation=pos in {"記号", "補助記号"},
                    )
                )

            # IMPORTANT: this string is produced by Kuroshiro itself.
            # It is the canonical singing reading and must not be rebuilt
            # from Kuromoji token readings.
            reading = normalize_reading(str(payload.get("reading", "")) or text)
            result.append(
                JapaneseAnalysis(
                    text=text,
                    reading=reading,
                    spaced=str(payload.get("spaced", "")),
                    furigana=str(payload.get("furigana", "")),
                    tokens=tuple(tokens),
                )
            )

        while len(result) < len(texts):
            result.append(self._fallback_analysis(texts[len(result)]))
        return result

    @staticmethod
    def _fallback_analysis(text: str) -> JapaneseAnalysis:
        punctuation = all(unicodedata.category(ch).startswith("P") for ch in text) if text else False
        token = AnalyzerToken(
            surface=text,
            reading=text if _is_kana(text) else "",
            lemma=text,
            normalized=text,
            pos="記号" if punctuation else "",
            pos_detail="fallback",
            start=0,
            end=len(text),
            kanji=contains_kanji(text),
            kana=_is_kana(text),
            punctuation=punctuation,
        )
        return JapaneseAnalysis(
            text=text,
            reading=normalize_reading(token.reading or text),
            spaced=text,
            furigana=text,
            tokens=(token,),
        )


__all__ = [
    "AnalyzerToken",
    "JapaneseAnalysis",
    "JapaneseAnalyzer",
    "contains_kanji",
    "normalize_reading",
]