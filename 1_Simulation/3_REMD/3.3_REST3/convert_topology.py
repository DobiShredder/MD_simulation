#!/usr/bin/env python3
"""Convert AMBER topology and restart files to GROMACS format."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

import parmed


def preserve_residue_specific_cmaps(structure: parmed.Structure) -> dict[str, str]:
    """Assign C-alpha atom types for each ff19SB CMAP grid and residue combination."""
    cmap_names: dict[tuple[int, str], str] = {}
    atom_names: dict[int, str] = {}

    for cmap in structure.cmaps:
        residue_name = cmap.atom3.residue.name
        cmap_key = (id(cmap.type), residue_name)
        cmap_name = cmap_names.setdefault(cmap_key, f"XC{len(cmap_names)}")
        atom_key = id(cmap.atom3)

        if atom_key in atom_names and atom_names[atom_key] != cmap_name:
            raise SystemExit("Different CMAPs are assigned to one C-alpha atom.")

        if atom_key not in atom_names:
            cmap.atom3.atom_type = copy.copy(cmap.atom3.atom_type)
            cmap.atom3.atom_type.name = cmap_name
            cmap.atom3.type = cmap_name
            atom_names[atom_key] = cmap_name

    if structure.cmaps and len(cmap_names) < 2:
        raise SystemExit("Could not separate ff19SB residue-specific CMAPs.")

    return {name: residue for (_, residue), name in cmap_names.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("topology", type=Path)
    parser.add_argument("coordinates", type=Path)
    parser.add_argument("output_topology", type=Path)
    parser.add_argument("output_coordinates", type=Path)
    args = parser.parse_args()

    for path in (args.topology, args.coordinates):
        if not path.is_file():
            raise SystemExit(f"Input file not found: {path}")

    structure = parmed.load_file(str(args.topology), xyz=str(args.coordinates))
    cmap_types = preserve_residue_specific_cmaps(structure)
    structure.save(str(args.output_topology), overwrite=True)
    structure.save(str(args.output_coordinates), overwrite=True)

    print(
        "GROMACS Conversion output: "
        f"{args.output_topology}, {args.output_coordinates} "
        f"(residue-specific CMAP types: {len(cmap_types)})"
    )


if __name__ == "__main__":
    main()
