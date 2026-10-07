# Running Hiro UST in PyCharm

## Recommended setup

1. Open the repository root (`text-to-ust`) in PyCharm.
2. Open **Settings → Project → Python Interpreter**.
3. Create/select a Python 3.10+ virtual environment.
4. In the PyCharm terminal, install the project in editable mode:

```bash
python -m pip install -e .
```

For development and EXE building:

```bash
python -m pip install -r requirements-dev.txt
```

## Recommended Run Configuration

Use the repository-root launcher.

**Run → Edit Configurations → + → Python**

Set:

- **Name:** `Hiro UST`
- **Script path:** `run.py`
- **Working directory:** repository root
- **Python interpreter:** the project's virtual environment

Then click **Run**.

This is equivalent to:

```bash
python run.py
```

## Alternative

The package entry point also works:

```bash
python -m hiro_ust
```

Do not use individual internal modules such as `core.py` or `ui/main_window.py` as the main application entry point.

## Common mistake

Do not run:

```text
src/hiro_ust/core.py
src/hiro_ust/ui/main_window.py
```

`core.py` is the UI-independent generation API. `ui/main_window.py` is the PySide6 presentation layer.

## Building the EXE from PyCharm

Open `build_exe.py` and run it with the same project interpreter.

Or use the PyCharm terminal:

```bash
python build_exe.py
```

The executable is written to:

```text
dist/Hiro_UST_Generator.exe
```
