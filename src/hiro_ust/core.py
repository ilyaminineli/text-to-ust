"""Public core API for Hiro UST."""
from __future__ import annotations

import random

from .config import GeneratorConfig, HiroConfig
from .converter import HiroUSTGenerator, Phonemizer
from .generator import USTWriter
from .generator.ustx_writer import USTXWriter
from .lyrics import LyricParser
from .melody import SCALES
from .melody.phrase_engine import PhraseMelodyEngine


class HiroUSTProcessor:
    """Parse -> furigana -> phonemize -> phrase melody -> serialize."""

    def __init__(self, config: GeneratorConfig | None = None):
        self.config = config or GeneratorConfig()
        self.generator = HiroUSTGenerator()
        self.phonemizer = Phonemizer()
        self.lyric_parser = LyricParser()
        self.melody = PhraseMelodyEngine(seed=self.config.seed)

    def process_lyrics(self, lyrics: str, project_name: str = "Hiro_Main", output_format: str = "ustx") -> str:
        if output_format not in {"ust", "ustx"}:
            raise ValueError("output_format must be 'ust' or 'ustx'")
        doc = self.lyric_parser.parse(lyrics, self.phonemizer)
        writer = USTWriter(project_name, self.config.tempo) if output_format == "ust" else USTXWriter(project_name, self.config.tempo)
        rng = random.Random(self.config.seed + 17)

        for section_index, section in enumerate(doc.sections):
            if section_index:
                writer.add_rest(self.config.base_length * 2)
            for line_index, line in enumerate(section.lines):
                if line_index or section_index:
                    writer.add_rest(self.config.base_length)
                for word_index, word in enumerate(line.words):
                    if word_index:
                        writer.add_rest(max(HiroConfig.MIN_NOTE_LEN, self.config.base_length // 2))
                    phonemes = [p for p in word.phonemes if p not in "。、！？,，…"]
                    if not phonemes:
                        continue
                    plan = self.melody.plan_phrase(
                        max(2, len(phonemes)),
                        int((self.config.range_low + self.config.range_high) / 2),
                    )
                    pitches = self.melody.render_phrase(
                        plan,
                        root=self.config.effective_root_key,
                        scale=SCALES[self.config.scale],
                        low=self.config.range_low,
                        high=self.config.range_high,
                    )
                    for phoneme, pitch in zip(phonemes, pitches):
                        length = self._note_length(phoneme, rng)
                        if phoneme == "っ":
                            writer.add_small_tsu(self.config.effective_root_key, length=min(60, length))
                        else:
                            writer.add_note(
                                length=length,
                                lyric=self.generator.romaji_to_hiragana(phoneme),
                                note_num=pitch,
                                pre_utter=self.config.pre_utterance,
                                voice_overlap=self.config.voice_overlap,
                                intensity=self.config.intensity_base,
                                envelope=self.config.envelope,
                            )
        return writer.finalize()

    def _note_length(self, phoneme: str, rng: random.Random) -> int:
        if phoneme == "っ":
            return 60
        char = phoneme[-1:] if phoneme else ""
        factor = 1.0 if char in "aeiou" else 0.65
        factor *= rng.uniform(1.0 - self.config.length_var * 0.35, 1.0 + self.config.length_var * 0.2)
        return max(HiroConfig.MIN_NOTE_LEN, min(HiroConfig.MAX_NOTE_LEN, int(self.config.base_length * factor)))

    def get_supported_scales(self) -> list[str]:
        return list(SCALES)


__all__ = ["HiroUSTProcessor", "GeneratorConfig"]
