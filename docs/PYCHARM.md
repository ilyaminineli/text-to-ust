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

Use the package module rather than opening an arbitrary `.py` file.

**Run → Edit Configurations → + → Python**

Set:

- **Name:** `Hiro UST`
- **Module name:** `hiro_ust`
- **Working directory:** repository root
- **Python interpreter:** the project's virtual environment

Then click **Run**.

This is equivalent to:

```bash
python run.py
```

## Alternative

You can run `src/hiro_ust/__main__.py` directly, but the module configuration is preferred because it follows the package layout and avoids path differences between IDEs and terminals.

## Common mistake

Do not use these as normal application entry points:

```text
src/hiro_ust/core.py
src/hiro_ust/ui/main_window.py.py
src/hiro_ust/cli.py
```

`core.py` is the programmatic API. `cli.py` is the launcher implementation. `ui/main_window.py.py` is PySide6 application shell.

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
