"""Configuration and validated runtime settings for Hiro UST."""
from dataclasses import dataclass


class HiroConfig:
    MIN_TEMPO = 60.0
    MAX_TEMPO = 240.0
    MIN_NOTE_LEN = 120
    MAX_NOTE_LEN = 1920
    MIN_LENGTH_VAR = 0.0
    MAX_LENGTH_VAR = 1.0
    MIN_STRETCH = 0.0
    MAX_STRETCH = 1.0
    MIN_PRE_UTTER = 0
    MAX_PRE_UTTER = 200
    MIN_VOICE_OVERLAP = 0
    MAX_VOICE_OVERLAP = 100
    MIN_INTENSITY = 30
    MAX_INTENSITY = 150
    PBS_SCALE = 50


@dataclass
class GeneratorConfig:
    tempo: float = 120.0
    base_length: int = 240
    root_key: int = 60
    range_low: int = 48
    range_high: int = 76
    voice: str = "C4 Default"
    scale: str = "Major Pentatonic"
    intone_level: str = "Medium (2)"
    length_var: float = 0.3
    stretch_prob: float = 0.25
    pre_utterance: int = 25
    voice_overlap: int = 10
    intensity_base: int = 80
    envelope: str = "Pop"
    flat_mode: bool = False
    quartertone_mode: bool = False
    lyrical_mode: bool = True
    use_motifs: bool = True
    chord_mode: bool = False
    accent: str = "None"
    seed: int = 1234

    def __post_init__(self) -> None:
        self.tempo = float(self.tempo)
        self.base_length = int(self.base_length)
        self.root_key = int(self.root_key)
        self.range_low = int(self.range_low)
        self.range_high = int(self.range_high)
        self.length_var = float(self.length_var)
        self.stretch_prob = float(self.stretch_prob)
        self.pre_utterance = int(self.pre_utterance)
        self.voice_overlap = int(self.voice_overlap)
        self.intensity_base = int(self.intensity_base)
        self.seed = int(self.seed)

        if not HiroConfig.MIN_TEMPO <= self.tempo <= HiroConfig.MAX_TEMPO:
            raise ValueError("tempo is outside the supported range")
        if not HiroConfig.MIN_NOTE_LEN <= self.base_length <= HiroConfig.MAX_NOTE_LEN:
            raise ValueError("base_length is outside the supported range")
        if not 0 <= self.root_key <= 127:
            raise ValueError("root_key must be between 0 and 127")
        if not 0 <= self.range_low < self.range_high <= 127:
            raise ValueError("range_low/range_high must be valid MIDI bounds")
        if not HiroConfig.MIN_LENGTH_VAR <= self.length_var <= HiroConfig.MAX_LENGTH_VAR:
            raise ValueError("length_var must be between 0 and 1")
        if not HiroConfig.MIN_STRETCH <= self.stretch_prob <= HiroConfig.MAX_STRETCH:
            raise ValueError("stretch_prob must be between 0 and 1")
        if not HiroConfig.MIN_PRE_UTTER <= self.pre_utterance <= HiroConfig.MAX_PRE_UTTER:
            raise ValueError("pre_utterance is outside the supported range")
        if not HiroConfig.MIN_VOICE_OVERLAP <= self.voice_overlap <= HiroConfig.MAX_VOICE_OVERLAP:
            raise ValueError("voice_overlap is outside the supported range")
        if not HiroConfig.MIN_INTENSITY <= self.intensity_base <= HiroConfig.MAX_INTENSITY:
            raise ValueError("intensity_base is outside the supported range")

    @property
    def intone(self) -> str:
        return self.intone_level

    @intone.setter
    def intone(self, value: str) -> None:
        self.intone_level = value

    @property
    def effective_root_key(self) -> int:
        return self.root_key


__all__ = ["HiroConfig", "GeneratorConfig"]
