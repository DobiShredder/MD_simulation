#!/usr/bin/env python3
"""Chignolin secondary structure의 residue-time map과 전체 분율을 표시한다."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analysis_utils import (
    analysis_time_ns,
    read_cpptraj_table,
    read_run_metadata,
    require_same_rows,
)


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


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "output")
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    _, assignments = read_cpptraj_table(args.output / "secondary_structure.dat")
    _, totals = read_cpptraj_table(args.output / "secondary_total.dat")
    frame_count = require_same_rows({"assignments": assignments, "totals": totals})
    if assignments.shape[1] != 11 or totals.shape[1] != 8:
        raise ValueError("secondary structure output column이 예상한 형식과 다릅니다.")

    metadata = read_run_metadata(args.output)
    time_ns = analysis_time_ns(frame_count, metadata)
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
        extent=[time_ns[0], time_ns[-1] if len(time_ns) > 1 else 0, 0.5, 10.5],
    )
    axes[0].set_xlabel("Analysis time (ns)")
    axes[0].set_ylabel("Residue")
    axes[0].set_yticks(np.arange(1, 11))
    color_bar = figure.colorbar(image, ax=axes[0], ticks=np.arange(8))
    color_bar.ax.set_yticklabels(STRUCTURE_LABELS)

    none_fraction = np.clip(1.0 - np.sum(totals[:, 1:], axis=1), 0.0, 1.0)
    axes[1].plot(time_ns, none_fraction, label=STRUCTURE_LABELS[0])
    for column, label in enumerate(STRUCTURE_LABELS[1:], start=1):
        axes[1].plot(time_ns, totals[:, column], label=label)
    axes[1].set_xlabel("Analysis time (ns)")
    axes[1].set_ylabel("Residue fraction")
    axes[1].set_ylim(0, 1)
    axes[1].legend(ncol=4, fontsize="small")

    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
