#!/usr/bin/env python3
"""Compare RMSD before and after backbone fitting."""

from __future__ import annotations

import argparse
from pathlib import Path

from result_generation import verify_generation

import matplotlib.pyplot as plt
import numpy as np


# Used only with --save-figure DIR.
FIGURE_NAME = "alignment.png"
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
    print(f"Running: Alignment analysis; input directory: {output_dir}")
    before = np.loadtxt(output_dir / "rmsd_before.dat", comments="#", ndmin=2)
    after = np.loadtxt(output_dir / "rmsd_after.dat", comments="#", ndmin=2)
    if before.shape[1] < 2 or after.shape[1] < 2:
        raise ValueError("RMSD output has too few columns.")
    if not np.array_equal(before[:, 0], after[:, 0]):
        raise ValueError("RMSD output frame indices do not match.")
    print(f"Frames: {len(before)}")

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.plot(before[:, 0], before[:, 1], label="Before fitting")
    axis.plot(after[:, 0], after[:, 1], label="After fitting")
    axis.set_xlabel("Frame")
    axis.set_ylabel("Backbone RMSD (Å)")
    axis.legend()
    figure.tight_layout()
    if verify_generation(output_dir) != generation:
        raise ValueError(f"Analysis generation changed while reading: {output_dir}")
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying Alignment analysis figure.")
    plt.show()
    print("Completed: Alignment analysis (interactive figure).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
