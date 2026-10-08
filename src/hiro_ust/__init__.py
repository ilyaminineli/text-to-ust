"""Public package API for Hiro UST."""

__version__ = "0.4.0"
__author__ = "Ilya Minin (Eli)"

from .core import HiroUSTProcessor
from .config import GeneratorConfig, HiroConfig
from .melody.phrase_engine import MelodyPolicy, PhraseMelodyEngine, PhrasePlan
from .melody import MelodyBrain, SCALES

__all__ = [
    "__version__",
    "__author__",
    "HiroUSTProcessor",
    "GeneratorConfig",
    "HiroConfig",
    "MelodyPolicy",
    "PhraseMelodyEngine",
    "PhrasePlan",
    "MelodyBrain",
    "SCALES",
]
