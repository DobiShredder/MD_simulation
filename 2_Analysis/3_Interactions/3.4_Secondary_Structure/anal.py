#!/usr/bin/env python3
"""Plot the Chignolin secondary-structure residue-time map and overall fractions."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np


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


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    assignments = np.loadtxt(
        output_dir / "secondary_structure.dat", comments="#", ndmin=2
    )
    totals = np.loadtxt(output_dir / "secondary_total.dat", comments="#", ndmin=2)
    if assignments.shape[1] != 11 or totals.shape[1] != 8:
        raise ValueError("Secondary-structure output columns do not match the expected format.")
    if not np.array_equal(assignments[:, 0], totals[:, 0]):
        raise ValueError("Frame indices in the secondary-structure outputs do not match.")

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
        extent=[frames[0], frames[-1] if len(frames) > 1 else 0, 0.5, 10.5],
    )
    axes[0].set_xlabel("Frame")
    axes[0].set_ylabel("Residue")
    axes[0].set_yticks(np.arange(1, 11))
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
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
