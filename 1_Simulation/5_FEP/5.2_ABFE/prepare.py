#!/usr/bin/env python3
"""3PTB에서 ABFE complex와 Boresch anchor metadata를 준비합니다."""

from __future__ import annotations

import argparse
from pathlib import Path


ResidueKey = tuple[str, str, str]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PDB 3PTB를 ABFE build용으로 전처리합니다.")
    parser.add_argument("input_pdb", type=Path)
    parser.add_argument("output_pdb", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    if not args.input_pdb.is_file():
        raise SystemExit(f"입력 PDB를 찾을 수 없습니다: {args.input_pdb}")

    lines = args.input_pdb.read_text(encoding="ascii").splitlines()
    disulfides: list[tuple[ResidueKey, ResidueKey]] = []
    for line in lines:
        if line.startswith("SSBOND"):
            first = (line[15:16], line[17:21].strip(), line[21:22])
            second = (line[29:30], line[31:35].strip(), line[35:36])
            disulfides.append((first, second))
    if len(disulfides) != 6:
        raise SystemExit(f"3PTB disulfide pair 6개가 필요합니다: {len(disulfides)}")

    disulfide_residues = {residue for pair in disulfides for residue in pair}
    protein: list[str] = []
    ligand: list[str] = []
    calcium: list[str] = []
    residue_indices: dict[ResidueKey, int] = {}
    counts = {"protein": 0, "BEN": 0, "CA": 0}
    asp189_key: ResidueKey | None = None

    for line in lines:
        record = line[:6]
        alternate = line[16:17]
        residue_name = line[17:20].strip()
        if alternate not in {" ", "A"}:
            continue
        if record == "ATOM  ":
            key = (line[21:22], line[22:26].strip(), line[26:27])
            if key not in residue_indices:
                residue_indices[key] = len(residue_indices) + 1
            if residue_name == "ASP" and key[1] == "189":
                asp189_key = key
            if key in disulfide_residues:
                line = f"{line[:17]}CYX{line[20:]}"
            if alternate == "A":
                line = f"{line[:16]} {line[17:]}"
            line = f"{line[:22]}{residue_indices[key]:4d}{line[26:]}"
            protein.append(line)
            counts["protein"] += 1
        elif record == "HETATM" and residue_name in {"BEN", "CA"}:
            if residue_name == "BEN":
                if line[12:16].strip() == "C":
                    line = f"{line[:12]} C7 {line[16:]}"
                ligand.append(line)
            else:
                calcium.append(line)
            counts[residue_name] += 1

    if counts["protein"] != 1629 or counts["BEN"] != 9 or counts["CA"] != 1:
        raise SystemExit(f"예상하지 못한 3PTB 구성입니다: {counts}")
    if asp189_key is None:
        raise SystemExit("Asp189를 찾지 못했습니다.")

    args.output_pdb.parent.mkdir(parents=True, exist_ok=True)
    ligand = [
        f"{line[:22]}{len(residue_indices) + 1:4d}{line[26:]}"
        for line in ligand
    ]
    calcium = [
        f"{line[:22]}{len(residue_indices) + 2:4d}{line[26:]}"
        for line in calcium
    ]
    output_lines = protein + ["TER"] + ligand + ["TER"] + calcium + ["TER", "END"]
    args.output_pdb.write_text("\n".join(output_lines) + "\n", encoding="ascii")

    bond_lines = []
    for first, second in disulfides:
        bond_lines.append(
            f"bond system.{residue_indices[first]}.SG system.{residue_indices[second]}.SG"
        )
    args.output_pdb.with_name("disulfides.leap").write_text(
        "\n".join(bond_lines) + "\n", encoding="ascii"
    )
    args.output_pdb.with_name("preparation.tsv").write_text(
        "field\tvalue\n"
        f"protein_residues\t{len(residue_indices)}\n"
        f"asp189_residue\t{residue_indices[asp189_key]}\n"
        "protein_anchor_atoms\tCA,CB,CG\n"
        "ligand_anchor_atoms\tC,C1,C2\n"
        "ligand_residue\tBEN\n",
        encoding="utf-8",
    )
    print(f"ABFE coordinate: {args.output_pdb}")


if __name__ == "__main__":
    main()
