#!/usr/bin/env python3
"""Mark the tempered atoms as hot in a processed GROMACS topology.

`plumed partial_tempering` scales the atoms whose type ends in "_". The atoms
come from tempered_atoms.tsv (tempered_selection.py), so the marked region is
the whole solute by default or the configured tempered_mask.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from tempered_selection import definition_selection, read_selection  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input_topology", type=Path, help="Processed GROMACS topology")
    parser.add_argument("tempered_atoms", type=Path, help="tempered_atoms.tsv from tempered_selection.py")
    parser.add_argument("output_topology", type=Path, help="Topology with hot atom types")
    args = parser.parse_args()

    try:
        hot_positions = definition_selection(args.input_topology, read_selection(args.tempered_atoms))
    except ValueError as error:
        raise SystemExit(f"Error: {error}") from None

    lines = args.input_topology.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    section = ""
    definition_index = -1
    local_index = 0
    marked = 0

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[] ").lower()
            if section == "moleculetype":
                definition_index += 1
                local_index = 0
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

        is_hot = local_index in hot_positions.get(definition_index, set())
        local_index += 1
        if not is_hot:
            output.append(line)
            continue

        fields[1] = f"{fields[1]}_"
        marked += 1
        rebuilt = " ".join(fields)
        if separator:
            rebuilt = f"{rebuilt} ;{comment}"
        output.append(rebuilt)

    if marked == 0:
        raise SystemExit("Error: no tempered atoms were marked as the hot region.")

    args.output_topology.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"Hot-region marker: {marked} atom records in {len(hot_positions)} molecule definitions")


if __name__ == "__main__":
    main()
