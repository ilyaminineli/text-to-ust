# Hiro UST — Architecture & Developer Guide

Hiro UST is a procedural lyric-to-UST engine. The long-term goal is not merely to convert text into notes, but to model enough linguistic, melodic, and expressive information to produce a convincing starting point for UTAU tuning.

## Pipeline

```text
Lyrics
  ↓
Song / section parser
  ↓
Japanese normalization + mora parsing
  ↓
Phoneme / accent analysis
  ↓
Phrase-aware melody generation
  ↓
Note timing + pitch decisions
  ↓
Expression / pitch-bend decisions
  ↓
UST / USTX serialization
```

Each stage should remain independent of the file format used at the final stage.

## Main components

### `converter/`
Text normalization and phonetic conversion.

- Japanese Hiragana/Katakana → mora/phoneme representation
- Romaji → Hiragana → phonemes
- punctuation preservation for phrase-aware generation
- language-mode handling

Japanese lyrics are mora-oriented. A sequence such as `きゃ`, `しょ`, and `っ` must not be treated as unrelated characters.

### `data/`
Static linguistic tables such as mora mappings and scale data.

The mora trie allows longest-match parsing. This prevents combinations such as `きゃ` from being split into `き` + `ゃ`.

### `melody/`
Musical decision making.

The melody layer contains both the existing candidate-scoring engine and the newer phrase-first layer. The phrase-first engine plans a phrase contour, register, interval motif, and cadence before rendering individual notes. This is the direction for the next generation system.

Randomness should always be seedable. A fixed seed is useful for debugging, regression tests, and comparing individual algorithm changes.

### `generator/`
Converts musical decisions into UST events.

The writer is deliberately kept separate from linguistic analysis. It should know about UST fields, not Japanese grammar.

### `voice/`
Voice-specific ranges, presets, envelopes, and phonetic utilities.

Voice configuration should affect generation through explicit parameters rather than hard-coded special cases.

### `ui/`
The PySide6 graphical interface. The UI owns controls, file dialogs, settings, preview tables, and presentation styling. It calls `HiroUSTProcessor` but contains no melody-generation rules.

The main window is deliberately editor-like: lyrics on the left, generated-note analysis in the center, and compact musical controls on the right. Generate/export actions stay in the toolbar.

## Determinism

Hiro uses seeded random generators for procedural decisions. Keep random streams isolated where possible:

```text
seed
 ├── melody decisions
 ├── timing variation
 ├── expression variation
 └── ornament decisions
```

This makes it possible to change expression without accidentally changing the melody.

## Japanese phonetics

Important units include:

- ordinary mora: `か`, `し`, `の`
- yōon: `きゃ`, `しゅ`, `ちょ`
- gemination: `っ`
- moraic nasal: `ん`
- long vowels: `ー` and orthographic long-vowel patterns
- punctuation and phrase boundaries

Punctuation is musically meaningful. `、`, `。`, `！`, `？`, and ellipses can eventually influence rests, cadence, intensity, timing, and vibrato.

## Melody model

Hiro should treat melody generation as a candidate-selection problem rather than pure random movement.

For each position, possible pitches can be scored using:

```text
scale fit
+ voice range
+ previous-pitch distance
+ phrase contour
+ Japanese pitch accent
+ rhythmic position
+ motif compatibility
+ cadence tendency
+ note importance
```

The highest-scoring candidates can then be sampled with controlled randomness.

## Motifs

Motifs are represented by interval patterns rather than only absolute MIDI pitches.

For example:

```text
C → D → E → G
```

becomes approximately:

```text
+2 → +2 → +3
```

The same motif can therefore reappear transposed to another part of the range.

## Pitch accents

Japanese pitch accent should eventually be represented as a contour rather than a single boolean flag. Useful information includes:

- accent type
- mora count
- accent nucleus / drop position
- pre-accent high region
- post-accent low region
- phrase-boundary behavior

The accent contour should influence melody and pitch expression, not simply force a fixed MIDI note.

## Expression

The intended expression pipeline is:

```text
NoteEvent
 ├── pitch
 ├── duration
 ├── lyric
 ├── intensity
 ├── timing
 ├── envelope
 └── pitch curve
      ├── attack
      ├── accent movement
      ├── portamento
      ├── vibrato
      └── release
```

Vibrato should be a decision made from musical context, not a property automatically applied to every note. Long vowels, sustained phrase-final notes, and important notes are stronger candidates than short passing notes.

## Microtones

UST stores integer MIDI note numbers, so fractional pitches such as `60.5` cannot simply be rounded. Hiro represents microtonal offsets using UST pitch-bend information while retaining the nearest MIDI base note.

This distinction is important for quarter-tone and other continuous pitch expressions.

## UST writing

The UST writer is a serialization layer. It should receive complete musical events and serialize them into fields such as:

- `Length`
- `Lyric`
- `NoteNum`
- `PreUtterance`
- `VoiceOverlap`
- `Intensity`
- `Envelope`
- `PBS`
- `PBW`
- `PBY`
- `PBM`
- `Flags`

Avoid putting linguistic or melody decisions inside the writer.

## Testing strategy

Recommended regression categories:

1. Mora parsing
2. Romaji conversion
3. punctuation preservation
4. small-tsu handling
5. yōon handling
6. deterministic generation with a fixed seed
7. voice-range limits
8. scale membership
9. pitch-bend serialization
10. UST syntax / UTF-8 output

Golden UST fixtures are particularly useful: the same lyrics, configuration, and seed should produce the same result unless an intentional algorithm change modifies it.

## Development direction

The PySide6 migration removes the GUI dependency from the generator and makes the application shell replaceable without changing the musical API.

The next milestone is to introduce explicit musical `NoteEvent` and `PhraseEvent` objects. After that, expression can be developed as a separate layer instead of being scattered through UST generation.

Kuromoji/Kuroshiro assets are currently vendored for a future Japanese-analysis layer. They should feed structured linguistic information into the lyric pipeline rather than becoming part of the low-level mora converter.
