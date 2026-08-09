#!/usr/bin/env python3
"""Chignolin residue contact frequency map과 contact 수를 표시한다."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analysis_utils import (
    analysis_time_ns,
    read_cpptraj_table,
    read_run_metadata,
    require_same_rows,
)


RESIDUE_COUNT = 10


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "output")
    return parser.parse_args()


def residue_pair(label: str) -> tuple[int, int] | None:
    residues = [int(value) for value in re.findall(r":(\d+)", label)]
    if len(residues) >= 2:
        return residues[0], residues[1]
    return None


def contact_frequency(header: list[str], data: np.ndarray) -> np.ndarray:
    pair_series: dict[tuple[int, int], np.ndarray] = {}

    for column, label in enumerate(header[1:], start=1):
        pair = residue_pair(label)
        if pair is None:
            continue
        residue_1, residue_2 = pair
        if not (1 <= residue_1 <= RESIDUE_COUNT and 1 <= residue_2 <= RESIDUE_COUNT):
            continue
        ordered_pair = tuple(sorted((residue_1, residue_2)))
        present = data[:, column] > 0
        if ordered_pair in pair_series:
            pair_series[ordered_pair] |= present
        else:
            pair_series[ordered_pair] = present.copy()

    if not pair_series:
        raise ValueError(f"residue contact label을 해석하지 못했습니다: {header}")

    frequency = np.zeros((RESIDUE_COUNT, RESIDUE_COUNT), dtype=float)
    for pair, present in pair_series.items():
        residue_1, residue_2 = pair
        value = float(np.mean(present))
        frequency[residue_1 - 1, residue_2 - 1] = value
        frequency[residue_2 - 1, residue_1 - 1] = value
    return frequency


def write_frequency(path: Path, frequency: np.ndarray) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write("residue_1\tresidue_2\tcontact_frequency\n")
        for residue_1 in range(1, RESIDUE_COUNT + 1):
            for residue_2 in range(residue_1 + 1, RESIDUE_COUNT + 1):
                handle.write(
                    f"{residue_1}\t{residue_2}\t"
                    f"{frequency[residue_1 - 1, residue_2 - 1]:.8f}\n"
                )


def main() -> int:
    args = parse_arguments()
    _, counts = read_cpptraj_table(args.output / "contact_count.dat")
    series_header, series = read_cpptraj_table(
        args.output / "contact_residue_series.dat"
    )
    frame_count = require_same_rows({"counts": counts, "series": series})
    if counts.shape[1] < 3:
        raise ValueError("contact count output column이 부족합니다.")

    frequency = contact_frequency(series_header, series)
    write_frequency(args.output / "contact_frequency.tsv", frequency)

    metadata = read_run_metadata(args.output)
    time_ns = analysis_time_ns(frame_count, metadata)

    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].plot(time_ns, counts[:, 1], label="Native")
    axes[0].plot(time_ns, counts[:, 2], label="Non-native")
    axes[0].set_xlabel("Analysis time (ns)")
    axes[0].set_ylabel("Heavy-atom contact count")
    axes[0].legend()

    image = axes[1].imshow(frequency, vmin=0, vmax=1, origin="lower", cmap="viridis")
    ticks = np.arange(RESIDUE_COUNT)
    axes[1].set_xticks(ticks, ticks + 1)
    axes[1].set_yticks(ticks, ticks + 1)
    axes[1].set_xlabel("Residue")
    axes[1].set_ylabel("Residue")
    axes[1].set_title("Contact frequency")
    figure.colorbar(image, ax=axes[1], label="Frame fraction")

    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
