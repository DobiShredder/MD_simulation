#!/usr/bin/env python3
"""Plot the Chignolin residue-contact frequency map and contact counts."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

from result_generation import input_generation

import matplotlib.pyplot as plt
import numpy as np


# Chignolin residue count; residue pairs outside 1-RESIDUE_COUNT are ignored.
RESIDUE_COUNT = 10

# Used only with --save-figure DIR.
FIGURE_NAME = "contacts.png"
FIGURE_DPI = 150


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
    protect_python_entry("output", writes=(output_dir,))
    completed_output_dir = output_dir
    with input_generation(output_dir) as output_dir:
        print(f"Running: Contacts analysis; input directory: {output_dir}")
        _, counts = read_table(output_dir / "contact_count.dat")
        if counts.shape[0] == 0 or counts.shape[1] < 3:
            raise ValueError("Contact-count output is empty or has too few columns.")
        if not np.all(np.isfinite(counts)) or np.any(counts[:, 1:3] < 0):
            raise ValueError("Contact-count output contains invalid values.")
        print(f"Frames: {len(counts)}")
        if np.all(counts[:, 1:3] == 0):
            frequency = np.zeros((RESIDUE_COUNT, RESIDUE_COUNT), dtype=float)
        else:
            series_header, series = read_table(output_dir / "contact_residue_series.dat")
            if not np.array_equal(counts[:, 0], series[:, 0]):
                raise ValueError("Frame indices in the contact outputs do not match.")
            frequency = contact_frequency(series_header, series)
        write_frequency(output_dir / "contact_frequency.tsv", frequency)
    # contact_frequency.tsv is published when the block above ends, before the
    # figure opens, so closing the window or pressing Ctrl-C keeps the result.
    output_dir = completed_output_dir
    print(f"Contact frequency: {output_dir / 'contact_frequency.tsv'}")

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
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying Contacts analysis figure.")
    plt.show()
    print(f"Completed: Contacts analysis; results: {output_dir} (figure displayed interactively)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
