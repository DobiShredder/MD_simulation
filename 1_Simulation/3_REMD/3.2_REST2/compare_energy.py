#!/usr/bin/env python3
"""두 GROMACS XVG의 potential energy가 tolerance 안에서 같은지 검사합니다."""

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
        raise SystemExit(f"energy 값을 찾지 못했습니다: {path}")

    return values[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("unscaled", type=Path)
    parser.add_argument("scale_one", type=Path)
    parser.add_argument("tolerance", type=float)
    args = parser.parse_args()

    unscaled = last_value(args.unscaled)
    scale_one = last_value(args.scale_one)
    difference = abs(unscaled - scale_one)

    if difference > args.tolerance:
        raise SystemExit(
            "scale 1.0 energy가 원본과 다릅니다: "
            f"|ΔE|={difference:.8g} kJ/mol, tolerance={args.tolerance}"
        )

    print(f"Scale 1.0 energy check: |ΔE|={difference:.8g} kJ/mol")


if __name__ == "__main__":
    main()

