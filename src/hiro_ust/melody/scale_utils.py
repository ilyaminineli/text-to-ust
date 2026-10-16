"""Shared scale interpretation for phrase planning and scored melody generation.

Generic scale names (for example Major Pentatonic) are intervals relative to
root_midi. Explicit key scales (for example D Major) keep their named tonic and
use root_midi only as a register anchor.
"""

from __future__ import annotations

from collections.abc import Sequence

from .scales import SCALES


KEYED_SCALE_NAMES = frozenset(
    f"{key} {mode}"
    for key in ("C", "D", "E", "F", "G", "A")
    for mode in ("Major", "Minor")
    if f"{key} {mode}" in SCALES
)


def scale_pitch_classes(
    scale_name: str,
    root_midi: int = 60,
    scales: dict[str, Sequence[int]] | None = None,
) -> frozenset[int]:
    """Return absolute pitch classes for a selected scale and root/register anchor."""
    available = SCALES if scales is None else scales
    try:
        values = tuple(int(value) % 12 for value in available[scale_name])
    except KeyError as exc:
        raise ValueError(f"Unsupported scale: {scale_name!r}") from exc
    if not values:
        raise ValueError(f"Scale {scale_name!r} has no pitch classes")

    if scale_name in KEYED_SCALE_NAMES:
        return frozenset(values)

    tonic = int(root_midi) % 12
    return frozenset((tonic + interval) % 12 for interval in values)


def scale_intervals(
    scale_name: str,
    root_midi: int = 60,
    scales: dict[str, Sequence[int]] | None = None,
) -> tuple[int, ...]:
    """Return scale offsets from root_midi, preserving tonic-first scale order."""
    available = SCALES if scales is None else scales
    try:
        values = tuple(int(value) % 12 for value in available[scale_name])
    except KeyError as exc:
        raise ValueError(f"Unsupported scale: {scale_name!r}") from exc
    if not values:
        raise ValueError(f"Scale {scale_name!r} has no pitch classes")

    root_pc = int(root_midi) % 12
    if scale_name in KEYED_SCALE_NAMES:
        return tuple((pitch_class - root_pc) % 12 for pitch_class in values)
    # Generic scale entries are intervals, already expressed relative to root.
    return values


def scale_tonic_pitch_class(
    scale_name: str,
    root_midi: int = 60,
    scales: dict[str, Sequence[int]] | None = None,
) -> int:
    """Return the scale's absolute tonic, using root_midi for generic modes."""
    available = SCALES if scales is None else scales
    try:
        values = tuple(int(value) % 12 for value in available[scale_name])
    except KeyError as exc:
        raise ValueError(f"Unsupported scale: {scale_name!r}") from exc
    if not values:
        raise ValueError(f"Scale {scale_name!r} has no pitch classes")
    if scale_name in KEYED_SCALE_NAMES:
        return values[0]
    return int(root_midi) % 12


def scale_note_pool(
    scale_name: str,
    root_midi: int,
    low: int,
    high: int,
    scales: dict[str, Sequence[int]] | None = None,
) -> list[int]:
    """Return sorted MIDI notes inside a range that belong to the resolved scale."""
    if low > high:
        return []
    pitch_classes = scale_pitch_classes(scale_name, root_midi, scales)
    return [
        note
        for note in range(int(low), int(high) + 1)
        if note % 12 in pitch_classes
    ]


__all__ = [
    "KEYED_SCALE_NAMES",
    "scale_pitch_classes",
    "scale_intervals",
    "scale_tonic_pitch_class",
    "scale_note_pool",
]
