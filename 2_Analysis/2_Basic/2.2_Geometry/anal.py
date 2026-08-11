#!/usr/bin/env python3
"""Plot Chignolin distances, angles, and residue-5 phi/psi."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def residue_five_columns(header: list[str]) -> tuple[int, int]:
    phi = [
        index
        for index, name in enumerate(header)
        if "phi" in name.lower() and name.endswith(":5")
    ]
    psi = [
        index
        for index, name in enumerate(header)
        if "psi" in name.lower() and name.endswith(":5")
    ]
    if len(phi) != 1 or len(psi) != 1:
        raise ValueError(f"residue 5 phi/psi column not found: {header}")
    return phi[0], psi[0]


def read_table(path: Path) -> tuple[list[str], np.ndarray]:
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().lstrip("#").split()
    data = np.loadtxt(path, comments="#", ndmin=2)
    return header, data


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    _, geometry = read_table(output_dir / "geometry.dat")
    torsion_header, torsions = read_table(output_dir / "phi_psi.dat")
    if geometry.shape[1] < 4:
        raise ValueError("geometry.dat has too few columns.")
    if not np.array_equal(geometry[:, 0], torsions[:, 0]):
        raise ValueError("Frame indices in the geometry outputs do not match.")

    phi_column, psi_column = residue_five_columns(torsion_header)

    figure, axes = plt.subplots(3, 1, figsize=(8, 10))
    axes[0].plot(geometry[:, 0], geometry[:, 1], label="Terminal Cα distance")
    axes[0].plot(geometry[:, 0], geometry[:, 2], label="Minimum heavy-atom distance")
    axes[0].set_ylabel("Distance (Å)")
    axes[0].legend()

    axes[1].plot(geometry[:, 0], geometry[:, 3])
    axes[1].set_xlabel("Frame")
    axes[1].set_ylabel("Cα angle (degree)")

    axes[2].scatter(torsions[:, phi_column], torsions[:, psi_column], s=12, alpha=0.6)
    axes[2].set_xlim(-180, 180)
    axes[2].set_ylim(-180, 180)
    axes[2].set_xlabel("Residue 5 φ (degree)")
    axes[2].set_ylabel("Residue 5 ψ (degree)")

    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
