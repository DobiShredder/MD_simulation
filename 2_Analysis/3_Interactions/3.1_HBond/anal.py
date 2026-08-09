#!/usr/bin/env python3
"""Chignolin 내부 및 water hydrogen bond의 수와 점유율을 표시한다."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analysis_utils import (
    analysis_time_ns,
    read_cpptraj_table,
    read_run_metadata,
    require_same_rows,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "output")
    return parser.parse_args()


def read_hbond_occupancy(path: Path) -> list[tuple[str, float]]:
    occupancies: list[tuple[str, float]] = []
    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            fields = raw_line.split()
            if not fields or fields[0].startswith("#") or len(fields) < 7:
                continue
            try:
                fraction = float(fields[-3])
            except ValueError:
                continue
            label = " / ".join(fields[:3])
            occupancies.append((label, fraction))
    return sorted(occupancies, key=lambda item: item[1], reverse=True)


def read_hbond_counts(path: Path, numeric_columns: int) -> np.ndarray:
    rows: list[list[float]] = []
    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            fields = raw_line.split()
            if not fields or fields[0].startswith("#"):
                continue
            try:
                rows.append([float(value) for value in fields[:numeric_columns]])
            except ValueError:
                continue
    if not rows:
        raise ValueError(f"hydrogen bond count data가 없습니다: {path}")
    return np.asarray(rows, dtype=float)


def main() -> int:
    args = parse_arguments()
    _, protein = read_cpptraj_table(args.output / "protein_hbond_count.dat")
    water = read_hbond_counts(args.output / "water_hbond_count.dat", 4)
    frame_count = require_same_rows({"protein": protein, "water": water})

    if protein.shape[1] < 2 or water.shape[1] < 4:
        raise ValueError("hydrogen bond count output column이 부족합니다.")

    metadata = read_run_metadata(args.output)
    time_ns = analysis_time_ns(frame_count, metadata)
    occupancy = read_hbond_occupancy(args.output / "protein_hbond_average.dat")[:10]

    figure, axes = plt.subplots(2, 1, figsize=(9, 8))
    axes[0].plot(time_ns, protein[:, 1], label="Protein–protein")
    axes[0].plot(time_ns, water[:, 2], label="Protein–water")
    axes[0].plot(time_ns, water[:, 3], label="Water bridges")
    axes[0].set_xlabel("Analysis time (ns)")
    axes[0].set_ylabel("Hydrogen bond count")
    axes[0].legend()

    if occupancy:
        labels = [item[0] for item in reversed(occupancy)]
        fractions = [item[1] for item in reversed(occupancy)]
        axes[1].barh(labels, fractions)
        axes[1].set_xlim(0, 1)
        axes[1].set_xlabel("Occupancy fraction")
    else:
        axes[1].text(0.5, 0.5, "No protein hydrogen bond", ha="center", va="center")
        axes[1].set_axis_off()

    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
