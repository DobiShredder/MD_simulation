#!/usr/bin/env python3
"""Plot total Chignolin SASA and mean per-residue contributions."""

from __future__ import annotations

from pathlib import Path

from result_generation import verify_generation

import matplotlib.pyplot as plt
import numpy as np


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    from writer_guard import protect_python_entry
    protect_python_entry("output", reads=(output_dir,))
    generation = verify_generation(output_dir)
    print(f"Running: SASA analysis; input directory: {output_dir}")
    total = np.loadtxt(output_dir / "sasa_total.dat", comments="#", ndmin=2)
    residues = np.loadtxt(output_dir / "sasa_byres.dat", comments="#", ndmin=2)
    if total.shape[1] < 2 or residues.shape[1] != 11:
        raise ValueError("SASA output column count differs from the expected Chignolin residue count.")
    if not np.array_equal(total[:, 0], residues[:, 0]):
        raise ValueError("Frame indices in the SASA outputs do not match.")

    mean_residue_sasa = np.mean(residues[:, 1:], axis=0)

    figure, axes = plt.subplots(2, 1, figsize=(8, 8))
    axes[0].plot(total[:, 0], total[:, 1])
    axes[0].set_xlabel("Frame")
    axes[0].set_ylabel("Protein SASA (Å²)")

    residue_numbers = np.arange(1, 11)
    axes[1].bar(residue_numbers, mean_residue_sasa)
    axes[1].set_xticks(residue_numbers)
    axes[1].set_xlabel("Residue")
    axes[1].set_ylabel("Mean SASA contribution (Å²)")

    figure.tight_layout()
    print("Displaying SASA analysis figure.")
    if verify_generation(output_dir) != generation:
        raise ValueError(f"Analysis generation changed while reading: {output_dir}")
    plt.show()
    print("Completed: SASA analysis (interactive figure).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
