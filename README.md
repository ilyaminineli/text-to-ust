# 響 Hiro UST

**Procedural Japanese lyric → UTAU UST generator** with mora-aware phonemization, phrase-first procedural melody, motif memory, Japanese analysis, timing variation, dynamics, and pitch-bend expression.

Hiro is designed as a **generative starting-point and tuning assistant**: instead of manually drawing every note and lyric assignment from scratch, it turns lyrics into a structured UST that can be opened in UTAU and refined further.

> Built by Ilya Minin (Eli) — artist, creative technologist, and generative-audio developer.

## Run Hiro

### Run the PySide6 application

From the repository root:

```bash
python run.py
```

The same GUI is available through:

```bash
python -m hiro_ust
```

For generation without opening the GUI:

```bash
python run.py --lyrics-file lyrics.txt --output song.ustx
```

Detailed IDE instructions: [`docs/PYCHARM.md`](docs/PYCHARM.md)

### Terminal

```bash
python -m pip install -e .
python -m hiro_ust
```

### Build the Windows EXE

Install development/build dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Then:

```bash
python build_exe.py
```

The resulting executable is:

```text
dist/Hiro_UST_Generator.exe
```

## Project structure

```text
text-to-ust/
├── README.md
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── build_exe.py
├── hibiki.ico
│
├── docs/
│   ├── ARCHITECTURE.md
│   └── PYCHARM.md
│
├── tests/
│
└── src/
    └── hiro_ust/
        ├── __init__.py
        ├── __main__.py        ← canonical application entry point
        ├── cli.py             ← launcher
        ├── core.py            ← public programmatic API
        ├── config.py
        ├── constants.py
        ├── logger.py
        ├── analyzer/           ← Japanese morphology / kanji / readings
        ├── converter/
        ├── data/
        ├── generator/
        ├── melody/
        ├── ui/                  ← PySide6 application shell
        ├── voice/
        └── core.py             ← UI-independent generation pipeline
```

The GUI is intentionally kept separate from the generator. The application shell is PySide6; lyric parsing, phonemization, melody planning, and serialization remain available as independent Python APIs.

## What Hiro does

Hiro takes Japanese lyrics written in Hiragana/Katakana or supported Romaji forms and generates a UST with:

- mora-aware lyric parsing
- yōon such as `きゃ`, `しゅ`, `ちょ`
- small-tsu gemination `っ`
- moraic nasal `ん`
- phrase and section boundaries
- procedural pitch selection
- scale-aware melody generation
- voice-range constraints
- motif reuse and variation
- deterministic seeded generation
- timing variation
- intensity/dynamics heuristics
- Japanese pitch-accent-aware behavior
- optional microtonal pitch-bend expression
- UST serialization

The project is intentionally **procedural rather than fully AI-generated**. The same seed can reproduce a generation, making musical experiments and algorithm changes easier to compare.

## Installation

Hiro uses a `src/` package layout. Install it in editable mode during development:

```bash
python -m pip install -e .
```

Runtime dependencies are kept in `requirements.txt` / `pyproject.toml`. The GUI uses PySide6. The kanji-reading backend uses the vendored Kuroshiro/Kuromoji assets through Node.js. Development and packaging tools such as PyInstaller are kept in `requirements-dev.txt`.

## Input, word structure, and kanji

Japanese lyrics are fundamentally **mora-oriented**, but Hiro now keeps linguistic structure above the mora layer. A lyric unit can contain multiple Japanese morphemes, each with its surface form, reading, lemma, part of speech, and UTAU phonemes.

For example, a unit containing kanji can be represented as:

```text
心 → こころ → noun → ko ko ro
数える → かぞえる → verb → ka zo e ru
```

The repository's vendored Kuroshiro/Kuromoji analyzer provides the Japanese morphological analysis used by the application. The editor can preview analyzed surface forms, normalized readings, POS tags, kanji flags, and generated phonemes before melody generation. The analyzer works on complete lyric lines and the result is then mapped back to the lyricist's whitespace groups. The desktop bridge uses the repository's `vendor/kuromoji/dict` directly.

Examples:

```text
きゃ → kya
しょ → sho
にゃ → nya
っ → っ
ん → n
```

A mora trie performs longest-match parsing so that `きゃ` is recognized as one yōon unit instead of being incorrectly split into `き` and `ゃ`.

Punctuation such as `、`, `。`, `！`, `？`, and `…` is preserved because it can carry musical phrase information.

## Melody generation

Hiro combines several procedural ideas instead of choosing every pitch randomly.

### Editor and analysis

Section markers such as `[Verse 1]`, `[Chorus]`, and `[Bridge]` are syntax-highlighted automatically. The analysis panel separates linguistic structure from generated notes, while less frequently used actions are grouped under Project, Generation, Analyze, and Debug menus.

### Phrase-first melody

The new melody layer plans phrases before rendering individual notes. It chooses a contour, register, interval motif, and cadence, then maps that musical plan onto the available scale and vocal range. This makes motif reuse and phrase-level variation possible without hard-coding individual note sequences.

### Melody preview

After generation, the PySide6 editor exposes a lightweight piano-roll preview in the **Melody** tab. Notes are rendered with their UST/USTX tick positions, MIDI pitches, durations, and lyrics, with phrase-scale grid lines for quick visual inspection.

The preview also includes a tiny synthesized audition path. It renders the current melody into a temporary WAV and plays it through Qt Multimedia when available, with a Windows fallback. This is intentionally a diagnostic sound rather than a replacement for the UTAU render.

Notes can be selected individually with Ctrl, as ranges with Shift, or by dragging a marquee over the piano roll. Playback can target either the full melody or the current selection, and a Stop control cancels the preview. The selection is also surfaced as note indices plus a `(start_tick, end_tick)` range, so the same UI model can later become the input to **range-based regeneration**: regenerate only the selected phrase/region while preserving the rest of the arrangement.

### Scales

The melody can be constrained to configured scales, including common diatonic, pentatonic, blues, whole-tone, octatonic, chromatic, and experimental palettes available in the project.

### Motif memory

Hiro can remember short melodic ideas and reuse them later. Motifs are represented as interval patterns, allowing the same shape to recur transposed to another pitch level.

### Deterministic generation

The seed controls procedural choices, making it possible to reproduce a result for debugging and algorithm comparison.

## Expression

Expression can include pitch bends, microtonal offsets, intensity, envelopes, pre-utterance, voice overlap, and timing variation.

UST stores integer MIDI note numbers, so fractional pitches such as `60.5` must be represented with pitch-bend information instead of simply being rounded away.

Vibrato is intended to become context-dependent rather than being applied indiscriminately to every note.

## Current limitations

Hiro is a **procedural generator and starting point**, not a replacement for a professional human UTAU tuner.

Current development areas include deeper Japanese pitch-accent modeling, Kuromoji-backed Japanese analysis, stronger voicebank-specific phonetic handling, richer rhythm generation, intelligent vibrato/portamento, and additional musical policies built on the phrase-first melody layer.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture and developer guide
- [`docs/PYCHARM.md`](docs/PYCHARM.md) — PyCharm setup, execution, and EXE building

## License

MIT.

## Author

**Ilya Minin (Eli)**
