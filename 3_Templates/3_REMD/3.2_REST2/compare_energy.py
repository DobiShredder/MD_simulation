#!/usr/bin/env python3
"""Check whether two GROMACS XVG potential energies agree within numerical tolerance."""

from __future__ import annotations

import argparse
from pathlib import Path


def last_value(path: Path) -> float:
    values: list[float] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "@")):
            continue
        fields = stripped.split()
        values.append(float(fields[-1]))

    if not values:
        raise SystemExit(f"energy value not found: {path}")

    return values[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("unscaled", type=Path, help="Unscaled potential-energy XVG")
    parser.add_argument("scale_one", type=Path, help="Scale-1.0 potential-energy XVG")
    parser.add_argument("tolerance", type=float, help="Allowed absolute difference in kJ/mol")
    args = parser.parse_args()

    unscaled = last_value(args.unscaled)
    scale_one = last_value(args.scale_one)
    difference = abs(unscaled - scale_one)

    if difference > args.tolerance:
        raise SystemExit(
            "Scale 1.0 energy differs from the original: "
            f"|ΔE|={difference:.8g} kJ/mol, tolerance={args.tolerance}"
        )

    print(f"Scale 1.0 energy check: |ΔE|={difference:.8g} kJ/mol")


if __name__ == "__main__":
    main()
