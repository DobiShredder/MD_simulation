#!/usr/bin/env python3
"""Plot counts and occupancies of intraprotein and water hydrogen bonds in Chignolin."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


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
        raise ValueError(f"hydrogen bond count data is missing: {path}")
    return np.asarray(rows, dtype=float)


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    protein = np.loadtxt(
        output_dir / "protein_hbond_count.dat", comments="#", ndmin=2
    )
    water = read_hbond_counts(output_dir / "water_hbond_count.dat", 4)

    if protein.shape[1] < 2 or water.shape[1] < 4:
        raise ValueError("Hydrogen-bond count output has too few columns.")
    if not np.array_equal(protein[:, 0], water[:, 0]):
        raise ValueError("Frame indices in the hydrogen-bond outputs do not match.")

    occupancy = read_hbond_occupancy(output_dir / "protein_hbond_average.dat")[:10]

    figure, axes = plt.subplots(2, 1, figsize=(9, 8))
    axes[0].plot(protein[:, 0], protein[:, 1], label="Protein–protein")
    axes[0].plot(water[:, 0], water[:, 2], label="Protein–water")
    axes[0].plot(water[:, 0], water[:, 3], label="Water bridges")
    axes[0].set_xlabel("Frame")
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
