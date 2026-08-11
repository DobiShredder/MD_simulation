#!/usr/bin/env python3
"""Prepare T4 lysozyme-JZ4 ABFE coordinates from 3HTB."""

from __future__ import annotations

import argparse
from pathlib import Path


JZ4_ATOM_NAMES = {
    "C4": "C1",
    "C7": "C2",
    "C8": "C3",
    "C9": "C4",
    "C10": "C5",
    "C11": "C6",
    "C12": "C7",
    "C13": "C8",
    "C14": "C9",
    "OAB": "O1",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare the T4 lysozyme–JZ4 complex from PDB 3HTB for ABFE."
    )
    parser.add_argument("input_pdb", type=Path)
    parser.add_argument("output_pdb", type=Path)
    return parser.parse_args()


def first_conformer(line: str) -> str | None:
    alternate_location = line[16:17]
    if alternate_location not in {" ", "A"}:
        return None
    if alternate_location == "A":
        return f"{line[:16]} {line[17:]}"
    return line


def rename_residue(line: str, residue_name: str) -> str:
    return f"{line[:17]}{residue_name:>3}{line[20:]}"


def rename_atom(line: str, atom_name: str) -> str:
    return f"{line[:12]}{atom_name:>4}{line[16:]}"


def main() -> None:
    args = parse_arguments()
    if not args.input_pdb.is_file():
        raise SystemExit(f"Input PDB not found: {args.input_pdb}")

    protein: list[str] = []
    ligand: list[str] = []

    for raw_line in args.input_pdb.read_text(encoding="ascii").splitlines():
        line = first_conformer(raw_line)
        if line is None:
            continue

        if line.startswith("ATOM  "):
            if line[17:20].strip() == "HIS":
                line = rename_residue(line, "HIE")
            protein.append(line)
            continue

        if not line.startswith("HETATM") or line[17:20].strip() != "JZ4":
            continue

        source_name = line[12:16].strip()
        if source_name not in JZ4_ATOM_NAMES:
            raise SystemExit(f"Unknown JZ4 atom name: {source_name}")
        line = rename_atom(line, JZ4_ATOM_NAMES[source_name])
        ligand.append(f"{line[:22]}{164:4d}{line[26:]}")

    protein_residues = {
        (line[21:22], line[22:26], line[26:27])
        for line in protein
    }
    ligand_names = {line[12:16].strip() for line in ligand}
    if len(protein) != 1300 or len(protein_residues) != 163:
        raise SystemExit(
            "Unexpected 3HTB protein atom/residue counts: "
            f"{len(protein)} atoms, {len(protein_residues)} residues"
        )
    if ligand_names != set(JZ4_ATOM_NAMES.values()):
        raise SystemExit(f"Expected 10 JZ4 heavy atoms: {ligand_names}")

    args.output_pdb.parent.mkdir(parents=True, exist_ok=True)
    output_lines = protein + ["TER"] + ligand + ["TER", "END"]
    args.output_pdb.write_text("\n".join(output_lines) + "\n", encoding="ascii")
    args.output_pdb.with_name("preparation.tsv").write_text(
        "field\tvalue\n"
        "protein_residues\t163\n"
        "protein_anchor_residue\t102\n"
        "protein_anchor_atoms\tCG,CB,CA\n"
        "ligand_anchor_atoms\tC7,C8,C9\n"
        "ligand_residue\tJZ4\n",
        encoding="utf-8",
    )

    print(f"ABFE coordinate: {args.output_pdb}")


if __name__ == "__main__":
    main()
