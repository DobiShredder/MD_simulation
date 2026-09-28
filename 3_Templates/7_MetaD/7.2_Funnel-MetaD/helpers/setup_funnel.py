#!/usr/bin/env python3
"""Resolve Funnel-MetaD atom selections and validate the initial geometry."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from config_utils import load_config, positive_float, section, string_value  # noqa: E402


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve AMBER masks into a PLUMED funnel axis and atom groups."
    )
    parser.add_argument("config", type=Path, help="Funnel-MetaD TOML configuration")
    parser.add_argument("topology", type=Path, help="AMBER parm7 topology")
    parser.add_argument("coordinates", type=Path, help="AMBER restart coordinates")
    parser.add_argument("output", type=Path, help="Directory for funnel context files")
    return parser.parse_args()


def mask_list(values: dict[str, object], key: str) -> list[str]:
    raw = values.get(key)
    if not isinstance(raw, list) or not raw or not all(isinstance(v, str) and v for v in raw):
        raise ValueError(f"{key} must be a non-empty list of AMBER masks")
    return list(raw)


def selected_atoms(topology, mask: str):
    from parmed.amber.mask import AmberMask

    selection = AmberMask(topology, mask).Selection()
    atoms = [atom for atom, selected in zip(topology.atoms, selection) if selected]
    if not atoms:
        raise ValueError(f"AMBER mask selects no atoms: {mask}")
    return atoms


def single_atom(topology, mask: str):
    atoms = selected_atoms(topology, mask)
    if len(atoms) != 1:
        raise ValueError(f"AMBER mask must select one atom: {mask} selected {len(atoms)}")
    return atoms[0]


def coordinates(atom) -> tuple[float, float, float]:
    return float(atom.xx), float(atom.xy), float(atom.xz)


def center_of_mass(atoms) -> tuple[float, float, float]:
    total_mass = sum(float(atom.mass) for atom in atoms)
    if total_mass <= 0.0:
        raise ValueError("Selected axis atoms have zero total mass")
    return tuple(
        sum(float(atom.mass) * coordinates(atom)[axis] for atom in atoms) / total_mass
        for axis in range(3)
    )


def subtract(left, right):
    return tuple(left[index] - right[index] for index in range(3))


def dot(left, right) -> float:
    return sum(left[index] * right[index] for index in range(3))


def norm(vector) -> float:
    return math.sqrt(dot(vector, vector))


def compress_atom_numbers(atoms) -> str:
    numbers = sorted({atom.idx + 1 for atom in atoms})
    ranges: list[str] = []
    start = previous = numbers[0]
    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = number
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(ranges)


def write_reference(path: Path, atoms) -> None:
    lines: list[str] = []
    for atom in atoms:
        x, y, z = coordinates(atom)
        residue = atom.residue
        element = (getattr(atom, "element_name", "") or atom.name[:1]).strip()[:2]
        lines.append(
            f"ATOM  {atom.idx + 1:5d} {atom.name:>4} {residue.name:>3} A"
            f"{residue.idx + 1:4d}    {x:8.3f}{y:8.3f}{z:8.3f}"
            f"  1.00  0.00          {element:>2}"
        )
    if len(lines) < 3:
        raise ValueError("alignment_mask must select at least three atoms")
    path.write_text("\n".join(lines + ["END"]) + "\n", encoding="ascii")


def main() -> None:
    args = parse_arguments()
    try:
        import parmed
    except ImportError:
        raise SystemExit("ParmEd is required to resolve funnel selections") from None

    try:
        config = load_config(args.config)
        selections = section(config, "funnel_selection")
        funnel = section(config, "funnel")
        topology = parmed.load_file(str(args.topology), xyz=str(args.coordinates))

        protein_atoms = selected_atoms(topology, string_value(selections, "protein_mask"))
        ligand_atoms = selected_atoms(topology, string_value(selections, "ligand_mask"))
        ligand_heavy = selected_atoms(
            topology, string_value(selections, "ligand_heavy_atom_mask")
        )
        alignment_atoms = selected_atoms(
            topology, string_value(selections, "alignment_mask")
        )
        anchor = single_atom(topology, string_value(selections, "anchor_atom_mask"))
        point_a_atoms = [
            single_atom(topology, mask)
            for mask in mask_list(selections, "axis_point_a_masks")
        ]
        point_b_atoms = [
            single_atom(topology, mask)
            for mask in mask_list(selections, "axis_point_b_masks")
        ]
        if {atom.idx for atom in protein_atoms} & {atom.idx for atom in ligand_atoms}:
            raise ValueError("protein_mask and ligand_mask overlap")
        if not {atom.idx for atom in ligand_heavy}.issubset({atom.idx for atom in ligand_atoms}):
            raise ValueError("ligand_heavy_atom_mask must be a subset of ligand_mask")

        point_a = center_of_mass(point_a_atoms)
        point_b = center_of_mass(point_b_atoms)
        ligand_center = center_of_mass(ligand_heavy)
        axis = subtract(point_b, point_a)
        axis_length = norm(axis)
        if axis_length == 0.0:
            raise ValueError("funnel axis points coincide")
        unit_axis = tuple(value / axis_length for value in axis)
        ligand_vector = subtract(ligand_center, point_a)
        projection_angstrom = dot(ligand_vector, unit_axis)
        perpendicular = tuple(
            ligand_vector[index] - projection_angstrom * unit_axis[index]
            for index in range(3)
        )
        projection_nm = projection_angstrom / 10.0
        distance_nm = norm(perpendicular) / 10.0

        zcc = positive_float(funnel, "zcc")
        radius = positive_float(funnel, "cylinder_radius")
        alpha = positive_float(funnel, "alpha")
        if alpha >= math.pi / 2.0:
            raise ValueError("alpha must be smaller than pi/2")
        minimum = float(funnel.get("minimum_projection"))
        if projection_nm <= zcc:
            allowed_radius = radius + math.tan(alpha) * (zcc - projection_nm)
        else:
            allowed_radius = radius
        if projection_nm <= minimum:
            raise ValueError(
                f"Initial ligand projection is below minimum: {projection_nm:.3f} nm"
            )
        if distance_nm >= allowed_radius:
            raise ValueError(
                "Initial ligand COM is outside the funnel: "
                f"distance={distance_nm:.3f}, radius={allowed_radius:.3f} nm"
            )
    except (TypeError, ValueError) as error:
        raise SystemExit(f"Funnel setup error: {error}") from None

    args.output.mkdir(parents=True, exist_ok=True)
    write_reference(args.output / "funnel-reference.pdb", alignment_atoms)
    points_nm = ",".join(f"{value / 10.0:.6f}" for value in point_a + point_b)
    context = f"""[groups]
protein_atoms = "{compress_atom_numbers(protein_atoms)}"
ligand_atoms = "{compress_atom_numbers(ligand_atoms)}"
ligand_heavy_atoms = "{compress_atom_numbers(ligand_heavy)}"

[geometry]
anchor_atom = {anchor.idx + 1}
points_nm = "{points_nm}"
reference_file = "funnel-reference.pdb"
initial_projection_nm = {projection_nm:.6f}
initial_distance_nm = {distance_nm:.6f}
initial_allowed_radius_nm = {allowed_radius:.6f}
"""
    (args.output / "funnel_context.toml").write_text(context, encoding="utf-8")
    (args.output / "atom_count.txt").write_text(
        f"{len(topology.atoms)}\n", encoding="ascii"
    )
    print(
        "Funnel geometry: "
        f"projection={projection_nm:.3f} nm, distance={distance_nm:.3f} nm, "
        f"allowed radius={allowed_radius:.3f} nm"
    )


if __name__ == "__main__":
    main()
