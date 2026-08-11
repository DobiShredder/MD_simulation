#!/usr/bin/env python3
"""Mark only protein atom types as hot in a processed GROMACS topology."""

from __future__ import annotations

import argparse
from pathlib import Path

SOLVENT_AND_IONS = {
    "WAT",
    "HOH",
    "SOL",
    "TIP3",
    "NA",
    "NA+",
    "SOD",
    "CL",
    "CL-",
    "CLA",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_topology", type=Path)
    parser.add_argument("output_topology", type=Path)
    args = parser.parse_args()

    lines = args.input_topology.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    section = ""
    marked = 0
    nonprotein_marked = 0

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[] ").lower()
            output.append(line)
            continue

        if section != "atoms" or not stripped or stripped.startswith(";"):
            output.append(line)
            continue

        data, separator, comment = line.partition(";")
        fields = data.split()

        if len(fields) < 5 or not fields[0].isdigit():
            output.append(line)
            continue

        residue_name = fields[3].upper()
        if residue_name in SOLVENT_AND_IONS:
            output.append(line)
            continue

        fields[1] = f"{fields[1]}_"
        marked += 1
        rebuilt = " ".join(fields)
        if separator:
            rebuilt = f"{rebuilt} ;{comment}"
        output.append(rebuilt)

        if residue_name in SOLVENT_AND_IONS:
            nonprotein_marked += 1

    if marked == 0:
        raise SystemExit("No protein atoms were marked as the hot region.")

    if nonprotein_marked:
        raise SystemExit("The hot region contains solvent or ion atoms.")

    args.output_topology.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"Protein hot-region marker: {marked} atoms")


if __name__ == "__main__":
    main()
