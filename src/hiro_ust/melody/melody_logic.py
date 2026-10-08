"""Phrase-aware procedural melody generation.

The generator is intentionally controlled: GUI parameters are treated as real
constraints/weights, while the seed supplies variation inside those constraints.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Sequence

import numpy as np

from ..constants import VOWEL_CHARS, CONSONANT_CHARS
from .intone_utils import get_intone_settings
from .scales import SCALES

# Voice roots used by the GUI. The values describe a comfortable relative
# melodic span around each voice's root, not a strict vocal range database.
VOICE_RANGE_BY_ROOT = {
    67: 15.0,  # Soprano
    60: 14.0,  # Alto
    55: 13.0,  # Tenor
    52: 12.0,  # Baritone
    48: 11.0,  # Bass
}


class NoteMarkov:
    """Small pitch-class transition model used only as a weak suggestion."""

    def __init__(self, order: int = 1, rng: np.random.Generator | None = None):
        self.order = max(1, int(order))
        self.transitions: dict[tuple[tuple[int, ...], int], np.ndarray] = {}
        self.rng = rng or np.random.default_rng()

    def train(self, notes: Sequence[float], stresses: Sequence[int]) -> None:
        if len(notes) != len(stresses) or len(notes) <= self.order:
            return
        counts = defaultdict(lambda: np.zeros(12, dtype=float))
        for i in range(len(notes) - self.order):
            state = tuple(int(round(n)) % 12 for n in notes[i : i + self.order])
            stress = int(stresses[i + self.order])
            target = int(round(notes[i + self.order])) % 12
            counts[(state, stress)][target] += 1.0
        self.transitions = dict(counts)

    def next_note(
        self, state: Sequence[float], stress: int, scale: Sequence[int]
    ) -> int | None:
        if not self.transitions:
            return None
        key = (tuple(int(round(n)) % 12 for n in state[-self.order :]), int(stress))
        probs = self.transitions.get(key)
        if probs is None:
            return None
        allowed = np.zeros(12, dtype=bool)
        for pitch_class in scale:
            allowed[int(pitch_class) % 12] = True
        probs = probs.copy()
        probs[~allowed] *= 0.15
        total = float(probs.sum())
        if total <= 0:
            return None
        probs /= total
        return int(self.rng.choice(np.arange(12), p=probs))


class MotifMemory:
    """Store interval patterns so motifs can recur in another register."""

    def __init__(
        self,
        motif_length: int = 4,
        max_motifs: int = 8,
        rng: random.Random | None = None,
    ):
        self.motif_length = max(2, int(motif_length))
        self.max_motifs = max(1, int(max_motifs))
        self.stored_motifs: list[list[int]] = []
        self.rng = rng or random.Random()

    def add_motif(self, notes: Sequence[float]) -> None:
        if len(notes) < self.motif_length:
            return
        values = [int(round(n)) for n in notes[-self.motif_length :]]
        intervals = [values[i + 1] - values[i] for i in range(len(values) - 1)]
        if not any(intervals) and self.stored_motifs:
            return
        if intervals not in self.stored_motifs:
            self.stored_motifs.append(intervals)
            self.stored_motifs = self.stored_motifs[-self.max_motifs :]

    def choose(self) -> list[int] | None:
        if not self.stored_motifs:
            return None
        return list(self.rng.choice(self.stored_motifs))

    def debug_motifs(self) -> str:
        if not self.stored_motifs:
            return "No motifs stored"
        return " | ".join(
            f"[{','.join(map(str, motif))}]" for motif in self.stored_motifs
        )


class MelodyBrain:
    """Generate melodic phrases with explicit, controllable musical behavior."""

    _intone_cache: dict[str, dict] = {}

    CONTOURS = ("arch", "rise", "fall", "late_peak", "wave", "answer", "pendulum")

    def __init__(self, seed: int | None = None):
        self.seed = 1234 if seed is None else int(seed)
        self.rng = random.Random(self.seed)
        self.np_rng = np.random.default_rng(self.seed + 101)

        self.last_note = 5.0
        self.note_history: list[float] = []
        self.recent_notes: list[float] = []
        self.phrases: list[float] = []
        self.phrase_len = 0

        self.VOWEL_CHARS = VOWEL_CHARS
        self.CONSONANT_CHARS = CONSONANT_CHARS

        self.word_morae: list[int] = []
        self.word_pos = 0
        self.pitch_drop_pos = 0
        self.is_high_pitch = False
        self.prev_high_pitch = False

        self.markov = NoteMarkov(order=1, rng=self.np_rng)
        self.motif_memory = MotifMemory(rng=self.rng)

        self._phrase_start = True
        self._phrase_length = 8
        self._phrase_style = "arch"
        self._phrase_register = 6.0
        self._phrase_span = 10.0
        self._phrase_index = 0
        self._previous_direction = 0
        self._active_motif: list[int] | None = None
        self._motif_index = 0
        self._voice_root = 60
        self._effective_range = 14.0

    def _is_vowel(self, phoneme: str) -> bool:
        if not phoneme:
            return False
        if phoneme in VOWEL_CHARS:
            return True
        return phoneme[-1].lower() in "aeiou"

    def train_markov(
        self, phonemes: Sequence[str], notes: Sequence[float] | None = None
    ) -> None:
        notes = list(self.note_history[-32:] if notes is None else notes)
        phonemes = list(phonemes)[-len(notes) :]
        if len(notes) < 3 or len(phonemes) != len(notes):
            return
        stresses = [int(self._is_vowel(p)) for p in phonemes]
        self.markov.train(notes, stresses)

    def set_accent_pattern(self, pattern: str, word_length: int) -> None:
        self.word_morae = list(range(max(0, int(word_length))))
        self.word_pos = 0
        if pattern == "Heiban":
            self.pitch_drop_pos, self.is_high_pitch = 999, True
        elif pattern == "Atamadaka":
            self.pitch_drop_pos, self.is_high_pitch = 1, True
        elif pattern == "Nakadaka":
            self.pitch_drop_pos, self.is_high_pitch = (
                max(2, int(word_length) // 2),
                True,
            )
        elif pattern == "Odaka":
            self.pitch_drop_pos, self.is_high_pitch = 999, False
        else:
            self.pitch_drop_pos, self.is_high_pitch = 0, False

    def _start_phrase(
        self,
        settings: dict,
        contour_bias: float,
        pitch_range_control: float,
        root_midi: int,
    ) -> None:
        self._voice_root = int(root_midi)
        base_range = VOICE_RANGE_BY_ROOT.get(int(root_midi), 14.0)
        control = max(0.4, min(1.7, float(pitch_range_control) / 70.0))
        self._effective_range = max(8.0, min(24.0, base_range * control))

        self._phrase_length = max(4, int(settings["phrase"]))
        self._phrase_index = len(self.phrases)
        self._phrase_start = False
        self._motif_index = 0
        self._active_motif = None

        # Curve is a bias, not a hard contour. Strong positive/negative settings
        # make rise/fall substantially more likely while retaining variety.
        bias = max(-1.0, min(1.0, float(contour_bias) / 50.0))
        weights = {
            "arch": 1.5,
            "rise": 1.0 + max(0.0, bias) * 2.2,
            "fall": 1.0 + max(0.0, -bias) * 2.2,
            "late_peak": 1.1,
            "wave": 1.1,
            "answer": 0.8,
            "pendulum": 0.7,
        }
        total = sum(weights.values())
        marker = self.rng.random() * total
        running = 0.0
        for style, weight in weights.items():
            running += weight
            if marker <= running:
                self._phrase_style = style
                break

        # Keep the register voice-specific. Different voices should not merely be
        # transpositions of the same wide MIDI area.
        center = self._effective_range * 0.52
        register_shift = self.rng.uniform(-1.8, 1.8)
        if self._phrase_index > 0:
            register_shift += self.rng.choice([-2.0, -1.0, 0.0, 1.0, 2.0])
        self._phrase_register = max(
            2.0, min(self._effective_range - 2.0, center + register_shift)
        )
        self._phrase_span = max(5.0, min(self._effective_range * 0.72, 12.0))

    def _contour_target(self, position: float) -> float:
        x = max(0.0, min(1.0, position))
        style = self._phrase_style
        if style == "rise":
            shape = x
        elif style == "fall":
            shape = 1.0 - x
        elif style == "late_peak":
            shape = math.sin(math.pi * (x * 0.78))
        elif style == "wave":
            shape = 0.5 + 0.5 * math.sin(2.0 * math.pi * x - math.pi / 2)
        elif style == "answer":
            shape = 0.38 + 0.28 * math.sin(math.pi * x)
        elif style == "pendulum":
            shape = 0.5 + 0.5 * math.sin(3.0 * math.pi * x)
        else:
            shape = math.sin(math.pi * x)
        return max(
            0.0,
            min(
                self._effective_range,
                self._phrase_register + (shape - 0.5) * self._phrase_span,
            ),
        )

    @staticmethod
    def _scale_candidates(scale: Sequence[int], maximum: float) -> list[int]:
        pcs = {int(x) % 12 for x in scale}
        upper = max(1, int(math.floor(maximum)))
        return [offset for offset in range(upper + 1) if offset % 12 in pcs]

    def _candidate_pool(
        self, scale: Sequence[int], settings: dict, target: float, is_vowel: bool
    ) -> list[int]:
        scale_candidates = self._scale_candidates(scale, self._effective_range)
        if not scale_candidates:
            return [int(round(self.last_note))]

        # Intone is a real movement constraint. Tight cannot secretly produce
        # Wild-style leaps because of an out-of-range contour target.
        normal_leap = int(settings["leap"])
        expanded_leap = int(settings.get("large_leap", 0))
        allow_large = expanded_leap > normal_leap and self.rng.random() < float(
            settings.get("large_leap_prob", 0.0)
        )
        allowed_leap = expanded_leap if allow_large else normal_leap

        local = [n for n in scale_candidates if abs(n - self.last_note) <= allowed_leap]
        if not local:
            nearest = min(scale_candidates, key=lambda n: abs(n - self.last_note))
            local = [nearest]

        # Add target-nearest tones only inside the intone limit.
        target_notes = sorted(scale_candidates, key=lambda n: abs(n - target))
        for note in target_notes:
            if abs(note - self.last_note) <= allowed_leap and note not in local:
                local.append(note)
            if len(local) >= 9:
                break

        # Vowels are melodic anchors: allow one additional nearby target when
        # intone permits it, but never violate the chosen maximum leap.
        if is_vowel:
            for note in target_notes[:3]:
                if abs(note - self.last_note) <= allowed_leap and note not in local:
                    local.append(note)

        return sorted(set(local))

    def _score_candidate(
        self,
        candidate: int,
        target: float,
        settings: dict,
        phrase_pos: float,
        is_vowel: bool,
        is_stretch: bool,
        chord_mode: bool,
        scale: Sequence[int],
        contour_bias: float,
        cadence: bool,
        markov_note: int | None,
    ) -> float:
        motion = candidate - self.last_note
        distance = abs(candidate - target)
        abs_motion = abs(motion)
        score = -1.6 * distance

        # Core intone feel.
        if abs_motion == 0:
            score += float(settings.get("repeat", 0.25)) * 4.0
        elif abs_motion <= 2:
            score += 3.5
        elif abs_motion <= 4:
            score += 2.0
        elif abs_motion <= 6:
            score += 0.7
        else:
            score -= 0.8

        # Repetition becomes attractive for Tight, but not endlessly.
        if len(self.note_history) >= 2 and candidate == int(
            round(self.note_history[-1])
        ) == int(round(self.note_history[-2])):
            score -= 2.7

        # Leap resolution.
        if (
            len(self.note_history) >= 1
            and abs(self.note_history[-1] - self.last_note) >= 4
        ):
            if motion * self._previous_direction < 0:
                score += 2.4
            elif motion * self._previous_direction > 0:
                score -= 1.2

        if is_vowel:
            score += 0.8
        else:
            score -= 0.35 * max(0, abs_motion - 2)
        if is_stretch:
            score += 1.2 if candidate == int(round(self.last_note)) else -0.6

        # Phrase shape.
        score += -0.65 * distance
        if contour_bias:
            wanted = 1 if contour_bias > 0 else -1
            strength = min(abs(float(contour_bias)) / 20.0, 2.5)
            if motion * wanted > 0:
                score += strength
            elif motion * wanted < 0:
                score -= strength * 0.25

        # Cadence = strong stability. In this engine the first scale degree is
        # the tonic relative to the selected root.
        if cadence:
            pcs = [int(x) % 12 for x in scale]
            pc = candidate % 12
            if pcs and pc == pcs[0]:
                score += 5.2
            elif pcs and pc in pcs[: min(3, len(pcs))]:
                score += 1.8
            score -= abs_motion * 0.55

        if chord_mode:
            beat = self.phrase_len % 8
            chord_root = 0 if beat not in {3, 5} else (5 if beat == 3 else 7)
            tones = {(chord_root + i) % 12 for i in (0, 4, 7)}
            score += 2.4 if candidate % 12 in tones else -0.55

        if markov_note is not None:
            # Weak learned prior; it cannot override contour or intone.
            score -= 0.12 * abs((candidate % 12) - markov_note)

        # Accent affects register emphasis without forcing a pitch class.
        if self.is_high_pitch:
            score += 0.7 if candidate >= target else -0.1
        elif self.pitch_drop_pos:
            score += 0.45 if candidate <= target else -0.05

        return score

    def get_smart_note(
        self,
        root_midi,
        scale_name,
        phoneme,
        intone_level="Tight (1)",
        flat_mode=False,
        quarter_tone=False,
        use_motifs=True,
        chord_mode=False,
        contour_bias=0,
        pitch_range=70,
        accent="None",
    ):
        scale = SCALES[scale_name]
        settings = self._intone_cache.setdefault(
            intone_level, get_intone_settings(intone_level)
        )

        if self._phrase_start or self.phrase_len == 0:
            self._start_phrase(settings, contour_bias, pitch_range, int(root_midi))

        self.phrase_len += 1
        phrase_pos = min(1.0, (self.phrase_len - 1) / max(1, self._phrase_length - 1))
        target = self._contour_target(phrase_pos)
        is_vowel = self._is_vowel(phoneme)
        is_stretch = phoneme == "+"
        cadence = self.phrase_len >= max(1, self._phrase_length - 1)

        # Motif continuation is a suggestion layered onto the candidate score.
        if (
            use_motifs
            and self._active_motif is None
            and self.motif_memory.stored_motifs
        ):
            trigger = 0.22 if self._phrase_index > 0 else 0.08
            if self.rng.random() < trigger:
                self._active_motif = self.motif_memory.choose()
                self._motif_index = 0

        motif_target = None
        if (
            use_motifs
            and self._active_motif
            and self._motif_index < len(self._active_motif)
        ):
            motif_target = self.last_note + self._active_motif[self._motif_index]

        candidates = self._candidate_pool(scale, settings, target, is_vowel)
        markov_note = self.markov.next_note(
            self.note_history[-1:], int(is_vowel), scale
        )

        scored: list[tuple[float, int]] = []
        for candidate in candidates:
            score = self._score_candidate(
                candidate,
                target,
                settings,
                phrase_pos,
                is_vowel,
                is_stretch,
                chord_mode,
                scale,
                contour_bias,
                cadence,
                markov_note,
            )
            if motif_target is not None:
                score += max(-2.5, 3.0 - 0.7 * abs(candidate - motif_target))
            scored.append((score, candidate))

        scored.sort(reverse=True)
        top_n = min(5, len(scored))
        top = scored[:top_n]
        temperature = max(0.12, float(settings.get("temperature", 0.5)))
        # Controlled randomness: lower intone = more deterministic, Wild = more
        # adventurous among the best musical candidates.
        weights = [math.exp((score - top[0][0]) / temperature) for score, _ in top]
        chosen = self.rng.choices([note for _, note in top], weights=weights, k=1)[0]

        # The active motif advances only when its candidate is actually close.
        if motif_target is not None:
            if abs(chosen - motif_target) <= 2.0:
                self._motif_index += 1
            if self._motif_index >= len(self._active_motif or []):
                self._active_motif = None
                self._motif_index = 0

        if quarter_tone and is_vowel and self.rng.random() < 0.25:
            chosen += self.rng.choice([0.5, -0.5])

        if flat_mode:
            # Flat mode is now truly flat while preserving the voice root.
            chosen = min(
                self._scale_candidates(scale, self._effective_range),
                key=lambda n: abs(n - self._phrase_register),
            )

        chosen = max(0.0, min(self._effective_range, float(chosen)))
        self.prev_high_pitch = self.is_high_pitch

        self.word_pos += 1
        if self.word_pos >= self.pitch_drop_pos:
            self.is_high_pitch = False
        if phoneme in "。！？,，、" or (
            self.word_morae and self.word_pos >= len(self.word_morae)
        ):
            self.word_pos = 0
            self.is_high_pitch = False

        if chosen > self.last_note:
            self._previous_direction = 1
        elif chosen < self.last_note:
            self._previous_direction = -1
        else:
            self._previous_direction = 0

        self.last_note = chosen
        self.note_history.append(chosen)
        self.recent_notes.append(chosen)
        if len(self.recent_notes) > 8:
            self.recent_notes.pop(0)

        if len(self.note_history) >= 4:
            self.motif_memory.add_motif(self.note_history)
            self.train_markov(
                [phoneme] * min(len(self.note_history), 32), self.note_history[-32:]
            )

        if cadence or phoneme in "。！？":
            self.phrases.append(self.last_note)
            self._phrase_start = True
            self.phrase_len = 0
            self._active_motif = None
            self._motif_index = 0

        return max(0.0, min(127.0, float(root_midi) + self.last_note))

    def get_intensity(self, note_height, phrase_progress):
        distance = abs(float(note_height) - self._phrase_register)
        base = 78 + int(min(18.0, distance * 0.6))
        if phrase_progress > 0.82:
            base += 8
        if phrase_progress < 0.12:
            base -= 3
        return max(50, min(120, base))


__all__ = ["MelodyBrain", "NoteMarkov", "MotifMemory", "VOICE_RANGE_BY_ROOT"]
