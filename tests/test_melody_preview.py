"""Tests for the generated melody preview adapter."""
from __future__ import annotations

from hiro_ust.ui.melody_preview import notes_from_output


def test_notes_from_ustx():
    output = """
voice_parts:
  - notes:
      - position: 0
        duration: 240
        tone: 60
        lyric: こ
      - position: 240
        duration: 480
        tone: 62
        lyric: こ
"""
    notes = notes_from_output(output, "ustx")
    assert [(n.position, n.duration, n.tone, n.lyric) for n in notes] == [
        (0, 240, 60, "こ"),
        (240, 480, 62, "こ"),
    ]


def test_notes_from_ust_skips_rests_but_preserves_positions():
    output = """[#SETTING]
Tempo=120.000

[#0000]
Length=120
Lyric=R

[#0001]
Length=240
NoteNum=60
Lyric=こ

[#0002]
Length=480
NoteNum=62
Lyric=ろ
"""
    notes = notes_from_output(output, "ust")
    assert [(n.position, n.duration, n.tone, n.lyric) for n in notes] == [
        (120, 240, 60, "こ"),
        (360, 480, 62, "ろ"),
    ]
