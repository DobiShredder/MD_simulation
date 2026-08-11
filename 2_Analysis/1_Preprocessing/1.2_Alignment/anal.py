#!/usr/bin/env python3
"""Compare RMSD before and after backbone fitting."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    before = np.loadtxt(output_dir / "rmsd_before.dat", comments="#", ndmin=2)
    after = np.loadtxt(output_dir / "rmsd_after.dat", comments="#", ndmin=2)
    if before.shape[1] < 2 or after.shape[1] < 2:
        raise ValueError("RMSD output has too few columns.")
    if not np.array_equal(before[:, 0], after[:, 0]):
        raise ValueError("RMSD output frame indices do not match.")

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.plot(before[:, 0], before[:, 1], label="Before fitting")
    axis.plot(after[:, 0], after[:, 1], label="After fitting")
    axis.set_xlabel("Frame")
    axis.set_ylabel("Backbone RMSD (Å)")
    axis.legend()
    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
