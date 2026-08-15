#!/usr/bin/env python3
"""Summarize OPES Expanded multithermal bias and energy range."""

import argparse
from pathlib import Path
import numpy as np


def read_colvar(path: Path) -> dict[str, np.ndarray]:
    fields = None
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#! FIELDS"):
            fields = line.split()[2:]
        elif line and not line.startswith("#"):
            rows.append([float(value) for value in line.split()])
    if fields is None or not rows:
        raise ValueError(f"COLVAR header or data not found: {path}")
    data = np.asarray(rows)
    return {name: data[:, index] for index, name in enumerate(fields)}


def count_deltafs_states(path: Path) -> int:
    fields = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#! FIELDS"):
            fields = line.split()[2:]
            break
    if fields is None:
        raise ValueError(f"DELTAFS header is missing: {path}")
    return max(0, len(fields) - 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", nargs="?", type=Path, default=Path(__file__).parent / "work")
    args = parser.parse_args()
    completion_marker = args.work_dir / ".production.complete"
    if not completion_marker.is_file():
        raise ValueError(f"Production completion marker not found: {completion_marker}")
    for filename in ("COLVAR", "DELTAFS", "opes.state"):
        path = args.work_dir / filename
        if not path.is_file():
            raise ValueError(f"Production output not found: {path}")

    output_dir = args.work_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    values = read_colvar(args.work_dir / "COLVAR")
    required = {"time", "ene", "ecv.ene", "opes.bias"}
    if not required.issubset(values):
        raise ValueError(f"Required COLVAR fields are missing: {args.work_dir / 'COLVAR'}")

    with (output_dir / "production_summary.tsv").open("w", encoding="utf-8") as handle:
        handle.write(
            "frames\tenergy_min_kj_mol\tenergy_max_kj_mol\t"
            "ecv_min\tecv_max\tbias_min_kj_mol\tbias_max_kj_mol\t"
            "deltafs_states\n"
        )
        row = (
            len(values["time"]),
            values["ene"].min(), values["ene"].max(),
            values["ecv.ene"].min(), values["ecv.ene"].max(),
            values["opes.bias"].min(), values["opes.bias"].max(),
            count_deltafs_states(args.work_dir / "DELTAFS"),
        )
        handle.write("\t".join(map(str, row)) + "\n")
    print(f"OPES Expanded diagnostics results: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
