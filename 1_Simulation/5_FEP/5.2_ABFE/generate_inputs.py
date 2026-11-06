#!/usr/bin/env python3
"""Generate ABFE restraint, charge and vdW inputs for 65 lambda windows."""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path

import parmed
from parmed.geometry import dihedral as parmed_dihedral


UNIFORM = [index / 10 for index in range(11)]
VDW = [0.000, 0.010, 0.025, 0.050, 0.100, 0.200, 0.300, 0.400,
       0.500, 0.600, 0.700, 0.800, 0.900, 0.950, 0.975, 1.000]
STAGES = [
    ("restraint", "complex", UNIFORM),
    ("complex_charge", "complex", UNIFORM),
    ("complex_vdw", "complex", VDW),
    ("solvent_charge", "solvent", UNIFORM),
    ("solvent_vdw", "solvent", VDW),
]
RestraintRecord = tuple[str, list[object], float, float]
LIGAND_RESIDUE = "JZ4"
# Production writes the six Boresch restraint values at the MBAR sampling
# interval (ntpr in inputs/production.in.template).
RESTRAINT_SAMPLE_INTERVAL_STEPS = 5000
RESTRAINT_DUMP_FILE = "production.restraint.dat"


def window_directory(
    work_dir: Path,
    stage: str,
    environment: str,
    window: str,
) -> Path:
    if stage == "restraint":
        interaction = "restraint"
    elif stage.endswith("_charge"):
        interaction = "charge"
    elif stage.endswith("_vdw"):
        interaction = "vdw"
    else:
        raise SystemExit(f"Unsupported ABFE stage: {stage}")
    return work_dir / interaction / environment / window


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", type=Path)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("protein_anchor_residue", type=int)
    return parser.parse_args()


def vector(a: list[float], b: list[float]) -> list[float]:
    return [b[index] - a[index] for index in range(3)]


def dot(a: list[float], b: list[float]) -> float:
    return sum(left * right for left, right in zip(a, b))


def norm(a: list[float]) -> float:
    return math.sqrt(dot(a, a))


def distance(a: list[float], b: list[float]) -> float:
    return norm(vector(a, b))


def angle(a: list[float], b: list[float], c: list[float]) -> float:
    left, right = vector(b, a), vector(b, c)
    cosine = max(-1.0, min(1.0, dot(left, right) / (norm(left) * norm(right))))
    return math.degrees(math.acos(cosine))


def dihedral(a: list[float], b: list[float], c: list[float], d: list[float]) -> float:
    return float(parmed_dihedral(a, b, c, d))


def atom_by_name(residue: object, name: str) -> object:
    matches = [atom for atom in residue.atoms if atom.name == name]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one atom named {name} in {residue.name}.")
    return matches[0]


def restraint_records(
    topology: object,
    protein_anchor_residue: int,
) -> list[RestraintRecord]:
    protein = topology.residues[protein_anchor_residue - 1]
    if protein.name != "GLN":
        raise SystemExit(
            f"Protein anchor residue is not GLN: {protein_anchor_residue} {protein.name}"
        )
    ligand_matches = [residue for residue in topology.residues if residue.name == LIGAND_RESIDUE]
    if len(ligand_matches) != 1:
        raise SystemExit(f"Expected exactly one {LIGAND_RESIDUE} residue, found {len(ligand_matches)}")
    ligand = ligand_matches[0]
    p1, p2, p3 = [atom_by_name(protein, name) for name in ("CG", "CB", "CA")]
    l1, l2, l3 = [atom_by_name(ligand, name) for name in ("C7", "C8", "C9")]
    xyz = lambda atom: list(topology.coordinates[atom.idx])
    return [
        ("distance", [p1, l1], distance(xyz(p1), xyz(l1)), 5.0),
        ("angle_a", [p2, p1, l1], angle(xyz(p2), xyz(p1), xyz(l1)), 100.0),
        ("angle_b", [p1, l1, l2], angle(xyz(p1), xyz(l1), xyz(l2)), 100.0),
        ("dihedral_a", [p3, p2, p1, l1], dihedral(xyz(p3), xyz(p2), xyz(p1), xyz(l1)), 100.0),
        ("dihedral_b", [p2, p1, l1, l2], dihedral(xyz(p2), xyz(p1), xyz(l1), xyz(l2)), 100.0),
        ("dihedral_c", [p1, l1, l2, l3], dihedral(xyz(p1), xyz(l1), xyz(l2), xyz(l3)), 100.0),
    ]


def restraint_bounds(kind: str, reference: float) -> tuple[float, float]:
    """Return AMBER r1/r4; the potential is harmonic between them and linear outside."""
    width = 2.0 if kind == "distance" else 180.0
    return reference - width, reference + width


