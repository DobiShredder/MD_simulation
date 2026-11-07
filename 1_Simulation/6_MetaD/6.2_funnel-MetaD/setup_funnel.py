#!/usr/bin/env python3
"""Calculate Funnel MetaD atom groups and axis from the built 3PTB topology."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import parmed


POINT_A_ATOMS = (("LEU185", "C"), ("PRO225", "CA"), ("PRO225", "N"))
POINT_B_ATOMS = (("CYS220", "CA"), ("LYS224", "C"), ("GLY226", "N"))

ZCC_NM = 1.8
ALPHA_RAD = 0.55
RCYL_NM = 0.1
MINS_NM = -0.5
MAXS_NM = 3.7


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("topology", type=Path)
    parser.add_argument("restart", type=Path)
    parser.add_argument("residue_map", type=Path)
    parser.add_argument("plumed_template", type=Path)
    parser.add_argument("output_dir", type=Path)
    return parser.parse_args()


def read_residue_map(path: Path) -> dict[str, int]:
    rows = path.read_text(encoding="ascii").splitlines()
    mapping = {}

    for line in rows[1:]:
        label, residue = line.split("\t")
        mapping[label] = int(residue)

    return mapping


def coordinates(atom) -> tuple[float, float, float]:
    return float(atom.xx), float(atom.xy), float(atom.xz)


def center_of_mass(atoms) -> tuple[float, float, float]:
    total_mass = sum(atom.mass for atom in atoms)

    return tuple(
        sum(atom.mass * coordinates(atom)[index] for atom in atoms) / total_mass
        for index in range(3)
    )


def vector_subtract(left, right):
    return tuple(left[index] - right[index] for index in range(3))


def dot(left, right) -> float:
    return sum(left[index] * right[index] for index in range(3))


def norm(vector) -> float:
    return math.sqrt(dot(vector, vector))


def format_atom_list(numbers: list[int]) -> str:
    return ",".join(str(number) for number in numbers)


def find_atom(topology, residue_number: int, atom_name: str):
    residue = topology.residues[residue_number - 1]
    matches = [atom for atom in residue.atoms if atom.name == atom_name]

    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one {atom_name} atom in residue {residue_number}."
        )

    return matches[0]


def write_reference(path: Path, protein_residues) -> None:
    lines = []

    for residue in protein_residues:
        ca_atoms = [atom for atom in residue.atoms if atom.name == "CA"]

        if len(ca_atoms) != 1:
            continue

        atom = ca_atoms[0]
        x, y, z = coordinates(atom)
        lines.append(
            f"ATOM  {atom.idx + 1:5d}  CA  {residue.name:>3} A"
            f"{residue.idx + 1:4d}    {x:8.3f}{y:8.3f}{z:8.3f}"
            "  1.00  0.00           C"
        )

    if len(lines) < 100:
        raise ValueError(f"Too few CA atoms for alignment: {len(lines)}")

    path.write_text("\n".join(lines + ["END"]) + "\n", encoding="ascii")


def main() -> None:
    args = parse_arguments()
    residue_map = read_residue_map(args.residue_map)
    topology = parmed.load_file(str(args.topology), xyz=str(args.restart))
    ligand_residue_number = residue_map["BEN"]
    protein_residues = topology.residues[: ligand_residue_number - 1]
    ligand = topology.residues[ligand_residue_number - 1]

    if ligand.name != "BEN":
        raise ValueError(
            f"BEN residue mapping does not match: {ligand.name}"
        )

    point_a_atoms = [
        find_atom(topology, residue_map[label], atom_name)
        for label, atom_name in POINT_A_ATOMS
    ]
    point_b_atoms = [
        find_atom(topology, residue_map[label], atom_name)
        for label, atom_name in POINT_B_ATOMS
    ]
    point_a = center_of_mass(point_a_atoms)
    point_b = center_of_mass(point_b_atoms)

    ligand_heavy_atoms = [atom for atom in ligand.atoms if atom.atomic_number > 1]
    ligand_all_numbers = [atom.idx + 1 for atom in ligand.atoms]
    ligand_heavy_numbers = [atom.idx + 1 for atom in ligand_heavy_atoms]
    ligand_com = center_of_mass(ligand_heavy_atoms)
    protein_heavy_atoms = [
        atom
        for residue in protein_residues
        for atom in residue.atoms
        if atom.atomic_number > 1
    ]
    anchor = min(
        protein_heavy_atoms,
        key=lambda protein_atom: min(
            norm(vector_subtract(coordinates(protein_atom), coordinates(ligand_atom)))
            for ligand_atom in ligand_heavy_atoms
        ),
    )

    axis = vector_subtract(point_b, point_a)
    axis_length = norm(axis)
    unit_axis = tuple(value / axis_length for value in axis)
    ligand_vector = vector_subtract(ligand_com, point_a)
    initial_lp_angstrom = dot(ligand_vector, unit_axis)
    perpendicular = tuple(
        ligand_vector[index] - initial_lp_angstrom * unit_axis[index]
        for index in range(3)
    )
    initial_ld_angstrom = norm(perpendicular)
    initial_lp_nm = initial_lp_angstrom / 10.0
    initial_ld_nm = initial_ld_angstrom / 10.0
    allowed_radius_nm = RCYL_NM + math.tan(ALPHA_RAD) * (ZCC_NM - initial_lp_nm)

    if not (MINS_NM < initial_lp_nm < ZCC_NM):
        raise ValueError(f"Initial BEN lp is outside the cone range: {initial_lp_nm:.3f} nm")
    if initial_ld_nm >= allowed_radius_nm:
        raise ValueError(
            "Initial BEN COM is outside the funnel: "
            f"ld={initial_ld_nm:.3f}, radius={allowed_radius_nm:.3f} nm"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    reference = args.output_dir / "funnel-reference.pdb"
    write_reference(reference, protein_residues)

    replacements = {
        "@PROTEIN_LAST@": str(protein_residues[-1].atoms[-1].idx + 1),
        "@LIGAND_ALL@": format_atom_list(ligand_all_numbers),
        "@LIGAND_HEAVY@": format_atom_list(ligand_heavy_numbers),
        "@ANCHOR@": str(anchor.idx + 1),
        "@POINTS@": ",".join(f"{value / 10.0:.6f}" for value in point_a + point_b),
        "@REFERENCE@": "funnel-reference.pdb",
    }
    template = args.plumed_template.read_text(encoding="utf-8")

    for token, value in replacements.items():
        template = template.replace(token, value)

    (args.output_dir / "plumed.dat").write_text(
        template.replace("@RESTART@", ""), encoding="utf-8"
    )
    (args.output_dir / "atom_count.txt").write_text(
        f"{len(topology.atoms)}\n", encoding="ascii"
    )
    (args.output_dir / "funnel_geometry.tsv").write_text(
        "parameter\tvalue\tunit\n"
        f"point_A\t{','.join(f'{value:.3f}' for value in point_a)}\tangstrom\n"
        f"point_B\t{','.join(f'{value:.3f}' for value in point_b)}\tangstrom\n"
        f"initial_lp\t{initial_lp_nm:.6f}\tnm\n"
        f"initial_ld\t{initial_ld_nm:.6f}\tnm\n"
        f"initial_radius\t{allowed_radius_nm:.6f}\tnm\n"
        f"anchor_atom\t{anchor.idx + 1}\tindex\n"
        f"ligand_heavy_atoms\t{format_atom_list(ligand_heavy_numbers)}\tindex\n",
        encoding="utf-8",
    )

    print(
        "Funnel geometry: "
        f"lp={initial_lp_nm:.3f} nm, ld={initial_ld_nm:.3f} nm, "
        f"allowed radius={allowed_radius_nm:.3f} nm"
    )


if __name__ == "__main__":
    main()
