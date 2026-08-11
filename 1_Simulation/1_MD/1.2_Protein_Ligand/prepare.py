#!/usr/bin/env python3
"""Prepare T4 lysozyme and bound JZ4 coordinates from 3HTB."""

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
        description="Prepare the T4 lysozyme–JZ4 complex from PDB 3HTB."
    )
    parser.add_argument("input_pdb", type=Path, help="downloaded 3HTB PDB")
    parser.add_argument("output_pdb", type=Path, help="prepared output complex PDB")
    return parser.parse_args()


def select_first_conformer(line: str) -> str | None:
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


def prepare_complex(lines: list[str]) -> tuple[list[str], list[str]]:
    protein: list[str] = []
    ligand: list[str] = []

    for raw_line in lines:
        line = select_first_conformer(raw_line)
        if line is None:
            continue

        if line.startswith("ATOM  "):
            if line[17:20].strip() == "HIS":
                line = rename_residue(line, "HIE")
            protein.append(line)
            continue

        if not line.startswith("HETATM"):
            continue
        if line[17:20].strip() != "JZ4":
            continue

        source_name = line[12:16].strip()
        if source_name not in JZ4_ATOM_NAMES:
            raise SystemExit(f"Unknown JZ4 atom name: {source_name}")

        line = rename_atom(line, JZ4_ATOM_NAMES[source_name])
        line = f"{line[:22]}{164:4d}{line[26:]}"
        ligand.append(line)

    return protein, ligand


def validate_complex(protein: list[str], ligand: list[str]) -> None:
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


def write_complex(output_pdb: Path, protein: list[str], ligand: list[str]) -> None:
    output_pdb.parent.mkdir(parents=True, exist_ok=True)
    output_lines = protein + ["TER"] + ligand + ["TER", "END"]
    output_pdb.write_text("\n".join(output_lines) + "\n", encoding="ascii")


def main() -> None:
    args = parse_arguments()
    if not args.input_pdb.is_file():
        raise SystemExit(f"Input PDB not found: {args.input_pdb}")

    lines = args.input_pdb.read_text(encoding="ascii").splitlines()
    protein, ligand = prepare_complex(lines)
    validate_complex(protein, ligand)
    write_complex(args.output_pdb, protein, ligand)

    print(
        f"Prepared complex structure: {args.output_pdb} "
        f"({len(protein)} protein atoms, {len(ligand)} JZ4 heavy atoms)"
    )


if __name__ == "__main__":
    main()
