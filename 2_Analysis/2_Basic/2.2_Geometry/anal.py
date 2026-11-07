#!/usr/bin/env python3
"""Plot Chignolin distances, angles, and one residue's phi/psi."""

from __future__ import annotations

import argparse
from pathlib import Path

from result_generation import verify_generation

import matplotlib.pyplot as plt
import numpy as np


# Residue for the phi/psi scatter; it must lie inside the multidihedral
# resrange (2-9) in inputs/cpptraj.in.
RAMACHANDRAN_RESIDUE = 5

# Used only with --save-figure DIR.
FIGURE_NAME = "geometry.png"
FIGURE_DPI = 150


def residue_torsion_columns(header: list[str], residue: int) -> tuple[int, int]:
    suffix = f":{residue}"
    phi = [
        index
        for index, name in enumerate(header)
        if "phi" in name.lower() and name.endswith(suffix)
    ]
    psi = [
        index
        for index, name in enumerate(header)
        if "psi" in name.lower() and name.endswith(suffix)
    ]
    if len(phi) != 1 or len(psi) != 1:
        raise ValueError(f"residue {residue} phi/psi column not found: {header}")
    return phi[0], psi[0]


def read_table(path: Path) -> tuple[list[str], np.ndarray]:
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().lstrip("#").split()
    data = np.loadtxt(path, comments="#", ndmin=2)
    return header, data


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
    print(f"Running: Geometry analysis; input directory: {output_dir}")
    _, geometry = read_table(output_dir / "geometry.dat")
    torsion_header, torsions = read_table(output_dir / "phi_psi.dat")
    if geometry.shape[1] < 4:
        raise ValueError("geometry.dat has too few columns.")
    if not np.array_equal(geometry[:, 0], torsions[:, 0]):
        raise ValueError("Frame indices in the geometry outputs do not match.")
    print(f"Frames: {len(geometry)}")

    phi_column, psi_column = residue_torsion_columns(torsion_header, RAMACHANDRAN_RESIDUE)

    figure, axes = plt.subplots(3, 1, figsize=(8, 10))
    axes[0].plot(geometry[:, 0], geometry[:, 1], label="Terminal Cα distance")
    axes[0].plot(geometry[:, 0], geometry[:, 2], label="Strand minimum heavy-atom distance (residues 1-4 vs 7-10)")
    axes[0].set_ylabel("Distance (Å)")
    axes[0].legend()

    axes[1].plot(geometry[:, 0], geometry[:, 3])
    axes[1].set_xlabel("Frame")
    axes[1].set_ylabel("Cα angle (degree)")

    axes[2].scatter(torsions[:, phi_column], torsions[:, psi_column], s=12, alpha=0.6)
    axes[2].set_xlim(-180, 180)
    axes[2].set_ylim(-180, 180)
    axes[2].set_xlabel(f"Residue {RAMACHANDRAN_RESIDUE} φ (degree)")
    axes[2].set_ylabel(f"Residue {RAMACHANDRAN_RESIDUE} ψ (degree)")

    figure.tight_layout()
    if verify_generation(output_dir) != generation:
        raise ValueError(f"Analysis generation changed while reading: {output_dir}")
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying Geometry analysis figure.")
    plt.show()
    print("Completed: Geometry analysis (interactive figure).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
