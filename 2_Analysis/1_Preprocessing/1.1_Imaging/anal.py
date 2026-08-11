#!/usr/bin/env python3
"""Plot Chignolin center displacement before and after imaging."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def vector_coordinates(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, comments="#", ndmin=2)
    if data.shape[1] < 4:
        raise ValueError(f"Vector output has too few columns: {path}")
    return data[:, 0], data[:, 1:4]


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    frames, raw_center = vector_coordinates(output_dir / "center_raw.dat")
    imaged_frames, imaged_center = vector_coordinates(
        output_dir / "center_imaged.dat"
    )
    box_frames, box_center = vector_coordinates(output_dir / "box_center.dat")
    if not np.array_equal(frames, imaged_frames) or not np.array_equal(
        frames, box_frames
    ):
        raise ValueError("Frame indices in the imaging outputs do not match.")

    raw_displacement = np.linalg.norm(raw_center - box_center, axis=1)
    imaged_displacement = np.linalg.norm(imaged_center - box_center, axis=1)

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.plot(frames, raw_displacement, label="Before autoimage")
    axis.plot(frames, imaged_displacement, label="After autoimage")
    axis.set_xlabel("Frame")
    axis.set_ylabel("Protein COM–box center distance (Å)")
    axis.legend()
    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
