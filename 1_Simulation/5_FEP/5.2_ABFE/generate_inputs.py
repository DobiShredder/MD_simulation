#!/usr/bin/env python3
"""ABFE restraint와 65개 alchemical window input을 생성합니다."""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path

import parmed


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
        raise SystemExit(f"지원하지 않는 ABFE stage입니다: {stage}")
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


def cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def norm(a: list[float]) -> float:
    return math.sqrt(dot(a, a))


def distance(a: list[float], b: list[float]) -> float:
    return norm(vector(a, b))


def angle(a: list[float], b: list[float], c: list[float]) -> float:
    left, right = vector(b, a), vector(b, c)
    cosine = max(-1.0, min(1.0, dot(left, right) / (norm(left) * norm(right))))
    return math.degrees(math.acos(cosine))


def dihedral(a: list[float], b: list[float], c: list[float], d: list[float]) -> float:
    b0, b1, b2 = vector(b, a), vector(b, c), vector(c, d)
    normal1, normal2 = cross(b0, b1), cross(b1, b2)
    x = dot(normal1, normal2)
    y = dot(cross(normal1, normal2), b1) / norm(b1)
    return math.degrees(math.atan2(y, x))


def atom_by_name(residue: object, name: str) -> object:
    matches = [atom for atom in residue.atoms if atom.name == name]
    if len(matches) != 1:
        raise SystemExit(f"{residue.name}에서 atom {name}을 하나만 찾지 못했습니다.")
    return matches[0]


def restraint_records(
    topology: object,
    protein_anchor_residue: int,
) -> list[tuple[str, list[object], float, float]]:
    protein = topology.residues[protein_anchor_residue - 1]
    if protein.name != "GLN":
        raise SystemExit(
            f"Protein anchor residue가 GLN이 아닙니다: {protein_anchor_residue} {protein.name}"
        )
    ligand_matches = [residue for residue in topology.residues if residue.name == "JZ4"]
    if len(ligand_matches) != 1:
        raise SystemExit(f"JZ4 residue를 하나만 찾지 못했습니다: {len(ligand_matches)}")
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


def write_restraints(path: Path, records: list[tuple[str, list[object], float, float]], scale: float) -> None:
    lines: list[str] = []
    for kind, atoms, reference, force in records:
        indices = ",".join(str(atom.idx + 1) for atom in atoms)
        width = 2.0 if kind == "distance" else 180.0
        lines.append(
            f"&rst iat={indices}, r1={reference-width:.6f}, r2={reference:.6f}, "
            f"r3={reference:.6f}, r4={reference+width:.6f}, "
            f"rk2={force*scale:.6f}, rk3={force*scale:.6f}, /"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render(template: Path, output: Path, replacements: dict[str, str]) -> None:
    text = template.read_text(encoding="utf-8")
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    if "@" in text:
        raise SystemExit(f"치환되지 않은 marker가 있습니다: {output}")
    output.write_text(text, encoding="utf-8")


def relative_link(target: Path, link: Path) -> None:
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(os.path.relpath(target, link.parent))


def write_uncharged_topology(source: Path, destination: Path) -> None:
    topology = parmed.load_file(str(source))
    ligand_residues = [residue for residue in topology.residues if residue.name == "JZ4"]
    if len(ligand_residues) != 1:
        raise SystemExit(f"{source}에서 JZ4 residue를 하나만 찾지 못했습니다.")
    for atom in ligand_residues[0].atoms:
        atom.charge = 0.0
    topology.save(str(destination), overwrite=True)


def alchemical_options(
    stage: str,
    lambda_value: float,
    schedule: list[float],
    collect_mbar: bool,
) -> str:
    common = f"icfe=1, clambda={lambda_value:.6f}, timask1=':JZ4', timask2='', "
    if stage == "restraint":
        common += (
            " ifsc=0, aces26=1, gti_nmropt=1,"
            " gti_sc_cc_energy_terms='', gti_sc_sc_energy_terms='',"
        )
    elif stage.endswith("vdw"):
        common += (
            " ifsc=1, scmask1=':JZ4', scmask2='', scalpha=0.5, scbeta=12.0,"
            " aces26=1, gti_sc_cc_energy_terms='ele,vdw,ele14,vdw14',"
            " gti_sc_sc_energy_terms='', gti_nmropt=0,"
        )
    else:
        common += " crgmask=':JZ4', ifsc=0,"
    if collect_mbar:
        mbar_lambda = ",".join(f"{value:.6f}" for value in schedule)
        common += (
            f" ifmbar=1, mbar_states={len(schedule)},"
            f" mbar_lambda={mbar_lambda},"
        )
    return common


def main() -> None:
    args = parse_arguments()
    topology = parmed.load_file(
        str(args.work_dir / "build" / "complex.parm7"),
        xyz=str(args.work_dir / "build" / "complex.rst7"),
    )
    for environment in ("complex", "solvent"):
        write_uncharged_topology(
            args.work_dir / "build" / f"{environment}.parm7",
            args.work_dir / "build" / f"{environment}_uncharged.parm7",
        )
    records = restraint_records(topology, args.protein_anchor_residue)
    metadata = ["restraint\treference\tforce_constant\tatom_indices"]
    for kind, atoms, reference, force in records:
        atom_indices = ",".join(str(atom.idx + 1) for atom in atoms)
        metadata.append(
            f"{kind}\t{reference:.8f}\t{force:.8f}\t{atom_indices}"
        )
    (args.work_dir / "restraints.tsv").write_text("\n".join(metadata) + "\n", encoding="utf-8")

    states = ["stage\tenvironment\twindow\tlambda\tseed\tdirectory"]
    state_index = 0
    for stage, environment, schedule in STAGES:
        for window_index, lambda_value in enumerate(schedule):
            state_index += 1
            window = f"{window_index:03d}"
            directory = window_directory(args.work_dir, stage, environment, window)
            directory.mkdir(parents=True, exist_ok=True)
            topology_name = (
                f"{environment}_uncharged.parm7"
                if stage.endswith("vdw")
                else f"{environment}.parm7"
            )
            relative_link(args.work_dir / "build" / topology_name, directory / "system.parm7")
            relative_link(
                args.work_dir / "build" / f"{environment}.rst7",
                directory / "system.rst7",
            )
            restraint_scale = 1.0 if environment == "complex" else 0.0
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
                )
                render(args.input_dir / f"{name}.in.template", directory / f"{name}.in", replacements)
            (directory / "minimize.in").write_text(
                (args.input_dir / "minimize.in").read_text(encoding="utf-8"), encoding="utf-8"
            )
            states.append(
                f"{stage}\t{environment}\t{window}\t{lambda_value:.6f}\t"
                f"{61000 + state_index}\t{directory}"
            )
    (args.work_dir / "states.tsv").write_text("\n".join(states) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
