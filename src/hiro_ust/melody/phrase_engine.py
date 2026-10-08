"""Phrase-first procedural melody engine.

The engine separates musical planning from note rendering:
1. choose a phrase contour;
2. build a small motif in scale degrees;
3. repeat/transform motifs;
4. resolve phrase endings;
5. expose note targets to the USTX writer.

This is intentionally deterministic for a given seed.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Sequence


@dataclass(frozen=True)
class MelodyPolicy:
    step_probability: float = 0.62
    repeat_probability: float = 0.12
    leap_probability: float = 0.16
    motif_probability: float = 0.45
    cadence_strength: float = 0.9
    contour_strength: float = 0.7
    syncopation: float = 0.15


@dataclass(frozen=True)
class PhrasePlan:
    contour: str
    length: int
    register: int
    intervals: tuple[int, ...]


class PhraseMelodyEngine:
    CONTOURS = ("arch", "rise", "fall", "wave", "late_peak")

    def __init__(self, seed: int = 1234, policy: MelodyPolicy | None = None):
        self.rng = random.Random(seed)
        self.policy = policy or MelodyPolicy()
        self.history: list[int] = []
        self.motifs: list[tuple[int, ...]] = []

    @staticmethod
    def _scale_notes(root: int, scale: Sequence[int], low: int, high: int) -> list[int]:
        pcs = {int(x) % 12 for x in scale}
        return [n for n in range(low, high + 1) if n % 12 in pcs]

    def _choose_contour(self, bias: float = 0.0) -> str:
        weights = {c: 1.0 for c in self.CONTOURS}
        if bias > 0:
            weights["rise"] += min(2.5, bias)
        if bias < 0:
            weights["fall"] += min(2.5, -bias)
        total = sum(weights.values())
        x = self.rng.random() * total
        for contour, weight in weights.items():
            x -= weight
            if x <= 0:
                return contour
        return "arch"

    def _contour(self, contour: str, i: int, length: int) -> float:
        x = i / max(1, length - 1)
        if contour == "rise":
            return x
        if contour == "fall":
            return 1 - x
        if contour == "wave":
            return 0.5 + 0.5 * math.sin(2 * math.pi * x - math.pi / 2)
        if contour == "late_peak":
            return math.sin(math.pi * (0.2 + 0.8 * x))
        return math.sin(math.pi * x)

    def _motif(self, length: int) -> tuple[int, ...]:
        steps = []
        for _ in range(max(1, length - 1)):
            r = self.rng.random()
            if r < self.policy.repeat_probability:
                step = 0
            elif r < self.policy.repeat_probability + self.policy.step_probability:
                step = self.rng.choice((-2, -1, 1, 2))
            else:
                step = self.rng.choice((-5, -4, 3, 4, 5))
            steps.append(step)
        return tuple(steps)

    def plan_phrase(
        self, length: int, register: int, contour_bias: float = 0.0
    ) -> PhrasePlan:
        length = max(2, int(length))
        contour = self._choose_contour(contour_bias)
        if self.motifs and self.rng.random() < self.policy.motif_probability:
            source = self.rng.choice(self.motifs)
            if len(source) == length - 1:
                intervals = source
            else:
                intervals = tuple(source[i % len(source)] for i in range(length - 1))
        else:
            intervals = self._motif(length)
        if intervals not in self.motifs:
            self.motifs.append(intervals)
            self.motifs = self.motifs[-12:]
        return PhrasePlan(contour, length, int(register), intervals)

    def render_phrase(
        self,
        plan: PhrasePlan,
        *,
        root: int,
        scale: Sequence[int],
        low: int,
        high: int,
    ) -> list[int]:
        pool = self._scale_notes(root, scale, low, high)
        if not pool:
            return [root] * plan.length

        current = min(pool, key=lambda n: abs(n - plan.register))
        result = []
        for i in range(plan.length):
            if i == 0:
                result.append(current)
                continue
            target = (
                plan.register + (self._contour(plan.contour, i, plan.length) - 0.5) * 10
            )
            desired = current + plan.intervals[i - 1]
            candidates = sorted(
                pool, key=lambda n: abs(n - target) + 0.55 * abs(n - desired)
            )
            window = candidates[: min(7, len(candidates))]
            current = self.rng.choice(window)
            result.append(current)

        # Cadence: favor tonic-ish ending, preferably by step.
        tonic_pc = int(scale[0]) % 12
        cadence = [n for n in pool if n % 12 == tonic_pc]
        if cadence:
            result[-1] = min(cadence, key=lambda n: abs(n - result[-2]))
        self.history.extend(result)
        return result


__all__ = ["MelodyPolicy", "PhraseMelodyEngine", "PhrasePlan"]
