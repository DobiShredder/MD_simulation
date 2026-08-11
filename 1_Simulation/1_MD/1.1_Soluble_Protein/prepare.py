#!/usr/bin/env python3
"""Extract the first coordinate model from the 1UAO NMR ensemble."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract the first coordinate model from PDB 1UAO."
    )
    parser.add_argument("input_pdb", type=Path, help="Downloaded 1UAO PDB")
    parser.add_argument("output_pdb", type=Path, help="Prepared PDB")

    return parser.parse_args()


def select_first_model_atom_records(lines: list[str]) -> list[str]:
    """Select ATOM records and primary alternate locations from the first model."""
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

        if not inside_first_model:
            continue

        if not line.startswith("ATOM  "):
            continue

        alternate_location = line[16:17]

        if alternate_location not in {" ", "A"}:
            continue

        if alternate_location == "A":
            line = f"{line[:16]} {line[17:]}"

        selected_records.append(line)

    return selected_records


def write_prepared_pdb(output_pdb: Path, atom_records: list[str]) -> None:
    """Write selected ATOM records to one PDB coordinate file."""
    output_pdb.parent.mkdir(parents=True, exist_ok=True)

    output_lines = atom_records + ["TER", "END"]
    output_text = "\n".join(output_lines) + "\n"

    output_pdb.write_text(output_text, encoding="ascii")


def main() -> None:
    args = parse_arguments()

    if not args.input_pdb.is_file():
        raise SystemExit(f"Input PDB not found: {args.input_pdb}")

    input_lines = args.input_pdb.read_text(encoding="ascii").splitlines()
    atom_records = select_first_model_atom_records(input_lines)

    if not atom_records:
        raise SystemExit("No ATOM records found in the first model.")

    write_prepared_pdb(args.output_pdb, atom_records)

    print(f"Prepared first-model structure: {args.output_pdb} ({len(atom_records)} atoms)")


if __name__ == "__main__":
    main()
