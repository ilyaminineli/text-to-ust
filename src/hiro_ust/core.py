"""Public core API for Hiro UST."""

from __future__ import annotations

import random

from .config import GeneratorConfig, HiroConfig
from .converter import HiroUSTGenerator, Phonemizer
from .generator import USTWriter
from .generator.ustx_writer import USTXWriter
from .lyrics import LyricParser
from .melody import SCALES, MelodyBrain
from .melody.phrase_engine import PhraseMelodyEngine

PUNCTUATION = frozenset("。、！？!?，,…")


class HiroUSTProcessor:
    """Parse -> furigana -> phonemize -> phrase melody -> serialize."""

    def __init__(self, config: GeneratorConfig | None = None):
        self.config = config or GeneratorConfig()
        self.generator = HiroUSTGenerator()
        self.phonemizer = Phonemizer()
        self.lyric_parser = LyricParser()
        self._reset_engines()

    def _reset_engines(self) -> None:
        self.melody = PhraseMelodyEngine(seed=self.config.seed)
        self.scored_melody = MelodyBrain(seed=self.config.seed)

    def process_lyrics(
        self, lyrics: str, project_name: str = "Hiro_Main", output_format: str = "ustx"
    ) -> str:
        if output_format not in {"ust", "ustx"}:
            raise ValueError("output_format must be 'ust' or 'ustx'")

        # Reset state so repeated calls on one processor remain deterministic.
        self._reset_engines()
        doc = self.lyric_parser.parse(lyrics, self.phonemizer)
        writer = (
            USTWriter(project_name, self.config.tempo)
            if output_format == "ust"
            else USTXWriter(project_name, self.config.tempo)
        )
        timing_rng = random.Random(self.config.seed + 17)
        expression_rng = random.Random(self.config.seed + 31)

        for section_index, section in enumerate(doc.sections):
            if section_index:
                writer.add_rest(self.config.base_length * 2)
            for line_index, line in enumerate(section.lines):
                if line_index or section_index:
                    writer.add_rest(self.config.base_length)
                for word_index, word in enumerate(line.words):
                    if word_index:
                        writer.add_rest(
                            max(HiroConfig.MIN_NOTE_LEN, self.config.base_length // 2)
                        )
                    phonemes = [
                        phoneme
                        for phoneme in word.phonemes
                        if phoneme not in PUNCTUATION
                    ]
                    if not phonemes:
                        continue

                    pitches = self._generate_pitches(phonemes, expression_rng)
                    for phoneme, pitch in zip(phonemes, pitches):
                        length = self._note_length(phoneme, timing_rng)
                        if phoneme == "っ":
                            writer.add_small_tsu(
                                self.config.effective_root_key, length=min(60, length)
                            )
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

    def _generate_pitches(self, phonemes: list[str], rng: random.Random) -> list[float]:
        if not phonemes:
            return []

        if not self.config.lyrical_mode:
            # Keep the scored melody policy available through the same parser,
            # serializer, range constraints, and deterministic timing pipeline.
            self.scored_melody.set_accent_pattern(self.config.accent, len(phonemes))
            pitches = [
                self.scored_melody.get_smart_note(
                    root_midi=self.config.effective_root_key,
                    scale_name=self.config.scale,
                    phoneme=phoneme,
                    intone_level=self.config.intone_level,
                    flat_mode=self.config.flat_mode,
                    quarter_tone=self.config.quartertone_mode,
                    use_motifs=self.config.use_motifs,
                    chord_mode=self.config.chord_mode,
                    accent=self.config.accent,
                )
                for phoneme in phonemes
            ]
            return [self._constrain_pitch(pitch) for pitch in pitches]

        plan = self.melody.plan_phrase(
            max(2, len(phonemes)),
            int((self.config.range_low + self.config.range_high) / 2),
            use_motifs=self.config.use_motifs,
        )
        pitches = self.melody.render_phrase(
            plan,
            root=self.config.effective_root_key,
            scale=SCALES[self.config.scale],
            low=self.config.range_low,
            high=self.config.range_high,
            flat_mode=self.config.flat_mode,
        )

        if self.config.quartertone_mode:
            pitches = [
                pitch + rng.choice((-0.5, 0.5))
                if self._is_vowel(phoneme) and rng.random() < 0.25
                else pitch
                for phoneme, pitch in zip(phonemes, pitches)
            ]
        return [self._constrain_pitch(pitch) for pitch in pitches]

    def _constrain_pitch(self, pitch: float) -> float:
        """Keep pitches inside the configured range and selected scale."""
        value = float(pitch)
        pitch_classes = {int(step) % 12 for step in SCALES[self.config.scale]}
        allowed = [
            note
            for note in range(self.config.range_low, self.config.range_high + 1)
            if note % 12 in pitch_classes
        ]
        if not allowed:
            return min(float(self.config.range_high), max(float(self.config.range_low), value))

        anchor = int(round(value))
        nearest = min(allowed, key=lambda note: (abs(note - anchor), note))
        fraction = value - anchor if self.config.quartertone_mode else 0.0
        candidate = nearest + fraction
        if candidate < self.config.range_low or candidate > self.config.range_high:
            return float(nearest)
        return float(candidate)

    @staticmethod
    def _is_vowel(phoneme: str) -> bool:
        return bool(phoneme) and phoneme[-1].lower() in "aeiou"

    def _note_length(self, phoneme: str, rng: random.Random) -> int:
        if phoneme == "っ":
            return 60
        char = phoneme[-1:].lower() if phoneme else ""
        factor = 1.0 if char in "aeiou" else 0.65
        factor *= rng.uniform(
            1.0 - self.config.length_var * 0.35,
            1.0 + self.config.length_var * 0.2,
        )
        # Stretch vowel-bearing morae probabilistically rather than every note.
        if char in "aeiou" and rng.random() < self.config.stretch_prob:
            factor *= rng.uniform(1.35, 1.9)
        return max(
            HiroConfig.MIN_NOTE_LEN,
            min(HiroConfig.MAX_NOTE_LEN, int(self.config.base_length * factor)),
        )

    def get_supported_scales(self) -> list[str]:
        return list(SCALES)


__all__ = ["HiroUSTProcessor", "GeneratorConfig"]
