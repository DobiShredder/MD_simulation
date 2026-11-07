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

# Parser 0.2.2 finds topology sections with substring tests such as
# `"system" in line`. ParmEd names multi-residue molecules system1, system2, ...,
# so every molecule whose name contains a section word is renamed.
PARSER_SECTION_WORDS = (
    "defaults", "atomtypes", "nonbond_params", "bondtypes", "constrainttypes",
    "angletypes", "dihedraltypes", "system", "molecules", "moleculetype",
)
PARSER_SOLUTE_PREFIX = "Solute_"


def preserve_residue_specific_cmaps(
    structure: parmed.Structure, hot_atom_indices: set[int]
) -> dict[str, str]:
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
    if structure.cmaps and not cmap_names:
        raise SystemExit("Could not separate residue-specific CMAPs.")

    return {name: residue for (_, residue, _), name in cmap_names.items()}


def rename_parser_unsafe_molecules(topology: Path) -> dict[str, str]:
    """Rename molecules that parser 0.2.2 would read as section headers."""
    lines = topology.read_text(encoding="utf-8").splitlines(keepends=True)
    section = ""
    expect_definition_name = False
    definition_names: list[str] = []
    renamed: dict[str, str] = {}

    for line_number, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith("[") and "]" in stripped:
            section = stripped[1 : stripped.index("]")].strip()
            expect_definition_name = section == "moleculetype"
            continue

        if not stripped or stripped.startswith((";", "#")):
            continue

        name = stripped.split()[0]
        if section == "moleculetype" and expect_definition_name:
            expect_definition_name = False
            definition_names.append(name)
            if any(word in name for word in PARSER_SECTION_WORDS):
                renamed[name] = f"{PARSER_SOLUTE_PREFIX}{len(renamed) + 1}"
                lines[line_number] = line.replace(name, renamed[name], 1)
        elif section == "molecules" and name in renamed:
            lines[line_number] = line.replace(name, renamed[name], 1)

    collisions = set(renamed.values()) & set(definition_names)
    if collisions:
        raise SystemExit(f"Renamed molecule names already exist: {sorted(collisions)}")

    topology.write_text("".join(lines), encoding="utf-8")
    return renamed


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

    for path in (args.topology, args.coordinates):
        if not path.is_file():
            raise SystemExit(f"Input file not found: {path}")

    structure = parmed.load_file(str(args.topology), xyz=str(args.coordinates))
    try:
        hot_atom_indices = {index - 1 for index, _, _ in read_selection(args.tempered_atoms)}
    except (OSError, ValueError) as error:
        raise SystemExit(f"Error: {error}") from None
    cmap_types = preserve_residue_specific_cmaps(structure, hot_atom_indices)
    structure.save(str(args.output_topology), overwrite=True)
    structure.save(str(args.output_coordinates), overwrite=True)
    renamed = rename_parser_unsafe_molecules(args.output_topology)
    print(
        "GROMACS Conversion output: "
        f"{args.output_topology}, {args.output_coordinates} "
        f"(renamed molecules: {len(renamed)}, "
        f"residue-specific CMAP types: {len(cmap_types)})"
    )


if __name__ == "__main__":
    main()
