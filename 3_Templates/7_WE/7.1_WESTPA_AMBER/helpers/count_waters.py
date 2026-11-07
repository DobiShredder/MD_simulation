#!/usr/bin/env python3
"""Count explicit-water residues in a PDB file."""

from __future__ import annotations

import argparse
from pathlib import Path

WATER_NAMES = {"WAT", "HOH", "TIP3", "TIP3P", "OPC"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Count explicit-water residues in a PDB file."
    )
    parser.add_argument("pdb", type=Path, help="PDB file produced by the solvation pass")
    args = parser.parse_args()

    residues: set[tuple[str, str, str]] = set()
    for line in args.pdb.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(("ATOM  ", "HETATM")) and line[17:20].strip().upper() in WATER_NAMES:
            residues.add((line[21:22], line[22:26], line[26:27]))
    print(len(residues))


if __name__ == "__main__":
    main()
