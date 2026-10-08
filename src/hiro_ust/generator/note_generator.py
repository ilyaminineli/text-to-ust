"""Note-level generation and pitch-bend utilities."""

import random
from typing import List, Optional, Tuple

from ..config import HiroConfig
from ..constants import VOWEL_CHARS, CONSONANT_CHARS
from ..melody.intone_utils import get_intone_settings
from ..melody.scales import SCALES


class NoteGenerator:
    def __init__(
        self, base_length: int = 240, length_var: float = 0.3, seed: int | None = None
    ):
        self.base_length = int(base_length)
        self.length_var = float(length_var)
        self.rng = random.Random(seed)
        self.vowel_chars = VOWEL_CHARS
        self.consonant_chars = CONSONANT_CHARS

    def get_note_length(
        self,
        phoneme: str,
        length_factor: float = 1.0,
        melody_brain: Optional[object] = None,
    ) -> int:
        if phoneme == "+":
            factor = 0.6
        else:
            vowel_chars = (
                getattr(melody_brain, "VOWEL_CHARS", self.vowel_chars)
                if melody_brain
                else self.vowel_chars
            )
            consonant_chars = (
                getattr(melody_brain, "CONSONANT_CHARS", self.consonant_chars)
                if melody_brain
                else self.consonant_chars
            )
            first = phoneme[0] if phoneme else "a"
            if first in vowel_chars:
                factor = 1.0 + self.rng.uniform(-self.length_var, self.length_var * 0.3)
            elif first in consonant_chars:
                factor = 0.5 + self.rng.uniform(0, self.length_var * 1.5)
            else:
                factor = 0.7 + self.rng.uniform(
                    -self.length_var * 0.2, self.length_var * 0.2
                )

        length = int(self.base_length * factor * length_factor)
        return max(HiroConfig.MIN_NOTE_LEN, min(HiroConfig.MAX_NOTE_LEN, length))

    def get_random_pitch(
        self,
        root_key: int,
        scale_name: str,
        intone_level: str = "Medium (2)",
        flat_mode: bool = False,
        quartertone_mode: bool = False,
        use_motifs: bool = True,
        chord_mode: bool = False,
    ) -> float:
        scale = SCALES.get(scale_name, SCALES["Major"])
        if flat_mode:
            return root_key + 5

        base_semitone = self.rng.choice(scale)
        if use_motifs:
            recent = getattr(self, "_recent_notes", [])
            if recent:
                base_semitone = min(scale, key=lambda x: abs(x - (recent[-1] % 12)))
            recent.append(base_semitone)
            self._recent_notes = recent[-4:]

        settings = get_intone_settings(intone_level)
        if chord_mode:
            chord_root = self.rng.choice([0, 3, 5])
            chord = [
                n for n in ((chord_root + i) % 12 for i in [0, 4, 7]) if n in scale
            ]
            base_semitone = self.rng.choice(chord or scale)

        if settings["leap"] < 3:
            base_semitone = min(base_semitone, settings["leap"] * 2)

        if quartertone_mode and self.rng.random() < 0.5:
            base_semitone += self.rng.choice([0, 0.5, -0.5])
        return root_key + base_semitone

    def create_stretch_notes(
        self,
        phoneme: str,
        stretch_prob: float = 0.25,
        max_stretch: int = 3,
        melody_brain: Optional[object] = None,
    ) -> List[Tuple[str, float]]:
        vowel_chars = (
            getattr(melody_brain, "VOWEL_CHARS", self.vowel_chars)
            if melody_brain
            else self.vowel_chars
        )
        if len(phoneme) >= 2 and phoneme[0] == phoneme[1] and phoneme[0] in vowel_chars:
            return [(phoneme[0], 1.8)]
        if (
            len(phoneme) == 1
            and phoneme in vowel_chars
            and self.rng.random() < (stretch_prob + 0.5)
        ):
            stretches = self.rng.randint(1, max(0, max_stretch))
            return [(phoneme, 1.2)] + [("+", 0.6)] * stretches
        return [(phoneme, 1.0)]


class PitchBendCalculator:
    @staticmethod
    def calculate_quartertone_bend(note_num: float) -> Tuple[str, str]:
        fraction = note_num - int(note_num)
        if abs(fraction) < 1e-9:
            return "0;0", "0"
        # UTAU pitch bend is expressed relative to the integer MIDI note.
        # PBS=50 gives 100 cents over 50 bend units, so a quarter-tone is 25.
        bend_amount = int(round(fraction * HiroConfig.PBS_SCALE))
        return f"0;{bend_amount}", "10"

    @staticmethod
    def calculate_accent_bend(
        melody_brain: object, note_length: int, accent: str
    ) -> Tuple[str, str, str, str]:
        pbs, pbw, pby, pbm = "0;0", "0", "0", ","
        if getattr(melody_brain, "is_high_pitch", False) is False and getattr(
            melody_brain, "prev_high_pitch", False
        ):
            drop_strength = random.choice([-50, -40, -35, -30, -25])
            pbs = f"0;{drop_strength}"
            if note_length > 200:
                pbw = f"25,50,{int(note_length * 0.15)}"
                pby = "-15,-15,0"
        elif accent == "Odaka" and getattr(melody_brain, "word_pos", 0) == 2:
            pbs = f"0;{random.choice([25, 35, 45])}"
            pbw = "20"
        elif getattr(melody_brain, "word_pos", 0) == 1 and getattr(
            melody_brain, "is_high_pitch", False
        ):
            pbs = f"0;{random.choice([15, 20])}"
        return pbs, pbw, pby, pbm


class EnvelopeCalculator:
    @staticmethod
    def calculate_intensity(
        melody_brain: object,
        intensity_base: int,
        note_position: int = 0,
        phrase_length: int = 12,
    ) -> int:
        phrase_progress = note_position / max(1, phrase_length)
        note_height = getattr(melody_brain, "last_note", 0)
        melody_offset = melody_brain.get_intensity(note_height, phrase_progress)
        return int(
            max(
                HiroConfig.RENDER_INTENSITY_MIN,
                min(
                    HiroConfig.RENDER_INTENSITY_MAX, intensity_base + melody_offset - 80
                ),
            )
        )


__all__ = ["NoteGenerator", "PitchBendCalculator", "EnvelopeCalculator"]
