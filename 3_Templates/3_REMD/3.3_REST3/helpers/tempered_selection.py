#!/usr/bin/env python3
"""Select the REST tempered (hot) atoms from the AMBER topology.

tempered_region = "solute" selects every atom outside water and ion residues.
tempered_region = "mask" selects the atoms of tempered_mask (AMBER mask syntax,
evaluated by ParmEd on system.parm7 before the GROMACS conversion).

The output table lists one selected atom per row with its 1-based index in
system.parm7. The GROMACS conversion, the hot-region marking, the net-charge
gate and the temperature predictor all read this one selection.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from config_utils import load_config, section, string_value  # noqa: E402

TEMPERED_REGIONS = ("solute", "mask")
SOLVENT_AND_ION_NAMES = {
    "CA", "CA2", "CA2+", "CL", "CL-", "CLA", "HOH", "K", "K+", "MG", "MG2", "MG2+", "NA", "NA+", "OPC", "POT", "SOD", "SOL", "TIP3", "TIP3P", "WAT", "ZN", "ZN2", "ZN2+",
}
TABLE_HEADER = ["atom_index", "residue_number", "residue_name", "atom_name"]

# One selected atom: 1-based atom index, residue name and atom name.
SelectedAtom = tuple[int, str, str]


def tempered_settings(build: dict[str, object]) -> tuple[str, str]:
    """Return (tempered_region, tempered_mask) after checking their combination."""
    region = string_value(build, "tempered_region")
    if region not in TEMPERED_REGIONS:
        raise ValueError("tempered_region must be solute or mask")

    mask = build.get("tempered_mask", "")
    if not isinstance(mask, str):
        raise ValueError("tempered_mask must be a string (AMBER mask syntax)")
    mask = mask.strip()
    if region == "mask" and not mask:
        raise ValueError('tempered_region = "mask" requires a non-empty tempered_mask')
    if region == "solute" and mask:
        raise ValueError('tempered_mask is used only with tempered_region = "mask"')
    return region, mask


def select_atoms(topology_path: Path, region: str, mask: str) -> tuple[list[SelectedAtom], object]:
    # Imported here so config validation does not need ParmEd.
    import parmed
    from parmed.amber import AmberMask

    structure = parmed.load_file(str(topology_path))
    if region == "solute":
        chosen = [
            atom for atom in structure.atoms
            if atom.residue.name.upper() not in SOLVENT_AND_ION_NAMES
        ]
    else:
        try:
            flags = AmberMask(structure, mask).Selection()
        except Exception as error:  # ParmEd raises MaskError and parser errors.
            raise ValueError(f"tempered_mask {mask!r} could not be evaluated: {error}") from None
        chosen = [atom for atom, flag in zip(structure.atoms, flags) if flag]

    if not chosen:
        raise ValueError(f"tempered region {region!r} selects no atoms: {topology_path}")
    for atom in chosen:
        if atom.residue.name.upper() in SOLVENT_AND_ION_NAMES:
            raise ValueError(
                f"tempered_mask {mask!r} selects water or ion residue "
                f"{atom.residue.name} {atom.residue.idx + 1}; REST tempers only solute atoms"
            )
    return [(atom.idx + 1, atom.residue.name, atom.name) for atom in chosen], structure


def write_selection(path: Path, structure: object, atoms: list[SelectedAtom]) -> None:
    lines = ["\t".join(TABLE_HEADER)]
    for atom_index, residue_name, atom_name in atoms:
        residue_number = structure.atoms[atom_index - 1].residue.idx + 1
        lines.append(f"{atom_index}\t{residue_number}\t{residue_name}\t{atom_name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_selection(path: Path) -> list[SelectedAtom]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].split("\t") != TABLE_HEADER:
        raise ValueError(f"{path}: invalid tempered-atom table header")
    atoms: list[SelectedAtom] = []
    for line_number, line in enumerate(lines[1:], start=2):
        fields = line.split("\t")
        if len(fields) != len(TABLE_HEADER) or not fields[0].isdigit():
            raise ValueError(f"{path}: line {line_number}: invalid tempered-atom row")
        atoms.append((int(fields[0]), fields[2], fields[3]))
    if not atoms:
        raise ValueError(f"{path}: no tempered atoms")
    return atoms


def topology_layout(path: Path) -> tuple[list[tuple[str, list[tuple[str, str]]]], list[tuple[str, int]]]:
    """Return [ moleculetype ] (name, [(residue, atom name)]) and [ molecules ] rows."""
    definitions: list[tuple[str, list[tuple[str, str]]]] = []
    molecule_rows: list[tuple[str, int]] = []
    section_name = ""
    expect_name = False

    for line in path.read_text(encoding="utf-8").splitlines():
        data = line.split(";", 1)[0].strip()
        if not data or data.startswith("#"):
            continue
        if data.startswith("[") and data.endswith("]"):
            section_name = data.strip("[] ").lower()
            expect_name = section_name == "moleculetype"
            continue
        fields = data.split()
        if section_name == "moleculetype" and expect_name:
            definitions.append((fields[0], []))
            expect_name = False
        elif section_name == "atoms" and definitions and len(fields) >= 5 and fields[0].isdigit():
            definitions[-1][1].append((fields[3], fields[4]))
        elif section_name == "molecules":
            molecule_rows.append((fields[0], int(fields[1])))

    if not definitions or not molecule_rows:
        raise ValueError(f"{path}: [ moleculetype ] or [ molecules ] not found")
    return definitions, molecule_rows


def definition_selection(topology: Path, atoms: list[SelectedAtom]) -> dict[int, set[int]]:
    """Map selected global atoms to 0-based atom positions in each molecule definition.

    A definition used by several molecule copies can carry only one hot/cold
    pattern, so every copy must select the same atoms.
    """
    definitions, molecule_rows = topology_layout(topology)
    names = [name for name, _ in definitions]
    selected = {atom_index: (residue, name) for atom_index, residue, name in atoms}

    patterns: dict[int, set[int]] = {}
    global_index = 0
    for molecule_name, count in molecule_rows:
        if molecule_name not in names:
            raise ValueError(f"{topology}: [ molecules ] lists undefined molecule {molecule_name}")
        definition_index = names.index(molecule_name)
        definition_atoms = definitions[definition_index][1]
        for _ in range(count):
            pattern = set()
            for local_index, (residue, atom_name) in enumerate(definition_atoms):
                global_index += 1
                if global_index not in selected:
                    continue
                expected = selected[global_index]
                if (residue.upper(), atom_name.upper()) != (expected[0].upper(), expected[1].upper()):
                    raise ValueError(
                        f"{topology}: atom {global_index} is {residue}:{atom_name} but the "
                        f"tempered selection lists {expected[0]}:{expected[1]}; "
                        "the GROMACS topology and system.parm7 atom order differ"
                    )
                pattern.add(local_index)
            previous = patterns.setdefault(definition_index, pattern)
            if previous != pattern:
                raise ValueError(
                    f"tempered selection differs between copies of molecule {molecule_name}; "
                    "the GROMACS topology stores identical copies once, so select all "
                    "copies alike or none of them"
                )

    if global_index < max(selected):
        raise ValueError(f"{topology}: has {global_index} atoms, fewer than the tempered selection")
    return {index: pattern for index, pattern in patterns.items() if pattern}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config", type=Path, help="TOML configuration file with [build] tempered_region")
    parser.add_argument("topology", type=Path, help="AMBER system.parm7")
    parser.add_argument("output", type=Path, help="tempered_atoms.tsv to write")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    try:
        region, mask = tempered_settings(section(load_config(args.config), "build"))
        atoms, structure = select_atoms(args.topology, region, mask)
    except ValueError as error:
        raise SystemExit(f"Tempered-region error: {error}") from None

    write_selection(args.output, structure, atoms)
    residue_count = len({structure.atoms[index - 1].residue.idx for index, _, _ in atoms})
    label = "solute" if region == "solute" else f"mask {mask!r}"
    print(f"Tempered region ({label}): {len(atoms)} atoms in {residue_count} residues -> {args.output}")


if __name__ == "__main__":
    main()
