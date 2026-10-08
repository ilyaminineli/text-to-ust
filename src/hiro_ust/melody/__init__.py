"""Melody generation package."""

from .melody_logic import MelodyBrain, MotifMemory, NoteMarkov, VOICE_RANGE_BY_ROOT
from .phrase_engine import MelodyPolicy, PhraseMelodyEngine, PhrasePlan
from .scales import SCALES
from .intone_utils import get_intone_settings
from .envelopes import ENVELOPE_PRESETS

__all__ = [
    "MelodyBrain",
    "MotifMemory",
    "NoteMarkov",
    "VOICE_RANGE_BY_ROOT",
    "MelodyPolicy",
    "PhraseMelodyEngine",
    "PhrasePlan",
    "SCALES",
    "get_intone_settings",
    "ENVELOPE_PRESETS",
]
