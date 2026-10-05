#!/usr/bin/env python3
"""Compare two GROMACS potential energies and retain a compact result table."""

from __future__ import annotations

import argparse
from pathlib import Path
import math


def last_value(path: Path) -> float:
    values: list[float] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "@")):
            continue
        values.append(float(stripped.split()[-1]))
    if not values:
        raise SystemExit(f"Energy value not found: {path}")
    return values[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("unscaled", type=Path, help="Unscaled potential-energy XVG")
    parser.add_argument("scale_one", type=Path, help="Scale-1.0 potential-energy XVG")
    parser.add_argument("tolerance", type=float, help="Allowed absolute difference in kJ/mol")
    parser.add_argument("--output", type=Path, help="Compact TSV result")
    args = parser.parse_args()
    if not math.isfinite(args.tolerance) or args.tolerance < 0:
        raise SystemExit("Energy comparison tolerance must be finite and nonnegative")

    unscaled = last_value(args.unscaled)
    scale_one = last_value(args.scale_one)
    if not math.isfinite(unscaled) or not math.isfinite(scale_one):
        raise SystemExit(f"Nonfinite energy: {args.unscaled} or {args.scale_one}")
    difference = abs(unscaled - scale_one)
    if not math.isfinite(difference):
        raise SystemExit(f"Nonfinite energy difference: {args.unscaled} and {args.scale_one}")
    status = "pass" if difference <= args.tolerance else "fail"

    if args.output is not None:
        text = (
            "variant\tpotential_kJ_mol\tdifference_kJ_mol\t"
            "tolerance_kJ_mol\tstatus\n"
            f"unscaled\t{unscaled:.12g}\t0\t{args.tolerance:.12g}\treference\n"
            f"scale_one\t{scale_one:.12g}\t{difference:.12g}\t"
            f"{args.tolerance:.12g}\t{status}\n"
        )
        args.output.write_text(text, encoding="utf-8")

    if status != "pass":
        raise SystemExit(
            "Scale 1.0 energy differs from original: "
            f"|ΔE|={difference:.8g} kJ/mol, tolerance={args.tolerance}"
        )
    print(f"Scale 1.0 energy check: |ΔE|={difference:.8g} kJ/mol")


if __name__ == "__main__":
    main()

