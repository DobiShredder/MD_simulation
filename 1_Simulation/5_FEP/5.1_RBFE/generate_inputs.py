#!/usr/bin/env python3
"""Generate common-core RBFE environment/window directories and AMBER inputs."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import parmed


LAMBDAS = [index / 10 for index in range(11)]
LIGAND_A = "BNZ"
LIGAND_B = "MBN"
# tleap builds the hydrogens of both ligands from mol2 templates, so mapped
# hydrogens differ by about 0.001 A before synchronization. A larger gap means
# the two poses do not overlay and the mapping or preparation is wrong.
CORE_TOLERANCE_ANGSTROM = 0.1


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", type=Path)
    parser.add_argument("input_dir", type=Path)
    return parser.parse_args()


def read_mapping(path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 2:
            raise SystemExit(f"{path}:{line_number}: expected two atom-name columns")
        rows.append((fields[0], fields[1]))
    if not rows:
        raise SystemExit(f"Atom mapping contains no rows: {path}")
    if len({a for a, _ in rows}) != len(rows) or len({b for _, b in rows}) != len(rows):
        raise SystemExit(f"Atom mapping must be one-to-one: {path}")
    return rows


def ligand_atoms(topology: object, residue_name: str) -> dict[str, object]:
    residues = [residue for residue in topology.residues if residue.name == residue_name]
    if len(residues) != 1:
        raise SystemExit(f"Expected one {residue_name} residue, found {len(residues)}")
    return {atom.name: atom for atom in residues[0].atoms}


def common_core(topology: object, mapping: list[tuple[str, str]]) -> tuple[list[str], list[str], list[tuple[object, object]]]:
    """Return the soft-core atom names of each ligand and the mapped atom pairs."""
    atoms_a = ligand_atoms(topology, LIGAND_A)
    atoms_b = ligand_atoms(topology, LIGAND_B)
    for name_a, name_b in mapping:
        if name_a not in atoms_a or name_b not in atoms_b:
            raise SystemExit(f"Mapped atom is absent from the topology: {LIGAND_A}@{name_a} {LIGAND_B}@{name_b}")
    pairs = [(atoms_a[a], atoms_b[b]) for a, b in mapping]

    # pmemd pairs the timask atoms that are not in scmask by their order, so
    # the mapped atoms must appear in the same order in both residues.
    pairs.sort(key=lambda pair: pair[0].idx)
    order_b = [atom_b.idx for _, atom_b in pairs]
    if order_b != sorted(order_b):
        raise SystemExit(
            f"Mapped {LIGAND_B} atoms are not in the same order as their {LIGAND_A} partners; "
            "reorder the mapping or the ligand atoms"
        )

    mapped_a = {atom_a.name for atom_a, _ in pairs}
    mapped_b = {atom_b.name for _, atom_b in pairs}
    unique_a = [name for name in atoms_a if name not in mapped_a]
    unique_b = [name for name in atoms_b if name not in mapped_b]
    return unique_a, unique_b, pairs


def synchronize_core(parm7: Path, rst7: Path, output: Path, pairs: list[tuple[object, object]]) -> float:
    """Copy the MBN core coordinates onto the mapped BNZ atoms."""
    restart = parmed.amber.Rst7.open(str(rst7))
    coordinates = restart.coordinates.reshape(-1, 3)
    largest = 0.0
    for atom_a, atom_b in pairs:
        gap = float(((coordinates[atom_a.idx] - coordinates[atom_b.idx]) ** 2).sum() ** 0.5)
        largest = max(largest, gap)
        coordinates[atom_a.idx] = coordinates[atom_b.idx]
    if largest > CORE_TOLERANCE_ANGSTROM:
        raise SystemExit(
            f"Mapped core atoms differ by {largest:.3f} A (limit {CORE_TOLERANCE_ANGSTROM} A): {parm7}"
        )
    restart.coordinates = coordinates.reshape(1, -1, 3)
    restart.write(str(output))
    return largest


def soft_core_mask(residue_name: str, names: list[str]) -> str:
    if not names:
        return ""
    return f":{residue_name}@{','.join(names)}"


def render(template: Path, output: Path, replacements: dict[str, str]) -> None:
    text = template.read_text(encoding="utf-8")
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    if "@LAMBDA@" in text or "@RANDOM_SEED@" in text or "@SCMASK" in text:
        raise SystemExit(f"Unreplaced marker found: {output}")
    output.write_text(text, encoding="utf-8")


def relative_link(target: Path, link: Path) -> None:
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(os.path.relpath(target, link.parent))


def main() -> None:
    args = parse_arguments()
    mapping = read_mapping(args.input_dir / "atom_mapping.tsv")
    state_rows = ["environment\twindow\tlambda\tseed\tdirectory"]
    state_index = 0
    masks: dict[str, tuple[str, str]] = {}

    for environment in ("complex", "solvent"):
        topology_file = args.work_dir / "build" / f"{environment}.parm7"
        restart_file = args.work_dir / "build" / f"{environment}.rst7"
        core_restart = args.work_dir / "build" / f"{environment}_core.rst7"
        topology = parmed.load_file(str(topology_file))
        unique_a, unique_b, pairs = common_core(topology, mapping)
        largest = synchronize_core(topology_file, restart_file, core_restart, pairs)
        scmask1 = soft_core_mask(LIGAND_A, unique_a)
        scmask2 = soft_core_mask(LIGAND_B, unique_b)
        masks[environment] = (scmask1, scmask2)
        print(
            f"{environment}: {len(pairs)} common-core atoms (largest pre-sync gap {largest:.4f} A); "
            f"scmask1='{scmask1}', scmask2='{scmask2}'"
        )

        for window_index, lambda_value in enumerate(LAMBDAS):
            state_index += 1
            window = f"{window_index:03d}"
            directory = args.work_dir / environment / window
            directory.mkdir(parents=True, exist_ok=True)

            relative_link(topology_file, directory / "system.parm7")
            relative_link(core_restart, directory / "system.rst7")
            replacements = {
                "@LAMBDA@": f"{lambda_value:.1f}",
                "@RANDOM_SEED@": str(51000 + state_index),
                "@SCMASK1@": scmask1,
                "@SCMASK2@": scmask2,
            }
            for stage in ("minimize", "heat", "equilibrate", "production"):
                render(
                    args.input_dir / f"{stage}.in.template",
                    directory / f"{stage}.in",
                    replacements,
                )
            state_rows.append(
                f"{environment}\t{window}\t{lambda_value:.1f}\t"
                f"{51000 + state_index}\t{directory}"
            )

    if masks["complex"] != masks["solvent"]:
        raise SystemExit("Complex and solvent soft-core masks differ; check the ligand atom names")
    (args.work_dir / "states.tsv").write_text("\n".join(state_rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
