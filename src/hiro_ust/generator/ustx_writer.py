"""OpenUtau USTX serialization with context-aware vocal expression."""

from __future__ import annotations

import hashlib
import math
import random

import yaml

EXPRESSIONS = {
    "dyn": {
        "name": "dynamics (curve)",
        "abbr": "dyn",
        "type": "Curve",
        "min": -240,
        "max": 120,
        "default_value": 0,
        "is_flag": False,
        "flag": "",
    },
    "pitd": {
        "name": "pitch deviation (curve)",
        "abbr": "pitd",
        "type": "Curve",
        "min": -1200,
        "max": 1200,
        "default_value": 0,
        "is_flag": False,
        "flag": "",
    },
    "clr": {
        "name": "voice color",
        "abbr": "clr",
        "type": "Options",
        "min": 0,
        "max": -1,
        "default_value": 0,
        "is_flag": False,
        "options": [],
    },
    "eng": {
        "name": "resampler engine",
        "abbr": "eng",
        "type": "Options",
        "min": 0,
        "max": 1,
        "default_value": 0,
        "is_flag": False,
        "options": ["", "worldline"],
    },
    "vel": {
        "name": "velocity",
        "abbr": "vel",
        "type": "Numerical",
        "min": 0,
        "max": 200,
        "default_value": 100,
        "is_flag": False,
        "flag": "",
    },
    "vol": {
        "name": "volume",
        "abbr": "vol",
        "type": "Numerical",
        "min": 0,
        "max": 200,
        "default_value": 100,
        "is_flag": False,
        "flag": "",
    },
    "atk": {
        "name": "attack",
        "abbr": "atk",
        "type": "Numerical",
        "min": 0,
        "max": 200,
        "default_value": 100,
        "is_flag": False,
        "flag": "",
    },
    "dec": {
        "name": "decay",
        "abbr": "dec",
        "type": "Numerical",
        "min": 0,
        "max": 100,
        "default_value": 0,
        "is_flag": False,
        "flag": "",
    },
    "gen": {
        "name": "gender",
        "abbr": "gen",
        "type": "Numerical",
        "min": -100,
        "max": 100,
        "default_value": 0,
        "is_flag": True,
        "flag": "g",
    },
    "genc": {
        "name": "gender (curve)",
        "abbr": "genc",
        "type": "Curve",
        "min": -100,
        "max": 100,
        "default_value": 0,
        "is_flag": False,
        "flag": "",
    },
    "bre": {
        "name": "breath",
        "abbr": "bre",
        "type": "Numerical",
        "min": 0,
        "max": 100,
        "default_value": 0,
        "is_flag": True,
        "flag": "B",
    },
    "brec": {
        "name": "breathiness (curve)",
        "abbr": "brec",
        "type": "Curve",
        "min": -100,
        "max": 100,
        "default_value": 0,
        "is_flag": False,
        "flag": "",
    },
    "lpf": {
        "name": "lowpass",
        "abbr": "lpf",
        "type": "Numerical",
        "min": 0,
        "max": 100,
        "default_value": 0,
        "is_flag": True,
        "flag": "H",
    },
    "norm": {
        "name": "normalize",
        "abbr": "norm",
        "type": "Numerical",
        "min": 0,
        "max": 100,
        "default_value": 86,
        "is_flag": True,
        "flag": "P",
    },
    "mod": {
        "name": "modulation",
        "abbr": "mod",
        "type": "Numerical",
        "min": 0,
        "max": 100,
        "default_value": 0,
        "is_flag": False,
        "flag": "",
    },
    "mod+": {
        "name": "modulation plus",
        "abbr": "mod+",
        "type": "Numerical",
        "min": 0,
        "max": 100,
        "default_value": 0,
        "is_flag": False,
        "flag": "",
    },
    "alt": {
        "name": "alternate",
        "abbr": "alt",
        "type": "Numerical",
        "min": 0,
        "max": 16,
        "default_value": 0,
        "is_flag": False,
        "flag": "",
    },
    "dir": {
        "name": "direct",
        "abbr": "dir",
        "type": "Options",
        "min": 0,
        "max": 1,
        "default_value": 0,
        "is_flag": False,
        "options": ["off", "on"],
    },
    "shft": {
        "name": "tone shift",
        "abbr": "shft",
        "type": "Numerical",
        "min": -36,
        "max": 36,
        "default_value": 0,
        "is_flag": False,
        "flag": "",
    },
    "shfc": {
        "name": "tone shift (curve)",
        "abbr": "shfc",
        "type": "Curve",
        "min": -1200,
        "max": 1200,
        "default_value": 0,
        "is_flag": False,
        "flag": "",
    },
    "tenc": {
        "name": "tension (curve)",
        "abbr": "tenc",
        "type": "Curve",
        "min": -100,
        "max": 100,
        "default_value": 0,
        "is_flag": False,
        "flag": "",
    },
    "voic": {
        "name": "voicing (curve)",
        "abbr": "voic",
        "type": "Curve",
        "min": 0,
        "max": 100,
        "default_value": 100,
        "is_flag": False,
        "flag": "",
    },
}


