#!/usr/bin/env python3
"""Convert AMBER topology and restart files to GROMACS format."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

import parmed

from scale_cmap import COLD_CMAP_TYPE_PREFIX
from tempered_selection import read_selection

HOT_CMAP_TYPE_PREFIX = "XC"


def preserve_residue_specific_cmaps(
    structure: parmed.Structure, hot_atom_indices: set[int]
) -> int:
    """Give each residue/CMAP combination a distinct C-alpha type.

    REST scales every map in [ cmaptypes ], so residues outside the tempered
    region get their own unscaled XU<n> types. A CMAP is hot when its central
    C-alpha atom is tempered.
    """
    existing_types = {str(atom.type) for atom in structure.atoms}
    cmap_names: dict[tuple[int, str, bool], str] = {}
    type_counts = {True: 0, False: 0}
    atom_names: dict[int, str] = {}

    for cmap in structure.cmaps:
        residue_name = cmap.atom3.residue.name
        is_hot = cmap.atom3.idx in hot_atom_indices
        cmap_key = (id(cmap.type), residue_name, is_hot)
        if cmap_key not in cmap_names:
            prefix = HOT_CMAP_TYPE_PREFIX if is_hot else COLD_CMAP_TYPE_PREFIX
            cmap_names[cmap_key] = f"{prefix}{type_counts[is_hot]}"
            type_counts[is_hot] += 1
        cmap_name = cmap_names[cmap_key]
        atom_key = id(cmap.atom3)
        if atom_key in atom_names and atom_names[atom_key] != cmap_name:
            raise SystemExit("Different CMAPs are assigned to one C-alpha atom.")
        if atom_key not in atom_names:
            cmap.atom3.atom_type = copy.copy(cmap.atom3.atom_type)
            cmap.atom3.atom_type.name = cmap_name
            cmap.atom3.type = cmap_name
            atom_names[atom_key] = cmap_name
    collisions = sorted(set(cmap_names.values()) & existing_types)
    if collisions:
        raise SystemExit(f"Generated CMAP type names already exist as atom types: {collisions}")
    return len(cmap_names)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert an AMBER system to GROMACS while preserving CMAP types."
    )
    parser.add_argument("topology", type=Path, help="Input AMBER parm7 topology")
    parser.add_argument("coordinates", type=Path, help="Input AMBER restart coordinates")
    parser.add_argument("output_topology", type=Path, help="Output GROMACS topology")
    parser.add_argument(
        "output_coordinates",
        type=Path,
        help="Output GROMACS coordinate file",
    )
    parser.add_argument(
        "--tempered-atoms",
        type=Path,
        required=True,
        help="tempered_atoms.tsv; CMAPs of other residues get unscaled XU types",
    )
    args = parser.parse_args()

    structure = parmed.load_file(str(args.topology), xyz=str(args.coordinates))
    try:
        hot_atom_indices = {index - 1 for index, _, _ in read_selection(args.tempered_atoms)}
    except (OSError, ValueError) as error:
        raise SystemExit(f"Error: {error}") from None
    cmap_count = preserve_residue_specific_cmaps(structure, hot_atom_indices)
    structure.save(str(args.output_topology), overwrite=True)
    structure.save(str(args.output_coordinates), overwrite=True)
    print(
        f"GROMACS topology and coordinates: {args.output_topology}, "
        f"{args.output_coordinates} (residue-specific CMAP types: {cmap_count})"
    )


if __name__ == "__main__":
    main()
