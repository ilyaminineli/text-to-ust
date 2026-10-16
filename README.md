# Hiro UST

**Procedural Japanese lyric → UTAU UST/USTX generator** with mora-aware phonemization, Japanese reading analysis, phrase-aware procedural melody, motif memory, timing variation, dynamics, and pitch-bend expression.

Hiro is a generative starting point and tuning assistant: it converts lyrics into a structured project that can be refined in UTAU. It is procedural rather than fully AI-generated; a fixed seed makes generation reproducible.

## Run

From the repository root:

```bash
python run.py
```

Generate from text or a file without opening the GUI:

```bash
python run.py --lyrics "きょうも こころ" --output song.ustx
python run.py --lyrics-file lyrics.txt --output song.ust --format ust
```

Install for development:

```bash
python -m pip install -e .
```

The package entry point `python -m hiro_ust` opens the GUI. `run.py` is the repository launcher and additionally exposes the command-line generation options. The Windows executable can be built with `python build_exe.py` after installing `requirements-dev.txt`.

## Canonical architecture

```text
run.py / python -m hiro_ust
          │
          ▼
     cli.py / UI
          │
          ▼
  HiroUSTProcessor (core.py)
          │
          ├── LyricParser → JapaneseAnalyzer
          │                   └── Node + vendored Kuroshiro/Kuromoji
          ├── converter.Phonemizer / mora trie
          ├── PhraseMelodyEngine
          └── USTWriter or USTXWriter
```

The canonical generation path is `HiroUSTProcessor` in `src/hiro_ust/core.py`. Keep linguistic analysis, phonemization, melody decisions, serialization, and UI presentation separate. The UI should call the processor rather than reimplementing generation.

### Project structure

- `src/hiro_ust/core.py` — public generation pipeline
- `src/hiro_ust/lyrics.py` and `analyzer/` — lyric structure and Japanese reading analysis
- `src/hiro_ust/converter/` — kana normalization, mora parsing, and phonemization
- `src/hiro_ust/melody/phrase_engine.py` — phrase-first melody planning
- `src/hiro_ust/melody/melody_logic.py` — earlier candidate-scoring / motif engine, retained as a public compatibility API
- `src/hiro_ust/generator/` — UST and USTX serialization
- `src/hiro_ust/voice/` — voice presets and phonetic utilities
- `src/hiro_ust/ui/` — PySide6 editor and melody preview
- `vendor/` — vendored Kuroshiro runtime and Kuromoji dictionary
- `tests/` — regression tests
- `docs/ARCHITECTURE.md` — pipeline, boundaries, and refactoring guidance
- `docs/PYCHARM.md` — IDE setup

## Japanese input

Hiro accepts Hiragana, Katakana, and supported Romaji. Kanji readings are provided by the vendored Kuroshiro/Kuromoji bridge using `vendor/kuromoji/dict`; Node.js is required for that backend. PyKakasi is the offline fallback for unresolved dictionary gaps. When the analyzer is unavailable, kana-only text can still be inspected, but unresolved Kanji are rejected rather than silently converted incorrectly.

Mora-aware parsing handles yōon such as `きゃ`, gemination `っ`, moraic nasal `ん`, long vowels, and phrase punctuation. The analyzer and converter are separate layers: the analyzer resolves surface text to readings, and the converter maps readings to UTAU phonemes.

## Melody and expression

The phrase-first engine plans contour, register, interval patterns, and cadence before rendering pitches against a scale and vocal range. Seeded choices support reproducible comparisons. The Melody tab provides a piano-roll preview and diagnostic audition; this preview is not a replacement for rendering through UTAU.

UST stores integer MIDI notes. Fractional pitch intent therefore needs pitch-bend expression rather than rounding the pitch and discarding the offset.

## Cleanup policy

There is one supported desktop UI: the PySide6 application in `src/hiro_ust/ui/`. `run.py`, `python -m hiro_ust`, and the `hiro-ust` console script are launch surfaces, not separate application implementations. `src/hiro_ust/app.py` and `src/hiro_ust/phonemizer.py` are compatibility import shims; keep them thin until downstream imports are checked.

The older `MelodyBrain` remains exported and covered by tests, so it must not be deleted as “dead code” until its useful scoring/motif behavior is migrated into `PhraseMelodyEngine` and compatibility is verified. Consolidation should happen behind the core API, with regression tests for output format, seed reproducibility, Japanese readings, timing, and pitch-bend serialization.

## Documentation and tests

- [Architecture & developer guide](docs/ARCHITECTURE.md)
- [PyCharm setup](docs/PYCHARM.md)

Run tests with:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

## License

MIT.

**Author:** Ilya Minin (Eli)
