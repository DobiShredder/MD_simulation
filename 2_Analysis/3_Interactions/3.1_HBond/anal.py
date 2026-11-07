#!/usr/bin/env python3
"""Plot counts and occupancies of intraprotein and water hydrogen bonds in Chignolin."""

from __future__ import annotations

import argparse
from pathlib import Path

from result_generation import verify_generation

import matplotlib.pyplot as plt
import numpy as np


# Number of most occupied intraprotein hydrogen bonds shown in the bar chart.
TOP_OCCUPANCY_COUNT = 10

# Used only with --save-figure DIR.
FIGURE_NAME = "hbond.png"
FIGURE_DPI = 150


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


def save_figure(figure: plt.Figure, figure_dir: Path) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    figure_path = figure_dir / FIGURE_NAME
    figure.savefig(figure_path, dpi=FIGURE_DPI)
    print(f"Saved figure: {figure_path}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--save-figure",
        metavar="DIR",
        type=Path,
        help="also save the figure as PNG in DIR (outside output/); "
        "by default the figure is only displayed",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    output_dir = Path(__file__).resolve().parent / "output"
    figure_dir = args.save_figure
    if figure_dir is not None and figure_dir.resolve().is_relative_to(output_dir):
        # Extra files in output/ would invalidate its recorded generation hashes.
        raise SystemExit(f"Error: --save-figure DIR must be outside {output_dir}")
    from writer_guard import protect_python_entry
    protect_python_entry("output", reads=(output_dir,))
    generation = verify_generation(output_dir)
    print(f"Running: HBond analysis; input directory: {output_dir}")
    protein = np.loadtxt(
        output_dir / "protein_hbond_count.dat", comments="#", ndmin=2
    )
    water = read_hbond_counts(output_dir / "water_hbond_count.dat", 4)

    if protein.shape[1] < 2 or water.shape[1] < 4:
        raise ValueError("Hydrogen-bond count output has too few columns.")
    if not np.array_equal(protein[:, 0], water[:, 0]):
        raise ValueError("Frame indices in the hydrogen-bond outputs do not match.")
    print(f"Frames: {len(protein)}")

    occupancy = read_hbond_occupancy(output_dir / "protein_hbond_average.dat")
    occupancy = occupancy[:TOP_OCCUPANCY_COUNT]

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
    if verify_generation(output_dir) != generation:
        raise ValueError(f"Analysis generation changed while reading: {output_dir}")
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying HBond analysis figure.")
    plt.show()
    print("Completed: HBond analysis (interactive figure).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
