#!/usr/bin/env python3
"""Convert AMBER topology and restart files to GROMACS format."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

import parmed


def preserve_residue_specific_cmaps(structure: parmed.Structure) -> int:
    """Give each ff19SB residue/CMAP combination a distinct C-alpha type."""
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
    return len(cmap_names)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert an AMBER system to GROMACS while preserving ff19SB CMAP types."
    )
    parser.add_argument("topology", type=Path, help="Input AMBER parm7 topology")
    parser.add_argument("coordinates", type=Path, help="Input AMBER restart coordinates")
    parser.add_argument("output_topology", type=Path, help="Output GROMACS topology")
    parser.add_argument(
        "output_coordinates",
        type=Path,
        help="Output GROMACS coordinate file",
    )
    args = parser.parse_args()

    structure = parmed.load_file(str(args.topology), xyz=str(args.coordinates))
    cmap_count = preserve_residue_specific_cmaps(structure)
    structure.save(str(args.output_topology), overwrite=True)
    structure.save(str(args.output_coordinates), overwrite=True)
    print(
        f"GROMACS topology and coordinates: {args.output_topology}, "
        f"{args.output_coordinates} (residue-specific CMAP types: {cmap_count})"
    )


if __name__ == "__main__":
    main()
