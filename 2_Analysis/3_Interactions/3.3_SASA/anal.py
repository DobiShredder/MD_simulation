#!/usr/bin/env python3
"""Plot total Chignolin SASA and mean per-residue contributions."""

from __future__ import annotations

import argparse
from pathlib import Path

from result_generation import verify_generation

import matplotlib.pyplot as plt
import numpy as np


# Must match the per-residue surf commands (:1 to :10) in inputs/cpptraj.in.
RESIDUE_COUNT = 10

# Used only with --save-figure DIR.
FIGURE_NAME = "sasa.png"
FIGURE_DPI = 150


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
    print(f"Running: SASA analysis; input directory: {output_dir}")
    total = np.loadtxt(output_dir / "sasa_total.dat", comments="#", ndmin=2)
    residues = np.loadtxt(output_dir / "sasa_byres.dat", comments="#", ndmin=2)
    if total.shape[1] < 2 or residues.shape[1] != RESIDUE_COUNT + 1:
        raise ValueError("SASA output column count differs from the expected Chignolin residue count.")
    if not np.array_equal(total[:, 0], residues[:, 0]):
        raise ValueError("Frame indices in the SASA outputs do not match.")
    print(f"Frames: {len(total)}")

    mean_residue_sasa = np.mean(residues[:, 1:], axis=0)

    figure, axes = plt.subplots(2, 1, figsize=(8, 8))
    axes[0].plot(total[:, 0], total[:, 1])
    axes[0].set_xlabel("Frame")
    axes[0].set_ylabel("Protein SASA (Å²)")

    residue_numbers = np.arange(1, RESIDUE_COUNT + 1)
    axes[1].bar(residue_numbers, mean_residue_sasa)
    axes[1].set_xticks(residue_numbers)
    axes[1].set_xlabel("Residue")
    axes[1].set_ylabel("Mean SASA contribution (Å²)")

    figure.tight_layout()
    if verify_generation(output_dir) != generation:
        raise ValueError(f"Analysis generation changed while reading: {output_dir}")
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying SASA analysis figure.")
    plt.show()
    print("Completed: SASA analysis (interactive figure).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
