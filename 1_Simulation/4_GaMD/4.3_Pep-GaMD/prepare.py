#!/usr/bin/env python3
"""1CKB chain A receptor와 resolved chain B peptide를 준비합니다."""

from __future__ import annotations

import argparse
from pathlib import Path

EXPECTED_PEPTIDE = ["PRO", "PRO", "PRO", "VAL", "PRO", "PRO", "ARG", "ARG"]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PDB 1CKB를 Pep-GaMD build용으로 전처리합니다.")
    parser.add_argument("input_pdb", type=Path)
    parser.add_argument("output_pdb", type=Path)
    return parser.parse_args()


def residue_key(line: str) -> tuple[str, str, str]:
    return line[21:22], line[22:26].strip(), line[26:27]


def main() -> None:
    args = arguments()
    if not args.input_pdb.is_file():
        raise SystemExit(f"입력 PDB를 찾을 수 없습니다: {args.input_pdb}")

    selected: list[tuple[str, tuple[str, str, str]]] = []
    residue_order: list[tuple[str, str, str]] = []
    residue_names: dict[tuple[str, str, str], str] = {}

    for line in args.input_pdb.read_text(encoding="ascii").splitlines():
        if not line.startswith("ATOM  ") or line[21:22] not in {"A", "B"}:
            continue
        alternate = line[16:17]
        if alternate not in {" ", "A"}:
            continue
        if alternate == "A":
            line = f"{line[:16]} {line[17:]}"
        key = residue_key(line)
        if key not in residue_names:
            residue_order.append(key)
            residue_names[key] = line[17:20].strip()
        selected.append((line, key))

    receptor = [key for key in residue_order if key[0] == "A"]
    peptide = [key for key in residue_order if key[0] == "B"]
    peptide_sequence = [residue_names[key] for key in peptide]
    if len(receptor) != 57:
        raise SystemExit(f"1CKB chain A는 57 resolved residues여야 합니다: {len(receptor)}")
    if peptide_sequence != EXPECTED_PEPTIDE:
        raise SystemExit(f"1CKB resolved peptide가 PPPVPPRR과 다릅니다: {peptide_sequence}")

    new_index = {key: index for index, key in enumerate(residue_order, start=1)}
    output_lines: list[str] = []
    atom_serial = 0
    previous_chain = ""
    for line, key in selected:
        chain = key[0]
        if previous_chain and chain != previous_chain:
            output_lines.append("TER")
        atom_serial += 1
        line = f"{line[:6]}{atom_serial:5d}{line[11:22]}{new_index[key]:4d} {line[27:]}"
        output_lines.append(line)
        previous_chain = chain
    output_lines.extend(["TER", "END"])

    args.output_pdb.parent.mkdir(parents=True, exist_ok=True)
    args.output_pdb.write_text("\n".join(output_lines) + "\n", encoding="ascii")
    peptide_start = len(receptor) + 1
    peptide_end = len(receptor) + len(peptide)
    args.output_pdb.with_name("system_metadata.tsv").write_text(
        "key\tvalue\n"
        f"receptor_residues\t{len(receptor)}\n"
        f"peptide_start_residue\t{peptide_start}\n"
        f"peptide_end_residue\t{peptide_end}\n"
        "peptide_sequence\tPPPVPPRR\n",
        encoding="utf-8",
    )
    print(f"Pep-GaMD 전처리 결과: {args.output_pdb} (peptide :{peptide_start}-{peptide_end})")


if __name__ == "__main__":
    main()
