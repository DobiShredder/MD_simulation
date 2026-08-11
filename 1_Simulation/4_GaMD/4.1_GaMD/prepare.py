#!/usr/bin/env python3
"""Extract the first coordinate model from the 1UAO NMR ensemble."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract the first coordinate model from PDB 1UAO."
    )
    parser.add_argument("input_pdb", type=Path)
    parser.add_argument("output_pdb", type=Path)
    return parser.parse_args()


def select_first_model(lines: list[str]) -> list[str]:
    has_model = any(line.startswith("MODEL ") for line in lines)
    inside_model = not has_model
    model_started = False
    atoms: list[str] = []

    for line in lines:
        if line.startswith("MODEL "):
            if model_started:
                break
            model_started = True
            inside_model = True
            continue

        if line.startswith("ENDMDL") and inside_model:
            break

        if not inside_model or not line.startswith("ATOM  "):
            continue

        alternate = line[16:17]
        if alternate not in {" ", "A"}:
            continue
        if alternate == "A":
            line = f"{line[:16]} {line[17:]}"
        atoms.append(line)

    return atoms


def main() -> None:
    args = parse_arguments()
    if not args.input_pdb.is_file():
        raise SystemExit(f"Input PDB not found: {args.input_pdb}")

    atoms = select_first_model(
        args.input_pdb.read_text(encoding="ascii").splitlines()
    )
    if len(atoms) != 138:
        raise SystemExit(f"The first 1UAO model must contain 138 atoms: {len(atoms)}")

    args.output_pdb.parent.mkdir(parents=True, exist_ok=True)
    args.output_pdb.write_text("\n".join(atoms + ["TER", "END"]) + "\n", encoding="ascii")
    print(f"Prepared first-model structure: {args.output_pdb} (138 atoms)")


if __name__ == "__main__":
    main()
