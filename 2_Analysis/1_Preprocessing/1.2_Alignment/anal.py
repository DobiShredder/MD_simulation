#!/usr/bin/env python3
"""Backbone fitting 전후 RMSD를 비교한다."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt

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


def main() -> int:
    args = parse_arguments()
    _, before = read_cpptraj_table(args.output / "rmsd_before.dat")
    _, after = read_cpptraj_table(args.output / "rmsd_after.dat")
    frame_count = require_same_rows({"before": before, "after": after})
    if before.shape[1] < 2 or after.shape[1] < 2:
        raise ValueError("RMSD output column이 부족합니다.")

    metadata = read_run_metadata(args.output)
    time_ns = analysis_time_ns(frame_count, metadata)

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.plot(time_ns, before[:, 1], label="Before fitting")
    axis.plot(time_ns, after[:, 1], label="After fitting")
    axis.set_xlabel("Analysis time (ns)")
    axis.set_ylabel("Backbone RMSD (Å)")
    axis.legend()
    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
