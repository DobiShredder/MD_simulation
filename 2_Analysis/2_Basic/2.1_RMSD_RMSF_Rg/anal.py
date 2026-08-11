#!/usr/bin/env python3
"""Plot Chignolin RMSD, residue RMSF, and radius of gyration."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
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

    figure, axes = plt.subplots(3, 1, figsize=(8, 9))
    axes[0].plot(rmsd_first[:, 0], rmsd_first[:, 1], label="First frame")
    axes[0].plot(rmsd_average[:, 0], rmsd_average[:, 1], label="Average structure")
    axes[0].set_ylabel("Backbone RMSD (Å)")
    axes[0].legend()

    axes[1].plot(rmsf[:, 0], rmsf[:, 1], marker="o")
    axes[1].set_xlabel("Residue")
    axes[1].set_ylabel("Backbone RMSF (Å)")

    axes[2].plot(rg[:, 0], rg[:, 1])
    axes[2].set_xlabel("Frame")
    axes[2].set_ylabel("Radius of gyration (Å)")

    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
