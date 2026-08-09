#!/usr/bin/env python3
"""Na+/Cl- weighted-ensemble example의 시작 coordinate를 생성합니다."""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--distance", type=float, default=8.0, help="초기 ion distance (Å)")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    if not math.isfinite(args.distance):
        raise SystemExit("초기 distance는 유한한 값이어야 합니다.")
    if args.distance <= 2.6:
        raise SystemExit("초기 distance는 bound-state 경계 2.6 Å보다 커야 합니다.")

    root = Path(__file__).resolve().parent
    work = Path(os.environ.get("WORK_DIR", root / "work"))
    structure = work / "structure"
    structure.mkdir(parents=True, exist_ok=True)
    mol2 = structure / "system.mol2"
    mol2.write_text(
        "@<TRIPOS>MOLECULE\nNaCl\n2 0 2 0 0\nSMALL\nUSER_CHARGES\n\n"
        "@<TRIPOS>ATOM\n"
        "      1 Na          0.0000    0.0000    0.0000 Na+       1 Na+       1.0000\n"
        f"      2 Cl          {args.distance:8.4f}    0.0000    0.0000 Cl-       2 Cl-      -1.0000\n"
        "@<TRIPOS>BOND\n"
        "@<TRIPOS>SUBSTRUCTURE\n"
        "     1 Na+         1 RESIDUE           0 ****  ****    0 ROOT\n"
        "     2 Cl-         2 RESIDUE           0 ****  ****    0 ROOT\n",
        encoding="ascii",
    )
    print(f"Na+/Cl- coordinate: {mol2}")


if __name__ == "__main__":
    main()
