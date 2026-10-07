"""Regression tests for Japanese lyric structure using the canonical example."""
from __future__ import annotations

import shutil

from hiro_ust.data.example_lyrics import EXAMPLE_LYRICS
from hiro_ust.lyrics import LyricParser


class TestPhonemizer:
    def text_to_phonemes(self, text):
        return list(text)


def test_example_contains_expected_sections():
    parser = LyricParser()
    doc = parser.parse(EXAMPLE_LYRICS, TestPhonemizer())

    names = [section.name for section in doc.sections]
    assert names == ["Main", "Verse 1", "Chorus", "Bridge", "Chorus"]
    assert doc.word_count > 20


def test_kanji_structure_survives_without_backend():
    parser = LyricParser()
    doc = parser.parse("心　僕の世界じゃない", TestPhonemizer())

    words = [word for section in doc.sections for line in section.lines for word in line.words]
    assert words[0].text == "心"
    assert words[0].kanji_count == 1
    assert words[1].text == "僕の世界じゃない"
    assert words[1].kanji_count >= 2


def test_kuroshiro_backend_is_used_when_node_is_available():
    if shutil.which("node") is None:
        return

    from hiro_ust.analyzer import JapaneseAnalyzer

    analyzer = JapaneseAnalyzer()
    if not analyzer.available:
        return

    tokens = analyzer.analyze("数える")
    assert tokens
    assert tokens[0].surface == "数え"
    assert tokens[0].reading
    assert any(token.kanji for token in tokens)