def _stable_rng(position: int, lyric: str, tone: int) -> random.Random:
    """Make expression deterministic without tying it to melody RNG state."""
    key = f"{position}|{lyric}|{tone}".encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(key).digest()[:8], "big")
    return random.Random(seed)


def _is_vowel(lyric: str) -> bool:
    return bool(lyric) and lyric[-1].lower() in "aeiou"


class USTXWriter:
    def __init__(self, project_name, tempo, singer_name="イーライ(JPN)"):
        self.project_name = str(project_name)
        self.tempo = float(tempo)
        self.singer_name = singer_name
        self.notes = []
        self.position = 0
        self.resolution = 480

    def add_rest(self, length):
        self.position += max(0, int(length))

    def add_small_tsu(self, root_key, length=60):
        self.notes.append(
            {
                "position": self.position,
                "duration": int(length),
                "tone": int(root_key),
                "lyric": "っ",
                "pitch": {
                    "data": [{"x": 0, "y": 0, "shape": "io"}],
                    "snap_first": True,
                },
                "vibrato": {
                    "length": 0,
                    "period": 175,
                    "depth": 20,
                    "in": 10,
                    "out": 10,
                    "shift": 0,
                    "drift": 0,
                    "vol_link": 0,
                },
                "phoneme_expressions": [
                    {"index": 0, "abbr": "norm", "value": 86},
                    {"index": 0, "abbr": "vol", "value": 30},
                ],
                "phoneme_overrides": [],
            }
        )
        self.position += int(length)

    @staticmethod
    def _pitch_curve(length: int, lyric: str, pbs: str, rng: random.Random):
        """Create natural attack/settle movement plus explicit accent bends."""
        curve = [{"x": 0, "y": 0, "shape": "io"}]
        bend = 0
        if pbs and ";" in pbs:
            try:
                bend = int(float(pbs.split(";", 1)[1]))
            except (TypeError, ValueError):
                bend = 0
        if bend:
            start = max(-90, min(90, bend * 2))
            curve = [
                {"x": -55, "y": start, "shape": "io"},
                {
                    "x": min(45, max(15, int(length * 0.18))),
                    "y": int(start * 0.35),
                    "shape": "io",
                },
                {"x": 59, "y": 0, "shape": "io"},
            ]
        elif _is_vowel(lyric) and length >= 180:
            scoop = rng.choice([-18, -12, 0, 10, 15])
            settle = rng.choice([8, 12, 18]) if scoop == 0 else 0
            curve = [
                {"x": -40, "y": scoop, "shape": "io"},
                {"x": min(55, max(20, int(length * 0.16))), "y": settle, "shape": "io"},
                {"x": 59, "y": 0, "shape": "io"},
            ]
        return curve

    @staticmethod
    def _vibrato(length: int, lyric: str, rng: random.Random):
        """Use context-dependent vibrato instead of applying it to every note."""
        vowel = _is_vowel(lyric)
        if not vowel or length < 300:
            return {
                "length": 0,
                "period": 160,
                "depth": 25,
                "in": 10,
                "out": 10,
                "shift": 0,
                "drift": 0,
                "vol_link": 0,
            }
        probability = 0.28 + min(0.35, (length - 300) / 1800)
        if rng.random() >= probability:
            return {
                "length": 0,
                "period": 160,
                "depth": 25,
                "in": 10,
                "out": 10,
                "shift": 0,
                "drift": 0,
                "vol_link": 0,
            }
        vib_len = max(90, min(360, int(length * rng.uniform(0.25, 0.55))))
        return {
            "length": vib_len,
            "period": rng.randint(135, 175),
            "depth": rng.randint(28, 55),
            "in": rng.randint(15, 28),
            "out": rng.randint(15, 30),
            "shift": rng.randint(-8, 8),
            "drift": rng.randint(0, 28),
            "vol_link": 0,
        }

    def add_note(
        self,
        length,
        lyric,
        note_num,
        pre_utter,
        voice_overlap,
        intensity,
        envelope,
        pbs="0;0",
        pbw="0",
        flags="",
        bpm=120,
    ):
        del pre_utter, voice_overlap, envelope, pbw, flags, bpm
        length = max(60, min(1920, int(length)))
        tone = int(max(21, min(108, round(float(note_num)))))
        rng = _stable_rng(self.position, str(lyric), tone)

        pitch_data = self._pitch_curve(length, str(lyric), pbs, rng)
        vibrato = self._vibrato(length, str(lyric), rng)

        # Keep the older expressive feel: gentle modulation and velocity variation,
        # but tie it deterministically to the note rather than the global RNG.
        velocity = max(120, min(200, int(165 + rng.uniform(-10, 18))))
        volume = max(50, min(200, int(intensity)))
        modulation = 8 if vibrato["length"] == 0 else 12

        self.notes.append(
            {
                "position": self.position,
                "duration": length,
                "tone": tone,
                "lyric": lyric,
                "pitch": {"data": pitch_data, "snap_first": lyric == "っ"},
                "vibrato": vibrato,
                "phoneme_expressions": [
                    {"index": 0, "abbr": "mod", "value": modulation},
                    {"index": 0, "abbr": "vel", "value": velocity},
                    {"index": 0, "abbr": "vol", "value": volume},
                ],
                "phoneme_overrides": [],
            }
        )
        self.position += length

    def finalize(self):
        return yaml.dump(
            {
                "name": self.project_name,
                "comment": "",
                "output_dir": "Vocal",
                "cache_dir": "UCache",
                "ustx_version": "0.7",
                "resolution": self.resolution,
                "bpm": self.tempo,
                "beat_per_bar": 4,
                "beat_unit": 4,
                "expressions": EXPRESSIONS,
                "exp_selectors": [
                    "dyn",
                    "pitd",
                    "clr",
                    "eng",
                    "vel",
                    "vol",
                    "atk",
                    "dec",
                    "gen",
                    "bre",
                ],
                "exp_primary": 0,
                "exp_secondary": 1,
                "key": 0,
                "time_signatures": [
                    {"bar_position": 0, "beat_per_bar": 4, "beat_unit": 4}
                ],
                "tempos": [{"position": 0, "bpm": self.tempo}],
                "tracks": [
                    {
                        "singer": self.singer_name,
                        "phonemizer": "OpenUtau.Plugin.Builtin.JapanesePresampPhonemizer",
                        "renderer_settings": {
                            "renderer": "CLASSIC",
                            "resampler": "moresampler.exe",
                            "wavtool": "moresampler.exe",
                        },
                        "track_name": "Track1",
                        "track_color": "Blue",
                        "mute": False,
                        "solo": False,
                        "volume": 0,
                        "pan": 0,
                        "track_expressions": [],
                        "voice_color_names": [""],
                    }
                ],
                "voice_parts": [
                    {
                        "duration": self.position,
                        "name": self.project_name,
                        "comment": "",
                        "track_no": 0,
                        "position": 0,
                        "notes": self.notes,
                    }
                ],
                "wave_parts": [],
            },
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
