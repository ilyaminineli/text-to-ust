"""Single facade for Hiro's phrase-first and scored melody policies.

The two algorithms remain independently testable, but the processor uses one
interface for mode selection, scale/range enforcement and expressive offsets.
This provides a migration seam for gradually moving scoring features into the
phrase-first planner without maintaining two end-to-end generation pipelines.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from .melody_logic import MelodyBrain
from .phrase_engine import PhraseMelodyEngine
from .scale_utils import scale_pitch_classes, scale_note_pool
from .scales import SCALES


class MelodyEngine:
    """Unified interface over phrase planning and scored note selection."""

    def __init__(self, seed: int = 1234):
        self.seed = int(seed)
        self.reset()

    def reset(self) -> None:
        """Reset every random stream and musical memory to a reproducible seed."""
        self.phrase = PhraseMelodyEngine(seed=self.seed)
        self.scored = MelodyBrain(seed=self.seed)
        self.expression_rng = random.Random(self.seed + 31)

    @staticmethod
    def _is_vowel(phoneme: str) -> bool:
        return bool(phoneme) and phoneme[-1].lower() in "aeiou"

    def _constrain(
        self,
        pitches: Sequence[float],
        *,
        root_midi: int,
        scale_name: str,
        low: int,
        high: int,
        quartertone: bool,
    ) -> list[float]:
        pitch_classes = scale_pitch_classes(scale_name, root_midi)
        allowed = [
            note
            for note in range(int(low), int(high) + 1)
            if note % 12 in pitch_classes
        ]
        result = []
        for value in pitches:
            value = float(value)
            if not allowed:
                result.append(min(float(high), max(float(low), value)))
                continue
            anchor = int(round(value))
            nearest = min(allowed, key=lambda note: (abs(note - anchor), note))
            fraction = value - anchor if quartertone else 0.0
            candidate = nearest + fraction
            result.append(float(nearest if candidate < low or candidate > high else candidate))
        return result

    def generate(
        self,
        phonemes: Sequence[str],
        *,
        root_midi: int,
        scale_name: str,
        low: int,
        high: int,
        phrase_aware: bool = True,
        use_motifs: bool = True,
        flat_mode: bool = False,
        quartertone: bool = False,
        intone_level: str = "Medium (2)",
        chord_mode: bool = False,
        accent: str = "None",
    ) -> list[float]:
        """Generate one lyric unit using a selected policy and shared constraints."""
        units = list(phonemes)
        if not units:
            return []
        if scale_name not in SCALES:
            raise ValueError(f"Unsupported scale: {scale_name!r}")
        if int(low) > int(high):
            raise ValueError("low pitch bound must not exceed high pitch bound")

        if phrase_aware and len(units) == 1:
            # Avoid asking the phrase planner for a two-note placeholder and
            # silently discarding its second note for a one-mora lyric unit.
            pool = scale_note_pool(scale_name, int(root_midi), int(low), int(high))
            pitch = (
                min(pool, key=lambda note: (abs(note - (int(low) + int(high)) / 2), note))
                if pool
                else min(int(high), max(int(low), int(root_midi)))
            )
            if (
                quartertone
                and not flat_mode
                and self._is_vowel(units[0])
                and self.expression_rng.random() < 0.25
            ):
                pitch += self.expression_rng.choice((-0.5, 0.5))
            self.phrase.history.append(int(round(pitch)))
            return self._constrain(
                [pitch],
                root_midi=int(root_midi),
                scale_name=scale_name,
                low=int(low),
                high=int(high),
                quartertone=quartertone and not flat_mode,
            )

        if phrase_aware:
            plan = self.phrase.plan_phrase(
                max(2, len(units)),
                int((int(low) + int(high)) / 2),
                use_motifs=use_motifs,
            )
            pitches = self.phrase.render_phrase(
                plan,
                root=int(root_midi),
                scale=SCALES[scale_name],
                low=int(low),
                high=int(high),
                flat_mode=flat_mode,
                scale_name=scale_name,
            )
            if flat_mode:
                # Do not perturb a deliberately flat line with microtonal offsets.
                quartertone = False
            if quartertone:
                pitches = [
                    pitch + self.expression_rng.choice((-0.5, 0.5))
                    if self._is_vowel(unit) and self.expression_rng.random() < 0.25
                    else pitch
                    for unit, pitch in zip(units, pitches)
                ]
        else:
            self.scored.set_accent_pattern(accent, len(units))
            pitches = [
                self.scored.get_smart_note(
                    root_midi=int(root_midi),
                    scale_name=scale_name,
                    phoneme=unit,
                    intone_level=intone_level,
                    flat_mode=flat_mode,
                    quarter_tone=quartertone,
                    use_motifs=use_motifs,
                    chord_mode=chord_mode,
                    accent=accent,
                )
                for unit in units
            ]

        return self._constrain(
            pitches,
            root_midi=int(root_midi),
            scale_name=scale_name,
            low=int(low),
            high=int(high),
            quartertone=quartertone,
        )


__all__ = ["MelodyEngine"]
