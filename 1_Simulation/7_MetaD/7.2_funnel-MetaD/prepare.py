#!/usr/bin/env python3
"""3PTB protein, BEN, Ca2+와 funnel axis residue mapping을 준비한다."""

from __future__ import annotations

import argparse
from pathlib import Path


ResidueKey = tuple[str, str, str]

AXIS_RESIDUES = {
    "LEU185": ("A", "185", " "),
    "CYS220": ("A", "220", " "),
    "LYS224": ("A", "224", " "),
    "PRO225": ("A", "225", " "),
    "GLY226": ("A", "226", " "),
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PDB 3PTB를 Funnel MetaD build용으로 전처리합니다."
    )
    parser.add_argument("input_pdb", type=Path)
    parser.add_argument("output_pdb", type=Path)
    return parser.parse_args()


def residue_key(line: str) -> ResidueKey:
    return line[21:22], line[22:26].strip(), line[26:27]


def read_disulfides(lines: list[str]) -> list[tuple[ResidueKey, ResidueKey]]:
    pairs = []

    for line in lines:
        if line.startswith("SSBOND"):
            first = (line[15:16], line[17:21].strip(), line[21:22])
            second = (line[29:30], line[31:35].strip(), line[35:36])
            pairs.append((first, second))

    return pairs


def main() -> None:
    args = parse_arguments()

    if not args.input_pdb.is_file():
        raise SystemExit(f"입력 PDB를 찾을 수 없습니다: {args.input_pdb}")

    lines = args.input_pdb.read_text(encoding="ascii").splitlines()
    disulfide_pairs = read_disulfides(lines)

    if len(disulfide_pairs) != 6:
        raise SystemExit(f"3PTB SSBOND 6개가 필요합니다: {len(disulfide_pairs)}")

    disulfide_residues = {
        residue
        for pair in disulfide_pairs
        for residue in pair
    }
    protein = []
    ligand = []
    calcium = []
    residue_indices: dict[ResidueKey, int] = {}

    for line in lines:
        alternate_location = line[16:17]

        if alternate_location not in {" ", "A"}:
            continue

        if alternate_location == "A":
            line = f"{line[:16]} {line[17:]}"

        if line.startswith("ATOM  "):
            key = residue_key(line)

            if key not in residue_indices:
                residue_indices[key] = len(residue_indices) + 1

            if key in disulfide_residues:
                line = f"{line[:17]}CYX{line[20:]}"

            line = f"{line[:22]}{residue_indices[key]:4d}{line[26:]}"
            protein.append(line)

        elif line.startswith("HETATM"):
            residue_name = line[17:20].strip()

            if residue_name == "BEN":
                if line[12:16].strip() == "C":
                    line = f"{line[:12]} C7 {line[16:]}"
                ligand.append(line)
            elif residue_name == "CA":
                calcium.append(line)

    if len(protein) != 1629 or len(ligand) != 9 or len(calcium) != 1:
        raise SystemExit(
            "예상하지 못한 3PTB atom 구성입니다: "
            f"protein={len(protein)}, BEN={len(ligand)}, CA={len(calcium)}"
        )

    missing_axis_residues = [
        label for label, key in AXIS_RESIDUES.items()
        if key not in residue_indices
    ]

    if missing_axis_residues:
        raise SystemExit(f"Funnel axis residue를 찾지 못했습니다: {missing_axis_residues}")

    protein_residues = len(residue_indices)
    ligand = [
        f"{line[:22]}{protein_residues + 1:4d}{line[26:]}"
        for line in ligand
    ]
    calcium = [
        f"{line[:22]}{protein_residues + 2:4d}{line[26:]}"
        for line in calcium
    ]

    args.output_pdb.parent.mkdir(parents=True, exist_ok=True)
    args.output_pdb.write_text(
        "\n".join(protein + ["TER"] + ligand + ["TER"] + calcium + ["END"]) + "\n",
        encoding="ascii",
    )

    bond_lines = [
        f"bond system.{residue_indices[first]}.SG system.{residue_indices[second]}.SG"
        for first, second in disulfide_pairs
    ]
    args.output_pdb.with_name("disulfides.leap").write_text(
        "\n".join(bond_lines) + "\n",
        encoding="ascii",
    )

    mapping_lines = ["label\tresidue"]
    for label, key in AXIS_RESIDUES.items():
        mapping_lines.append(f"{label}\t{residue_indices[key]}")
    mapping_lines.append(f"BEN\t{protein_residues + 1}")
    args.output_pdb.with_name("funnel_residues.tsv").write_text(
        "\n".join(mapping_lines) + "\n",
        encoding="ascii",
    )

    print(
        f"Funnel MetaD 전처리 결과: {args.output_pdb} "
        f"({protein_residues} protein residues, BEN 9 atoms, Ca2+ 1개)"
    )


if __name__ == "__main__":
    main()
