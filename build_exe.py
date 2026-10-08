#!/usr/bin/env python3
"""Build the Hiro UST Generator Windows executable with PyInstaller."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def build_exe() -> int:
    project_root = Path(__file__).resolve().parent
    src_path = project_root / "src"
    icon_path = project_root / "hibiki.ico"
    dist_path = project_root / "dist"
    build_path = project_root / "build"

    for path in (dist_path, build_path):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=Hiro_UST_Generator",
        "--onefile",
        "--windowed",
        f"--paths={src_path}",
        "--collect-all=hiro_ust",
        "--add-data=vendor;vendor",
        "--hidden-import=hiro_ust",
        "--hidden-import=hiro_ust.ui",
        "--hidden-import=hiro_ust.ui.main_window",
        "--hidden-import=hiro_ust.ui.theme",
        "--hidden-import=hiro_ust.ui.highlighter",
        "--hidden-import=hiro_ust.analyzer",
        "--hidden-import=hiro_ust.analyzer.japanese",
        "--hidden-import=PySide6",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=numpy",
        "--hidden-import=yaml",
        "--distpath=dist",
        "--workpath=build",
        "--specpath=.",
    ]

    if icon_path.exists():
        cmd.insert(6, f"--icon={icon_path}")

    cmd.append(str(src_path / "hiro_ust" / "__main__.py"))

    print("Building Hiro UST Generator with PySide6 and vendored Kuromoji…")
    result = subprocess.run(cmd, cwd=project_root)
    if result.returncode == 0:
        exe_path = dist_path / "Hiro_UST_Generator.exe"
        if exe_path.exists():
            print(f"Created: {exe_path}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(build_exe())
