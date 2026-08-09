#!/usr/bin/env python3
"""Imaging 전후 Chignolin center displacement를 표시한다."""

from __future__ import annotations

import argparse
from pathlib import Path
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


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "output")
    return parser.parse_args()


def vector_coordinates(path: Path) -> np.ndarray:
    _, data = read_cpptraj_table(path)
    if data.shape[1] < 4:
        raise ValueError(f"vector output column이 부족합니다: {path}")
    return data[:, 1:4]


def main() -> int:
    args = parse_arguments()
    raw_center = vector_coordinates(args.output / "center_raw.dat")
    imaged_center = vector_coordinates(args.output / "center_imaged.dat")
    box_center = vector_coordinates(args.output / "box_center.dat")
    frame_count = require_same_rows(
        {
            "raw": raw_center,
            "imaged": imaged_center,
            "box": box_center,
        }
    )

    metadata = read_run_metadata(args.output)
    time_ns = analysis_time_ns(frame_count, metadata)
    raw_displacement = np.linalg.norm(raw_center - box_center, axis=1)
    imaged_displacement = np.linalg.norm(imaged_center - box_center, axis=1)

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.plot(time_ns, raw_displacement, label="Before autoimage")
    axis.plot(time_ns, imaged_displacement, label="After autoimage")
    axis.set_xlabel("Analysis time (ns)")
    axis.set_ylabel("Protein COM–box center distance (Å)")
    axis.legend()
    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
