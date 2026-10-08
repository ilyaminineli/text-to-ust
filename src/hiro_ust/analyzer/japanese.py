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


class JapaneseAnalysisError(RuntimeError):
    """Raised when Japanese text cannot be converted to a safe kana reading."""


class JapaneseAnalyzer:
    """Kuroshiro first; modern Python fallback only for unresolved dictionary gaps."""

    def __init__(self, node_executable: str = "node") -> None:
        self.node_executable = node_executable
        bundle_root = Path(
            getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3])
        )
        self.bridge = bundle_root / "vendor" / "kuroshiro_bridge.js"
        self.dict_path = bundle_root / "vendor" / "kuromoji" / "dict"
        self.backend = "kuroshiro-kuromoji"
        self._available: bool | None = None
        self._pykakasi = None

    @property
    def available(self) -> bool:
        if self._available is None:
            self._available = (
                self.bridge.exists()
                and self.dict_path.exists()
                and shutil.which(self.node_executable) is not None
            )
        return self._available

    def _modern_fallback(self, text: str) -> str:
        """Convert dictionary gaps with PyKakasi while preserving Kuroshiro as primary."""
        if self._pykakasi is None:
            try:
                import pykakasi
            except ImportError as exc:
                raise JapaneseAnalysisError(
                    "Kuroshiro/Kuromoji left Kanji unresolved and the modern "
                    "Japanese fallback is not installed.\n"
                    "Install it with:\n\n"
                    "    pip install pykakasi\n\n"
                    f"Source text: {text!r}"
                ) from exc
            self._pykakasi = pykakasi.kakasi()

        try:
            converted = self._pykakasi.convert(text)
            reading = "".join(
                str(item.get("hira", item.get("kana", "")))
                for item in converted
            )
        except Exception as exc:
            raise JapaneseAnalysisError(
                f"PyKakasi failed to convert {text!r}: {exc}"
            ) from exc

        reading = normalize_reading(reading)

        if contains_kanji(reading):
            raise JapaneseAnalysisError(
                "Both Kuroshiro/Kuromoji and PyKakasi left Kanji unresolved.\n"
                f"Input: {text!r}\n"
                f"PyKakasi reading: {reading!r}"
            )

        return reading

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
            missing = []
            if not self.bridge.exists():
                missing.append(f"bridge not found: {self.bridge}")
            if not self.dict_path.exists():
                missing.append(f"Kuromoji dictionary not found: {self.dict_path}")
            if shutil.which(self.node_executable) is None:
                missing.append(f"Node executable not found: {self.node_executable}")

            detail = "; ".join(missing) or "unknown backend availability error"

            if any(contains_kanji(text) for text in texts):
                raise JapaneseAnalysisError(
                    "Kuroshiro/Kuromoji is unavailable, so Kanji cannot be "
                    f"safely converted to Hiragana: {detail}"
                )

            return [self._fallback_analysis(text) for text in texts]

        try:
            process = subprocess.run(
                [self.node_executable, str(self.bridge)],
                input=json.dumps(texts, ensure_ascii=False),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=max(
                    30,
                    min(180, 25 + sum(len(text) for text in texts) // 2),
                ),
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise JapaneseAnalysisError(
                f"Failed to execute Kuroshiro bridge: {exc}"
            ) from exc

        if process.returncode != 0:
            stderr = (process.stderr or "").strip()
            raise JapaneseAnalysisError(
                "Kuroshiro/Kuromoji bridge failed "
                f"(exit code {process.returncode}).\n"
                f"{stderr or 'Node returned no diagnostic output.'}"
            )

        try:
            raw_batches = json.loads(process.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise JapaneseAnalysisError(
                "Kuroshiro bridge returned invalid JSON.\n"
                f"Output: {(process.stdout or '').strip()[:1000]!r}"
            ) from exc

        if not isinstance(raw_batches, list) or len(raw_batches) != len(texts):
            raise JapaneseAnalysisError(
                "Kuroshiro bridge returned an unexpected number of analyses."
            )

        result: list[JapaneseAnalysis] = []

        for text, payload in zip(texts, raw_batches):
            if not isinstance(payload, dict):
                raise JapaneseAnalysisError(
                    f"Invalid Kuroshiro payload for {text!r}: {payload!r}"
                )

            raw_tokens = payload.get("tokens", [])
            tokens: list[AnalyzerToken] = []
            cursor = 0

            if not isinstance(raw_tokens, list):
                raise JapaneseAnalysisError(
                    f"Kuromoji token output is not a list for {text!r}"
                )

            for raw in raw_tokens:
                if not isinstance(raw, dict):
                    continue

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

            raw_reading = str(payload.get("reading", ""))
            if not raw_reading:
                raise JapaneseAnalysisError(
                    f"Kuroshiro returned an empty reading for {text!r}"
                )

            if contains_kanji(raw_reading):
                # Kuroshiro's old IPADIC dictionary can miss modern lexical
                # compounds. PyKakasi provides a second, offline Japanese
                # dictionary in Python for those gaps.
                reading = self._modern_fallback(text)
            else:
                reading = normalize_reading(raw_reading)

            if contains_kanji(reading):
                raise JapaneseAnalysisError(
                    "Japanese reading still contains Kanji before phonemization: "
                    f"{reading!r} (source: {text!r})"
                )

            result.append(
                JapaneseAnalysis(
                    text=text,
                    reading=reading,
                    spaced=str(payload.get("spaced", "")),
                    furigana=str(payload.get("furigana", "")),
                    tokens=tuple(tokens),
                )
            )

        return result

    @staticmethod
    def _fallback_analysis(text: str) -> JapaneseAnalysis:
        punctuation = (
            all(unicodedata.category(ch).startswith("P") for ch in text)
            if text
            else False
        )
        token = AnalyzerToken(
            surface=text,
            reading=text if _is_kana(text) else "",
            lemma=text,
            normalized=text,
            pos="記号" if punctuation else "",
            pos_detail="fallback-kana-only",
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
    "JapaneseAnalysisError",
    "JapaneseAnalyzer",
    "contains_kanji",
    "normalize_reading",
]
