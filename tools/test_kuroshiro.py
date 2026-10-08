"""End-to-end Kuroshiro/Kuromoji Node-runtime diagnostic."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "vendor" / "kuroshiro_bridge.js"
DICT = ROOT / "vendor" / "kuromoji" / "dict"

TESTS = [
    "スターズ　静かに数える",
    "物がなくて　持つかない",
    "心　止まり沈むよ",
    "光　待つけど　見つからない",
]


def main() -> int:
    node = shutil.which("node")
    npm = shutil.which("npm")

    if node is None:
        raise RuntimeError("Node.js was not found on PATH.")
    if npm is None:
        raise RuntimeError("npm was not found on PATH.")

    print(f"Node: {node}")
    print(f"npm:  {npm}")
    print(f"Bridge: {BRIDGE}")
    print(f"Dictionary: {DICT}")
    print()

    if not BRIDGE.exists():
        raise RuntimeError(f"Bridge not found: {BRIDGE}")
    if not DICT.exists():
        raise RuntimeError(f"Dictionary directory not found: {DICT}")

    archives = sorted(DICT.glob("*.dat.gz"))
    if not archives:
        raise RuntimeError(f"No .dat.gz archives found in {DICT}")

    process = subprocess.run(
        [node, str(BRIDGE)],
        input=json.dumps(TESTS, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )

    if process.returncode != 0:
        raise RuntimeError(
            "Kuroshiro/Kuromoji bridge failed.\n\n"
            + (process.stderr or "No stderr output.")
        )

    payload = json.loads(process.stdout)

    for item in payload:
        print(f"SOURCE:   {item['text']}")
        print(f"READING:  {item['reading']}")
        print(f"SPACED:   {item['spaced']}")
        print(f"FURIGANA: {item['furigana']}")
        print()

    print("Kuroshiro + Node Kuromoji runtime succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
