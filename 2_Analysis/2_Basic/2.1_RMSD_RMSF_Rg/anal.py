#!/usr/bin/env python3
"""Plot Chignolin RMSD, residue RMSF, and radius of gyration."""

from __future__ import annotations

import argparse
from pathlib import Path

from result_generation import verify_generation

import matplotlib.pyplot as plt
import numpy as np


# Used only with --save-figure DIR.
FIGURE_NAME = "rmsd_rmsf_rg.png"
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
    print(f"Running: RMSD/RMSF/Rg analysis; input directory: {output_dir}")
    rmsd_first = np.loadtxt(output_dir / "rmsd_first.dat", comments="#", ndmin=2)
    rmsd_average = np.loadtxt(
        output_dir / "rmsd_average.dat", comments="#", ndmin=2
    )
    rmsf = np.loadtxt(output_dir / "rmsf_byres.dat", comments="#", ndmin=2)
    rg = np.loadtxt(output_dir / "rg.dat", comments="#", ndmin=2)

    if not np.array_equal(rmsd_first[:, 0], rmsd_average[:, 0]):
        raise ValueError("RMSD output frame indices do not match.")
    if not np.array_equal(rmsd_first[:, 0], rg[:, 0]):
        raise ValueError("Frame indices in the RMSD and Rg outputs do not match.")
    print(f"Frames: {len(rmsd_first)}")

    figure, axes = plt.subplots(3, 1, figsize=(8, 9))
    axes[0].plot(rmsd_first[:, 0], rmsd_first[:, 1], label="First frame")
    axes[0].plot(rmsd_average[:, 0], rmsd_average[:, 1], label="Average structure")
    axes[0].set_ylabel("Backbone RMSD (Å)")
    axes[0].legend()

    axes[1].plot(rmsf[:, 0], rmsf[:, 1], marker="o")
    axes[1].set_xlabel("Residue")
    axes[1].set_ylabel("Cα RMSF (Å)")

    axes[2].plot(rg[:, 0], rg[:, 1])
    axes[2].set_xlabel("Frame")
    axes[2].set_ylabel("Radius of gyration (Å)")

    figure.tight_layout()
    if verify_generation(output_dir) != generation:
        raise ValueError(f"Analysis generation changed while reading: {output_dir}")
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying RMSD/RMSF/Rg analysis figure.")
    plt.show()
    print("Completed: RMSD/RMSF/Rg analysis (interactive figure).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
