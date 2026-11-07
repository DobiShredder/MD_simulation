#!/usr/bin/env python3
"""Plot Chignolin center displacement before and after imaging."""

from __future__ import annotations

import argparse
from pathlib import Path

from result_generation import verify_generation

import matplotlib.pyplot as plt
import numpy as np


# Used only with --save-figure DIR.
FIGURE_NAME = "imaging.png"
FIGURE_DPI = 150


def vector_coordinates(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, comments="#", ndmin=2)
    if data.shape[1] < 4:
        raise ValueError(f"Vector output has too few columns: {path}")
    return data[:, 0], data[:, 1:4]


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
    print(f"Running: Imaging analysis; input directory: {output_dir}")
    frames, raw_center = vector_coordinates(output_dir / "center_raw.dat")
    imaged_frames, imaged_center = vector_coordinates(
        output_dir / "center_imaged.dat"
    )
    box_frames, box_center = vector_coordinates(output_dir / "box_center.dat")
    if not np.array_equal(frames, imaged_frames) or not np.array_equal(
        frames, box_frames
    ):
        raise ValueError("Frame indices in the imaging outputs do not match.")
    print(f"Frames: {len(frames)}")

    raw_displacement = np.linalg.norm(raw_center - box_center, axis=1)
    imaged_displacement = np.linalg.norm(imaged_center - box_center, axis=1)

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.plot(frames, raw_displacement, label="Before autoimage")
    axis.plot(frames, imaged_displacement, label="After autoimage")
    axis.set_xlabel("Frame")
    axis.set_ylabel("Protein COM–box center distance (Å)")
    axis.legend()
    figure.tight_layout()
    if verify_generation(output_dir) != generation:
        raise ValueError(f"Analysis generation changed while reading: {output_dir}")
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying Imaging analysis figure.")
    plt.show()
    print("Completed: Imaging analysis (interactive figure).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
