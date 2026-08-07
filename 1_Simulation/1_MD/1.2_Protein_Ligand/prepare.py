#!/usr/bin/env python3
"""3PTB에서 protein, BEN과 구조적 calcium을 남기고 결정수를 제거한다."""

from __future__ import annotations

import argparse
from pathlib import Path


ResidueKey = tuple[str, str, str]
DisulfidePair = tuple[ResidueKey, ResidueKey]


def parse_arguments() -> argparse.Namespace:
    """Command-line argument를 읽는다."""
    parser = argparse.ArgumentParser(
        description="PDB 3PTB의 protein, BEN ligand와 구조적 calcium을 전처리합니다."
    )
    parser.add_argument("input_pdb", type=Path, help="다운로드한 3PTB PDB")
    parser.add_argument("output_pdb", type=Path, help="전처리 결과 complex PDB")

    return parser.parse_args()


def read_disulfide_pairs(lines: list[str]) -> list[DisulfidePair]:
    """PDB SSBOND record에서 disulfide residue pair를 읽는다."""
    pairs: list[DisulfidePair] = []

    for line in lines:
        if not line.startswith("SSBOND"):
            continue

        first = (line[15:16], line[17:21].strip(), line[21:22])
        second = (line[29:30], line[31:35].strip(), line[35:36])
        pairs.append((first, second))

    return pairs


def select_complex_records(
    lines: list[str],
    disulfide_residues: set[ResidueKey],
) -> tuple[list[str], dict[ResidueKey, int], dict[str, int]]:
    """Protein, BEN과 structural Ca2+를 선택하고 CYX 이름을 적용한다."""
    selected_records: list[str] = []
    residue_indices: dict[ResidueKey, int] = {}
    atom_counts = {"protein": 0, "BEN": 0, "CA": 0}

    for line in lines:
        record_type = line[:6]
        residue_name = line[17:20].strip()
        alternate_location = line[16:17]

        if alternate_location not in {" ", "A"}:
            continue

        keep_record = False

        if record_type == "ATOM  ":
            keep_record = True
            atom_counts["protein"] += 1

            residue_key = (line[21:22], line[22:26].strip(), line[26:27])

            if residue_key not in residue_indices:
                residue_indices[residue_key] = len(residue_indices) + 1

            if residue_key in disulfide_residues:
                line = f"{line[:17]}CYX{line[20:]}"

        elif record_type == "HETATM" and residue_name in {"BEN", "CA"}:
            keep_record = True
            atom_counts[residue_name] += 1

        if not keep_record:
            continue

        if alternate_location == "A":
            line = f"{line[:16]} {line[17:]}"

        selected_records.append(line)

    return selected_records, residue_indices, atom_counts


def validate_selection(
    atom_counts: dict[str, int],
    disulfide_pairs: list[DisulfidePair],
    residue_indices: dict[ResidueKey, int],
) -> None:
    """Tutorial에서 사용하는 3PTB 구성과 일치하는지 확인한다."""
    expected_atoms_found = (
        atom_counts["protein"] > 0
        and atom_counts["BEN"] == 9
        and atom_counts["CA"] == 1
    )

    if not expected_atoms_found:
        raise SystemExit(f"예상하지 못한 3PTB 구성입니다: {atom_counts}")

    disulfide_residues = {
        residue
        for pair in disulfide_pairs
        for residue in pair
    }

    if len(disulfide_pairs) != 6:
        raise SystemExit("3PTB의 disulfide bond 6개를 찾지 못했습니다.")

    if not disulfide_residues.issubset(residue_indices):
        raise SystemExit(
            "Disulfide residue를 output residue number에 mapping하지 못했습니다."
        )


def write_complex_pdb(output_pdb: Path, selected_records: list[str]) -> None:
    """Selected coordinate record를 complex PDB로 저장한다."""
    output_pdb.parent.mkdir(parents=True, exist_ok=True)

    output_lines = selected_records + ["TER", "END"]
    output_pdb.write_text("\n".join(output_lines) + "\n", encoding="ascii")


def write_disulfide_commands(
    bond_file: Path,
    disulfide_pairs: list[DisulfidePair],
    residue_indices: dict[ResidueKey, int],
) -> None:
    """tleap에서 사용할 disulfide bond command를 저장한다."""
    commands = []

    for first, second in disulfide_pairs:
        first_index = residue_indices[first]
        second_index = residue_indices[second]
        commands.append(f"bond system.{first_index}.SG system.{second_index}.SG")

    bond_file.write_text("\n".join(commands) + "\n", encoding="ascii")


def main() -> None:
    args = parse_arguments()

    if not args.input_pdb.is_file():
        raise SystemExit(f"입력 PDB를 찾을 수 없습니다: {args.input_pdb}")

    input_lines = args.input_pdb.read_text(encoding="ascii").splitlines()
    disulfide_pairs = read_disulfide_pairs(input_lines)
    disulfide_residues = {
        residue
        for pair in disulfide_pairs
        for residue in pair
    }

    selected_records, residue_indices, atom_counts = select_complex_records(
        input_lines,
        disulfide_residues,
    )

    validate_selection(atom_counts, disulfide_pairs, residue_indices)

    write_complex_pdb(args.output_pdb, selected_records)

    bond_file = args.output_pdb.with_name("disulfides.leap")
    write_disulfide_commands(bond_file, disulfide_pairs, residue_indices)

    print(
        f"Complex 전처리 결과: {args.output_pdb} "
        f"({atom_counts['protein']} protein atoms, "
        f"{atom_counts['BEN']} BEN atoms, {atom_counts['CA']} Ca2+ ion)"
    )
    print(f"Disulfide 명령: {bond_file} (CYX pair 6개)")


if __name__ == "__main__":
    main()
