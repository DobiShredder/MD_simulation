#!/usr/bin/env python3
"""Plot the Chignolin residue-contact frequency map and contact counts."""

from __future__ import annotations

from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np


RESIDUE_COUNT = 10


def read_table(path: Path) -> tuple[list[str], np.ndarray]:
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().lstrip("#").split()
    data = np.loadtxt(path, comments="#", ndmin=2)
    return header, data


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
        raise ValueError(f"Could not parse residue-contact label: {header}")

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
    output_dir = Path(__file__).resolve().parent / "output"
    _, counts = read_table(output_dir / "contact_count.dat")
    series_header, series = read_table(output_dir / "contact_residue_series.dat")
    if counts.shape[1] < 3:
        raise ValueError("Contact-count output has too few columns.")
    if not np.array_equal(counts[:, 0], series[:, 0]):
        raise ValueError("Frame indices in the contact outputs do not match.")

    frequency = contact_frequency(series_header, series)
    write_frequency(output_dir / "contact_frequency.tsv", frequency)

    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].plot(counts[:, 0], counts[:, 1], label="Native")
    axes[0].plot(counts[:, 0], counts[:, 2], label="Non-native")
    axes[0].set_xlabel("Frame")
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
