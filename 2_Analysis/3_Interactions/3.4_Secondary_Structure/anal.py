#!/usr/bin/env python3
"""Plot the Chignolin secondary-structure residue-time map and overall fractions."""

from __future__ import annotations

import argparse
from pathlib import Path

from result_generation import verify_generation

import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np


# Must match the secstruct mask (:1-10) in inputs/cpptraj.in.
RESIDUE_COUNT = 10

# Used only with --save-figure DIR.
FIGURE_NAME = "secondary_structure.png"
FIGURE_DPI = 150


STRUCTURE_LABELS = [
    "None",
    "Extended",
    "Bridge",
    "3-10",
    "Alpha",
    "Pi",
    "Turn",
    "Bend",
]


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
    print(f"Running: Secondary/Structure analysis; input directory: {output_dir}")
    assignments = np.loadtxt(
        output_dir / "secondary_structure.dat", comments="#", ndmin=2
    )
    totals = np.loadtxt(output_dir / "secondary_total.dat", comments="#", ndmin=2)
    if assignments.shape[1] != RESIDUE_COUNT + 1 or totals.shape[1] != 8:
        raise ValueError("Secondary-structure output columns do not match the expected format.")
    if not np.array_equal(assignments[:, 0], totals[:, 0]):
        raise ValueError("Frame indices in the secondary-structure outputs do not match.")
    print(f"Frames: {len(assignments)}")

    frames = assignments[:, 0]
    map_values = assignments[:, 1:].T

    colors = [
        "#f2f2f2",
        "#377eb8",
        "#984ea3",
        "#4daf4a",
        "#e41a1c",
        "#ff7f00",
        "#ffff33",
        "#a65628",
    ]
    color_map = ListedColormap(colors)
    normalization = BoundaryNorm(np.arange(-0.5, 8.5, 1), color_map.N)

    figure, axes = plt.subplots(2, 1, figsize=(10, 8))
    image = axes[0].imshow(
        map_values,
        aspect="auto",
        origin="lower",
        interpolation="nearest",
        cmap=color_map,
        norm=normalization,
        extent=[frames[0], frames[-1] if len(frames) > 1 else 0, 0.5, RESIDUE_COUNT + 0.5],
    )
    axes[0].set_xlabel("Frame")
    axes[0].set_ylabel("Residue")
    axes[0].set_yticks(np.arange(1, RESIDUE_COUNT + 1))
    color_bar = figure.colorbar(image, ax=axes[0], ticks=np.arange(8))
    color_bar.ax.set_yticklabels(STRUCTURE_LABELS)

    none_fraction = np.clip(1.0 - np.sum(totals[:, 1:], axis=1), 0.0, 1.0)
    axes[1].plot(frames, none_fraction, label=STRUCTURE_LABELS[0])
    for column, label in enumerate(STRUCTURE_LABELS[1:], start=1):
        axes[1].plot(frames, totals[:, column], label=label)
    axes[1].set_xlabel("Frame")
    axes[1].set_ylabel("Residue fraction")
    axes[1].set_ylim(0, 1)
    axes[1].legend(ncol=4, fontsize="small")

    figure.tight_layout()
    if verify_generation(output_dir) != generation:
        raise ValueError(f"Analysis generation changed while reading: {output_dir}")
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying Secondary/Structure analysis figure.")
    plt.show()
    print("Completed: Secondary/Structure analysis (interactive figure).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
