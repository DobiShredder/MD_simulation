#!/usr/bin/env python3
"""Generate Chignolin terminal C-alpha distance restraints for each window."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import parmed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("topology", type=Path)
    parser.add_argument("coordinates", type=Path)
    parser.add_argument("states", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()

    structure = parmed.load_file(str(args.topology), xyz=str(args.coordinates))
    first = [
        atom.idx + 1
        for atom in structure.atoms
        if atom.residue.idx == 0 and atom.name == "CA"
    ]
    last = [
        atom.idx + 1
        for atom in structure.atoms
        if atom.residue.idx == 9 and atom.name == "CA"
    ]

    if len(first) != 1 or len(last) != 1:
        raise SystemExit("Could not select exactly one CA atom from each of residues 1 and 10.")

    args.output_directory.mkdir(parents=True, exist_ok=True)

    with args.states.open(encoding="utf-8", newline="") as handle:
        states = list(csv.DictReader(handle, delimiter="\t"))

    for state in states:
        center = float(state["window_center_A"])
        text = (
            "&rst\n"
            f" iat={first[0]},{last[0]},\n"
            f" r1={center - 2.0:.1f}, r2={center:.1f}, "
            f"r3={center:.1f}, r4={center + 2.0:.1f},\n"
            " rk2=10.0, rk3=10.0,\n"
            "/\n"
        )
        path = args.output_directory / state["replica"] / "distance.RST"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="ascii")

    print(
        "Terminal Cα selection: "
        f":1@CA={first[0]}, :10@CA={last[0]}"
    )


if __name__ == "__main__":
    main()
