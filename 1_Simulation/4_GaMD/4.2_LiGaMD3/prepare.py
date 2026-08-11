#!/usr/bin/env python3
"""Prepare 3PTB protein, BEN, Ca2+, and LiGaMD3 build metadata."""

from __future__ import annotations

import argparse
from pathlib import Path

ResidueKey = tuple[str, str, str]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare PDB 3PTB for the LiGaMD3 build.")
    parser.add_argument("input_pdb", type=Path)
    parser.add_argument("output_pdb", type=Path)
    return parser.parse_args()


def residue_key(line: str) -> ResidueKey:
    return line[21:22], line[22:26].strip(), line[26:27]


def disulfides(lines: list[str]) -> list[tuple[ResidueKey, ResidueKey]]:
    pairs = []
    for line in lines:
        if line.startswith("SSBOND"):
            first = (line[15:16], line[17:21].strip(), line[21:22])
            second = (line[29:30], line[31:35].strip(), line[35:36])
            pairs.append((first, second))
    return pairs


def main() -> None:
    args = arguments()
    if not args.input_pdb.is_file():
        raise SystemExit(f"Input PDB not found: {args.input_pdb}")

    lines = args.input_pdb.read_text(encoding="ascii").splitlines()
    pairs = disulfides(lines)
    if len(pairs) != 6:
        raise SystemExit(f"Expected 6 SSBOND records in 3PTB, found {len(pairs)}")
    cyx = {residue for pair in pairs for residue in pair}

    protein: list[str] = []
    ligand: list[str] = []
    calcium: list[str] = []
    residue_indices: dict[ResidueKey, int] = {}
    residue_names: dict[ResidueKey, str] = {}

    for line in lines:
        alternate = line[16:17]
        if alternate not in {" ", "A"}:
            continue
        if alternate == "A":
            line = f"{line[:16]} {line[17:]}"

        if line.startswith("ATOM  "):
            key = residue_key(line)
            if key not in residue_indices:
                residue_indices[key] = len(residue_indices) + 1
                residue_names[key] = line[17:20].strip()
            if key in cyx:
                line = f"{line[:17]}CYX{line[20:]}"
            line = f"{line[:22]}{residue_indices[key]:4d}{line[26:]}"
            protein.append(line)
        elif line.startswith("HETATM"):
            name = line[17:20].strip()
            if name == "BEN":
                if line[12:16].strip() == "C":
                    line = f"{line[:12]} C7 {line[16:]}"
                ligand.append(line)
            elif name == "CA":
                calcium.append(line)

    if len(protein) != 1629 or len(ligand) != 9 or len(calcium) != 1:
        raise SystemExit(
            "Unexpected 3PTB atom composition: "
            f"protein={len(protein)}, BEN={len(ligand)}, CA={len(calcium)}"
        )

    asp189 = [
        index for key, index in residue_indices.items()
        if key[1] == "189" and residue_names[key] == "ASP"
    ]
    if len(asp189) != 1:
        raise SystemExit(f"Expected exactly one catalytic-pocket Asp189, found {asp189}")

    args.output_pdb.parent.mkdir(parents=True, exist_ok=True)
    ligand = [
        f"{line[:22]}{len(residue_indices) + 1:4d}{line[26:]}"
        for line in ligand
    ]
    calcium = [
        f"{line[:22]}{len(residue_indices) + 2:4d}{line[26:]}"
        for line in calcium
    ]
    args.output_pdb.write_text(
        "\n".join(protein + ["TER"] + ligand + ["TER"] + calcium + ["END"]) + "\n",
        encoding="ascii",
    )

    bond_lines = [
        f"bond system.{residue_indices[first]}.SG system.{residue_indices[second]}.SG"
        for first, second in pairs
    ]
    args.output_pdb.with_name("disulfides.leap").write_text(
        "\n".join(bond_lines) + "\n", encoding="ascii"
    )
    args.output_pdb.with_name("system_metadata.tsv").write_text(
        "key\tvalue\n"
        f"receptor_residues\t{len(residue_indices)}\n"
        f"asp189_residue\t{asp189[0]}\n"
        "ligand_name\tBEN\n",
        encoding="utf-8",
    )
    print(f"Prepared LiGaMD3 structure: {args.output_pdb}")


if __name__ == "__main__":
    main()
