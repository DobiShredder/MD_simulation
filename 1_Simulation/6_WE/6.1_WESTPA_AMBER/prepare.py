#!/usr/bin/env python3
"""1UAO NMR ensemble에서 Chignolin의 첫 번째 coordinate model을 추출합니다."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PDB 1UAO에서 첫 번째 coordinate model을 추출합니다."
    )
    parser.add_argument("input_pdb", type=Path, help="다운로드한 1UAO PDB")
    parser.add_argument("output_pdb", type=Path, help="전처리 결과 PDB")
    return parser.parse_args()


def select_first_model_atom_records(lines: list[str]) -> list[str]:
    has_model_records = any(line.startswith("MODEL ") for line in lines)
    selected_records: list[str] = []
    inside_first_model = not has_model_records
    first_model_started = False

    for line in lines:
        if line.startswith("MODEL "):
            if first_model_started:
                break
            first_model_started = True
            inside_first_model = True
            continue

        if line.startswith("ENDMDL") and inside_first_model:
            break
        if not inside_first_model or not line.startswith("ATOM  "):
            continue

        alternate_location = line[16:17]
        if alternate_location not in {" ", "A"}:
            continue
        if alternate_location == "A":
            line = f"{line[:16]} {line[17:]}"
        selected_records.append(line)

    return selected_records


def main() -> None:
    args = parse_arguments()
    if not args.input_pdb.is_file():
        raise SystemExit(f"입력 PDB를 찾을 수 없습니다: {args.input_pdb}")

    atom_records = select_first_model_atom_records(
        args.input_pdb.read_text(encoding="ascii").splitlines()
    )
    if not atom_records:
        raise SystemExit("첫 번째 model에서 ATOM record를 찾지 못했습니다.")

    args.output_pdb.parent.mkdir(parents=True, exist_ok=True)
    args.output_pdb.write_text(
        "\n".join(atom_records + ["TER", "END"]) + "\n",
        encoding="ascii",
    )
    print(f"Chignolin 전처리 결과: {args.output_pdb} ({len(atom_records)} atoms)")


if __name__ == "__main__":
    main()
