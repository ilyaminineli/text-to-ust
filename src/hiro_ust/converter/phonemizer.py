"""Japanese/romaji/experimental English phonemization helpers."""

import re

ROMAJI_MAP = {
    "a": "あ",
    "i": "い",
    "u": "う",
    "e": "え",
    "o": "お",
    "ā": "あー",
    "ī": "いー",
    "ū": "うー",
    "ē": "えー",
    "ō": "おー",
    "ka": "か",
    "ki": "き",
    "ku": "く",
    "ke": "け",
    "ko": "こ",
    "ga": "が",
    "gi": "ぎ",
    "gu": "ぐ",
    "ge": "げ",
    "go": "ご",
    "kya": "きゃ",
    "kyu": "きゅ",
    "kyo": "きょ",
    "gya": "ぎゃ",
    "gyu": "ぎゅ",
    "gyo": "ぎょ",
    "sa": "さ",
    "shi": "し",
    "su": "す",
    "se": "せ",
    "so": "そ",
    "za": "ざ",
    "ji_s": "じ",
    "zu": "ず",
    "ze": "ぜ",
    "zo": "ぞ",
    "sha": "しゃ",
    "shu": "しゅ",
    "sho": "しょ",
    "ja": "じゃ",
    "ju": "じゅ",
    "jo": "じょ",
    "ta": "た",
    "chi": "ち",
    "tsu": "つ",
    "te": "て",
    "to": "と",
    "da": "だ",
    "ji_t": "ぢ",
    "zu_t": "づ",
    "de": "で",
    "do": "ど",
    "cha": "ちゃ",
    "chu": "ちゅ",
    "cho": "ちょ",
    "na": "な",
    "ni": "に",
    "nu": "ぬ",
    "ne": "ね",
    "no": "の",
    "nya": "にゃ",
    "nyu": "にゅ",
    "nyo": "にょ",
    "ha": "は",
    "hi": "ひ",
    "fu": "ふ",
    "he": "へ",
    "ho": "ほ",
    "ba": "ば",
    "bi": "び",
    "bu": "ぶ",
    "be": "べ",
    "bo": "ぼ",
    "pa": "ぱ",
    "pi": "ぴ",
    "pu": "ぷ",
    "pe": "ぺ",
    "po": "ぽ",
    "hya": "ひゃ",
    "hyu": "ひゅ",
    "hyo": "ひょ",
    "ma": "ま",
    "mi": "み",
    "mu": "む",
    "me": "め",
    "mo": "も",
    "mya": "みゃ",
    "myu": "みゅ",
    "myo": "みょ",
    "ya": "や",
    "yu": "ゆ",
    "yo": "よ",
    "ra": "ら",
    "ri": "り",
    "ru": "る",
    "re": "れ",
    "ro": "ろ",
    "rya": "りゃ",
    "ryu": "りゅ",
    "ryo": "りょ",
    "wa": "わ",
    "wi": "うぃ",
    "we": "うぇ",
    "wo": "を",
    "n": "ん",
    "っ": "っ",
    "xtsu": "っ",
    "-": "ー",
}

ENGLISH_VOWEL_MAP = {"a": "あ", "e": "え", "i": "い", "o": "お", "u": "う"}
ENGLISH_CONSONANT_MAP = {
    "b": "b",
    "k": "k",
    "g": "g",
    "d": "d",
    "t": "t",
    "p": "p",
    "m": "m",
    "n": "ん",
    "r": "r",
    "s": "s",
    "h": "h",
    "f": "f",
    "v": "v",
    "ch": "ち",
    "sh": "し",
    "j": "じ",
}
PUNCTUATION = set("。、！？,!?;:…")


class Phonemizer:
    def __init__(self):
        self.mode = "japanese"

    def set_mode(self, mode: str) -> None:
        if mode not in {"japanese", "hepburn", "wapuro", "english"}:
            raise ValueError(f"Unsupported phonemizer mode: {mode}")
        self.mode = mode

    @staticmethod
    def _contains_japanese(text: str) -> bool:
        return any("\u3040" <= c <= "\u30ff" for c in text)

    def text_to_phonemes(self, text: str):
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        text = text.strip().lower()
        if not text:
            return []
        if self.mode == "english":
            return self._english_to_phonemes(text)
        if self.mode == "japanese" and self._contains_japanese(text):
            return self._hiragana_to_phonemes(text)
        return self._romaji_to_phonemes(text)

    def _hiragana_to_phonemes(self, text: str):
        from hiro_ust.converter import HiroUSTGenerator

        generator = HiroUSTGenerator()
        result = []
        chunk = []
        for char in text:
            if char in PUNCTUATION:
                if chunk:
                    result.extend(generator.hiragana_to_romaji("".join(chunk)))
                    chunk = []
                result.append(char)
            else:
                chunk.append(char)
        if chunk:
            result.extend(generator.hiragana_to_romaji("".join(chunk)))
        return result

    def _romaji_to_phonemes(self, text: str):
        from hiro_ust.converter import HiroUSTGenerator

        generator = HiroUSTGenerator()
        phonemes = []
        for token in re.findall(r"[a-zāīūēō-]+|[^\s]", text):
            if token in PUNCTUATION:
                phonemes.append(token)
                continue
            i = 0
            hiragana = []
            while i < len(token):
                for length in (4, 3, 2, 1):
                    candidate = token[i : i + length]
                    if candidate in ROMAJI_MAP:
                        hiragana.append(ROMAJI_MAP[candidate])
                        i += length
                        break
                else:
                    hiragana.append(token[i])
                    i += 1
            phonemes.extend(generator.hiragana_to_romaji("".join(hiragana)))
        return phonemes

    def _english_to_phonemes(self, text: str):
        """Very small grapheme approximation; not a full English phonemizer."""
        phonemes = []
        for word in re.findall(r"[a-z']+|[^\s]", text):
            if word in PUNCTUATION:
                phonemes.append(word)
                continue
            i = 0
            while i < len(word):
                if word[i : i + 2] in {"ch", "sh"}:
                    phonemes.append(ENGLISH_CONSONANT_MAP[word[i : i + 2]])
                    i += 2
                else:
                    char = word[i]
                    phonemes.append(
                        ENGLISH_VOWEL_MAP.get(
                            char, ENGLISH_CONSONANT_MAP.get(char, char)
                        )
                    )
                    i += 1
        return phonemes


__all__ = ["Phonemizer", "ROMAJI_MAP"]