def write_restraints(
    path: Path,
    records: list[RestraintRecord],
    scale: float,
) -> None:
    lines: list[str] = []
    for kind, atoms, reference, force in records:
        indices = ",".join(str(atom.idx + 1) for atom in atoms)
        lower, upper = restraint_bounds(kind, reference)
        lines.append(
            f"&rst iat={indices}, r1={lower:.6f}, r2={reference:.6f}, "
            f"r3={reference:.6f}, r4={upper:.6f}, "
            f"rk2={force*scale:.6f}, rk3={force*scale:.6f}, /"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render(template: Path, output: Path, replacements: dict[str, str]) -> None:
    text = template.read_text(encoding="utf-8")
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    if "@" in text:
        raise SystemExit(f"Unreplaced marker found: {output}")
    output.write_text(text, encoding="utf-8")


def relative_link(target: Path, link: Path) -> None:
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(os.path.relpath(target, link.parent))


def write_uncharged_topology(source: Path, destination: Path) -> None:
    topology = parmed.load_file(str(source))
    ligand_residues = [residue for residue in topology.residues if residue.name == "JZ4"]
    if len(ligand_residues) != 1:
        raise SystemExit(f"Expected exactly one JZ4 residue in {source}.")
    for atom in ligand_residues[0].atoms:
        atom.charge = 0.0
    topology.save(str(destination), overwrite=True)


def ligand_residue_numbers(topology: object) -> list[int]:
    return [
        residue.idx + 1
        for residue in topology.residues
        if residue.name == LIGAND_RESIDUE
    ]


def check_charge_topology(
    work_dir: Path,
    environment: str,
    records: list[RestraintRecord],
) -> tuple[str, str]:
    """Check the two-copy charge topology and return the two copy masks.

    LEaP appends the second ligand copy after the solute, so every solute atom,
    including the restraint anchors, keeps its index from the single-copy build.
    """
    build_dir = work_dir / "build"
    single = parmed.load_file(str(build_dir / f"{environment}.parm7"))
    double = parmed.load_file(
        str(build_dir / f"{environment}_charge.parm7"),
        xyz=str(build_dir / f"{environment}_charge.rst7"),
    )
    single_ligands = ligand_residue_numbers(single)
    double_ligands = ligand_residue_numbers(double)
    if len(single_ligands) != 1 or len(double_ligands) != 2:
        raise SystemExit(
            f"Expected one {LIGAND_RESIDUE} in {environment}.parm7 and two in "
            f"{environment}_charge.parm7, found {len(single_ligands)} and {len(double_ligands)}"
        )
    first_copy, second_copy = double_ligands
    if first_copy != single_ligands[0]:
        raise SystemExit(
            f"The first {LIGAND_RESIDUE} copy moved in {environment}_charge.parm7: "
            f"residue {first_copy}, expected {single_ligands[0]}"
        )

    first_atoms = double.residues[first_copy - 1].atoms
    second_atoms = double.residues[second_copy - 1].atoms
    if len(first_atoms) != len(second_atoms):
        raise SystemExit(f"The two {LIGAND_RESIDUE} copies differ in size: {environment}_charge.parm7")
    for first, second in zip(first_atoms, second_atoms):
        same_coordinates = all(
            abs(double.coordinates[first.idx][axis] - double.coordinates[second.idx][axis]) < 1.0e-3
            for axis in range(3)
        )
        if first.name != second.name or first.charge != second.charge or not same_coordinates:
            raise SystemExit(
                f"The two {LIGAND_RESIDUE} copies differ in {environment}_charge.parm7 at atom {first.name}"
            )

    if environment == "complex":
        for kind, atoms, _, _ in records:
            for atom in atoms:
                copied = double.atoms[atom.idx]
                if (copied.name, copied.residue.name, copied.residue.idx) != (
                    atom.name, atom.residue.name, atom.residue.idx
                ):
                    raise SystemExit(
                        f"Restraint {kind} atom {atom.idx + 1} differs in complex_charge.parm7"
                    )
    return f":{first_copy}", f":{second_copy}"


def alchemical_options(
    stage: str,
    lambda_value: float,
    schedule: list[float],
    collect_mbar: bool,
    charge_masks: tuple[str, str] | None = None,
) -> str:
    if stage == "restraint":
        # Ordinary MD with lambda-scaled DISANG force constants; anal.py
        # rebuilds the MBAR energies from the DUMPAVE restraint values.
        return ""
    common = f"icfe=1, clambda={lambda_value:.6f}, "
    if stage.endswith("vdw"):
        common += (
            " timask1=':JZ4', timask2='',"
            " ifsc=1, scmask1=':JZ4', scmask2='', scalpha=0.5, scbeta=12.0,"
            " aces26=1, gti_sc_cc_energy_terms='ele,vdw,ele14,vdw14',"
            " gti_sc_sc_energy_terms='', gti_nmropt=0,"
        )
    else:
        # Linear TI between two identical ligand copies (Amber manual 27.1.8.1):
        # V0 keeps the charged first copy, V1 the second copy uncharged by crgmask.
        first_copy, second_copy = charge_masks
        common += (
            f" timask1='{first_copy}', timask2='{second_copy}',"
            f" crgmask='{second_copy}', ifsc=0,"
        )
    if collect_mbar:
        mbar_lambda = ",".join(f"{value:.6f}" for value in schedule)
        common += (
            f" ifmbar=1, mbar_states={len(schedule)},"
            f" mbar_lambda={mbar_lambda},"
        )
    return common


def prepare_alchemical_topologies(work_dir: Path) -> None:
    """Create the neutral-ligand topologies used by the VDW stages."""
    for environment in ("complex", "solvent"):
        write_uncharged_topology(
            work_dir / "build" / f"{environment}.parm7",
            work_dir / "build" / f"{environment}_uncharged.parm7",
        )


def write_restraint_metadata(work_dir: Path, records: list[RestraintRecord]) -> None:
    """Record the six Boresch restraints in DISANG order for anal.py."""
    lines = ["restraint\treference\tforce_constant\tr1\tr4\tatom_indices"]
    for kind, atoms, reference, force in records:
        atom_indices = ",".join(str(atom.idx + 1) for atom in atoms)
        lower, upper = restraint_bounds(kind, reference)
        lines.append(
            f"{kind}\t{reference:.8f}\t{force:.8f}\t{lower:.8f}\t{upper:.8f}\t{atom_indices}"
        )
    (work_dir / "restraints.tsv").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_window(
    work_dir: Path,
    input_dir: Path,
    stage: str,
    environment: str,
    schedule: list[float],
    window_index: int,
    lambda_value: float,
    state_index: int,
    records: list[RestraintRecord],
    charge_masks: dict[str, tuple[str, str]],
) -> str:
    """Generate links, restraints, and AMBER inputs for one ABFE window."""
    window = f"{window_index:03d}"
    directory = window_directory(work_dir, stage, environment, window)
    directory.mkdir(parents=True, exist_ok=True)

    topology_name = f"{environment}.parm7"
    coordinate_name = f"{environment}.rst7"
    if stage.endswith("vdw"):
        topology_name = f"{environment}_uncharged.parm7"
    elif stage.endswith("charge"):
        topology_name = f"{environment}_charge.parm7"
        coordinate_name = f"{environment}_charge.rst7"
    relative_link(work_dir / "build" / topology_name, directory / "system.parm7")
    relative_link(work_dir / "build" / coordinate_name, directory / "system.rst7")

    # The restraint stage is fully restrained at lambda 0 and unrestrained at
    # lambda 1. Charge and vdW complex windows keep the full restraint.
    if environment == "solvent":
        restraint_scale = 0.0
    elif stage == "restraint":
        restraint_scale = 1.0 - lambda_value
    else:
        restraint_scale = 1.0
    write_restraints(directory / "disang.rest", records, restraint_scale)

    replacements = {
        "@STAGE@": stage,
        "@LAMBDA@": f"{lambda_value:.6f}",
        "@RANDOM_SEED@": str(61000 + state_index),
        "@RESTRAINT_OPTIONS@": "nmropt=1," if environment == "complex" else "",
        "@WT_END@": "&wt type='END', /" if environment == "complex" else "",
        "@DISANG@": "DISANG=disang.rest" if environment == "complex" else "",
    }
    for name in ("heat", "equilibrate", "production"):
        replacements["@ALCHEMICAL_OPTIONS@"] = alchemical_options(
            stage,
            lambda_value,
            schedule,
            collect_mbar=name == "production",
            charge_masks=charge_masks.get(environment),
        )
        if stage == "restraint" and name == "production":
            replacements["@WT_END@"] = (
                f"&wt type='DUMPFREQ', istep1={RESTRAINT_SAMPLE_INTERVAL_STEPS}, /\n"
                "&wt type='END', /"
            )
            replacements["@DISANG@"] = f"DISANG=disang.rest\nDUMPAVE={RESTRAINT_DUMP_FILE}"
        render(
            input_dir / f"{name}.in.template",
            directory / f"{name}.in",
            replacements,
        )
    render(input_dir / "minimize.in", directory / "minimize.in", replacements)

    return (
        f"{stage}\t{environment}\t{window}\t{lambda_value:.6f}\t"
        f"{61000 + state_index}\t{directory}"
    )


def main() -> None:
    args = parse_arguments()
    topology = parmed.load_file(
        str(args.work_dir / "build" / "complex.parm7"),
        xyz=str(args.work_dir / "build" / "complex.rst7"),
    )
    prepare_alchemical_topologies(args.work_dir)
    records = restraint_records(topology, args.protein_anchor_residue)
    write_restraint_metadata(args.work_dir, records)
    charge_masks = {
        environment: check_charge_topology(args.work_dir, environment, records)
        for environment in ("complex", "solvent")
    }

    states = ["stage\tenvironment\twindow\tlambda\tseed\tdirectory"]
    state_index = 0
    for stage, environment, schedule in STAGES:
        for window_index, lambda_value in enumerate(schedule):
            state_index += 1
            states.append(
                write_window(
                    args.work_dir,
                    args.input_dir,
                    stage,
                    environment,
                    schedule,
                    window_index,
                    lambda_value,
                    state_index,
                    records,
                    charge_masks,
                )
            )
    (args.work_dir / "states.tsv").write_text("\n".join(states) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
