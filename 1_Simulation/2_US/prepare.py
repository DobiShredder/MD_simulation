#!/usr/bin/env python3
"""Extract the first model from the 1UAO NMR ensemble."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract the first coordinate model from PDB 1UAO."
    )
    parser.add_argument("input_pdb", type=Path, help="Downloaded 1UAO PDB")
    parser.add_argument("output_pdb", type=Path, help="Prepared PDB")
    return parser.parse_args()


def select_first_model(lines: list[str]) -> list[str]:
    has_models = any(line.startswith("MODEL ") for line in lines)
    inside_first_model = not has_models
    first_model_started = False
    selected: list[str] = []

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

        selected.append(line)

    return selected


def main() -> None:
    args = parse_arguments()

    if not args.input_pdb.is_file():
        raise SystemExit(f"Input PDB not found: {args.input_pdb}")

    lines = args.input_pdb.read_text(encoding="ascii").splitlines()
    atom_records = select_first_model(lines)

    if not atom_records:
        raise SystemExit("No ATOM records found in the first model.")

    args.output_pdb.parent.mkdir(parents=True, exist_ok=True)
    output = "\n".join(atom_records + ["TER", "END"]) + "\n"
    args.output_pdb.write_text(output, encoding="ascii")

    print(f"Prepared structure: {args.output_pdb} ({len(atom_records)} atoms)")


if __name__ == "__main__":
    main()

