# Repository cleanup audit

This file records the consolidation rules for follow-up maintenance. The aim is to remove duplicated behavior, not to delete code solely because it is older or appears unused in one entry point.

## Canonical paths

- The installed console command, module entry point, and repository-root launcher now route through `hiro_ust.cli.main`.
- `HiroUSTProcessor` is the sole processor-facing lyric-to-output pipeline.
- The PySide6 window is loaded lazily only when the GUI is requested, so command-line generation does not import the UI.
- Melody algorithms remain modular behind a common engine API. The older scored engine remains available until downstream imports and output compatibility have been checked.

## Intentional compatibility surfaces

- `src/hiro_ust/app.py` is a compatibility import for earlier UI callers.
- `src/hiro_ust/phonemizer.py` is a compatibility import for the canonical converter phonemizer.
- `run.py` remains a small repository-root launcher so existing user instructions and scripts continue to work.
- `MelodyBrain`, `PhraseMelodyEngine`, and their public types remain importable while features and test coverage are migrated.

These wrappers should stay thin. Do not add generation rules or duplicated state to them.

## Files not considered junk

- `vendor/kuromoji/dict/` contains the Japanese morphological analyzer dictionary required by the Kuroshiro bridge.
- `vendor/kuroshiro_bridge.js`, `vendor/kuroshiro.min.js`, and related vendor assets support the Japanese-reading workflow.
- `tools/test_kuroshiro.py` is an integration diagnostic for the optional Node-backed analyzer.
- `tests/` covers linguistic conversion, lyric structure, export, and melody preview.
- Both `pyproject.toml` and `requirements.txt` declare runtime dependencies for different installation workflows; keep them synchronized rather than deleting either file.

## Low-risk cleanup in this pass

- Removed duplicated and overlapping ignore patterns from `.gitignore`.
- Consolidated duplicated argument parsing into `hiro_ust.cli`; `run.py` now delegates to it.
- Corrected the CLI entry point so the installed `hiro-ust` command supports the same generation options as `python run.py`.
- Removed the unnecessary npm executable check from the Node diagnostic. The diagnostic invokes Node; it does not run npm itself.

## Validation checklist

Before merging cleanup work, run:

```bash
python -m pytest
python run.py --lyrics "あ い う" --output smoke.ust --format ust
python -m hiro_ust --lyrics "あ い う" --output smoke.ustx --format ustx
hiro-ust --lyrics "あ い う" --output smoke.ustx --format ustx
```

The Node-backed Kanji path should also be tested after installing the Node dependencies with `npm install`. Kana-only fallback tests should not require Node.


The test workflow runs on pull requests and pushes to `master`. It installs the Python package, development dependencies and locked Node packages before running the full pytest suite.
