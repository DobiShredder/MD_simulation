#!/usr/bin/env python3
"""Prepare protein and bound benzene/toluene coordinates from 4W53."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


# build.sh parameterizes BNZ/MBN from the RCSB ideal SDF files, which contain
# hydrogens. antechamber names SDF atoms by element and file order (C1, C2, ...).
# The 4W53 crystal atoms follow the same chemical component order, so renaming
# them lets tleap match the mol2 templates and build the missing hydrogens.
MBN_ATOM_NAMES = {
    "C": "C1",
    "C1": "C2",
    "C2": "C3",
    "C3": "C4",
    "C4": "C5",
    "C5": "C6",
    "C6": "C7",
}
# Benzene uses the toluene ring atoms. The crystal names C1-C6 already follow
# the BNZ_ideal.sdf ring order, so they are kept.
BNZ_ATOM_NAMES = ["C1", "C2", "C3", "C4", "C5", "C6"]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare PDB 4W53 for the RBFE build.")
    parser.add_argument("input_pdb", type=Path)
    parser.add_argument("protein_pdb", type=Path)
    return parser.parse_args()


def pdb_line_with_residue(line: str, residue_name: str) -> str:
    return f"{line[:17]}{residue_name:>3}{line[20:]}"


def pdb_line_with_atom(line: str, atom_name: str) -> str:
    return f"{line[:12]} {atom_name:<3}{line[16:]}"


def write_pdb(path: Path, records: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(records + ["TER", "END"]) + "\n", encoding="ascii")


def main() -> None:
    args = parse_arguments()
    if (os.environ.get("MD_WRITER_PARENT") != str(os.getppid())
            or os.environ.get("MD_WRITER_ENTRY") != sys.argv[0]):
        os.execv(sys.executable, [sys.executable, "helpers/writer_guard.py", "--python-entry",
                   "--registry", "work", "--read", str(args.input_pdb),
                   "--write", str(args.protein_pdb),
                   "--write", str(args.protein_pdb.with_name("bound_mbn.pdb")),
                   "--write", str(args.protein_pdb.with_name("bound_bnz.pdb")),
                   "--write", str(args.protein_pdb.with_name("preparation.tsv")), "--", *sys.argv])
    if not args.input_pdb.is_file():
        raise SystemExit(f"Structure preparation input PDB not found: {args.input_pdb}")
    print(f"Preparing structure: {args.input_pdb}")

    protein: list[str] = []
    toluene: list[str] = []
    for line in args.input_pdb.read_text(encoding="ascii").splitlines():
        if line.startswith("ATOM  ") and line[16:17] in {" ", "A"}:
            protein.append(f"{line[:16]} {line[17:]}" if line[16:17] == "A" else line)
        if line.startswith("HETATM") and line[17:20].strip() == "MBN":
            toluene.append(pdb_line_with_residue(line, "MBN"))

    if len(protein) < 1000:
        raise SystemExit(f"4W53 protein has fewer atoms than expected: {len(protein)}")
    if len(toluene) != 7:
        raise SystemExit(f"Expected 7 MBN heavy atoms in 4W53, found {len(toluene)}")

    methyl_atoms = [line for line in toluene if line[12:16].strip() == "C"]
    if len(methyl_atoms) != 1:
        raise SystemExit("Expected exactly one toluene methyl carbon named C.")

    benzene = [
        pdb_line_with_residue(line, "BNZ")
        for line in toluene
        if line[12:16].strip() in BNZ_ATOM_NAMES
    ]
    if len(benzene) != 6:
        raise SystemExit(f"Expected 6 toluene ring atoms named C1-C6, found {len(benzene)}")

    renamed_toluene = []
    for line in toluene:
        source_name = line[12:16].strip()
        if source_name not in MBN_ATOM_NAMES:
            raise SystemExit(f"Unknown MBN atom name in 4W53: {source_name}")
        renamed_toluene.append(pdb_line_with_atom(line, MBN_ATOM_NAMES[source_name]))
    toluene = renamed_toluene

    write_pdb(args.protein_pdb, protein)
    write_pdb(args.protein_pdb.with_name("bound_mbn.pdb"), toluene)
    write_pdb(args.protein_pdb.with_name("bound_bnz.pdb"), benzene)

    metadata = args.protein_pdb.with_name("preparation.tsv")
    metadata.write_text(
        "field\tvalue\n"
        f"protein_atoms\t{len(protein)}\n"
        "benzene_residue\tBNZ\n"
        "toluene_residue\tMBN\n"
        "transformation\tBNZ_to_MBN\n",
        encoding="utf-8",
    )
    print(f"RBFE coordinate: {args.protein_pdb.parent}")


if __name__ == "__main__":
    main()
