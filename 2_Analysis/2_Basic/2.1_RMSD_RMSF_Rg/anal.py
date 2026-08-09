#!/usr/bin/env python3
"""Chignolin RMSD, residue RMSF와 radius of gyration을 표시한다."""

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
    _, rmsd_first = read_cpptraj_table(args.output / "rmsd_first.dat")
    _, rmsd_average = read_cpptraj_table(args.output / "rmsd_average.dat")
    _, rmsf = read_cpptraj_table(args.output / "rmsf_byres.dat")
    _, rg = read_cpptraj_table(args.output / "rg.dat")

    frame_count = require_same_rows(
        {
            "rmsd_first": rmsd_first,
            "rmsd_average": rmsd_average,
            "rg": rg,
        }
    )
    metadata = read_run_metadata(args.output)
    time_ns = analysis_time_ns(frame_count, metadata)

    figure, axes = plt.subplots(3, 1, figsize=(8, 9))
    axes[0].plot(time_ns, rmsd_first[:, 1], label="First frame")
    axes[0].plot(time_ns, rmsd_average[:, 1], label="Average structure")
    axes[0].set_ylabel("Backbone RMSD (Å)")
    axes[0].legend()

    axes[1].plot(rmsf[:, 0], rmsf[:, 1], marker="o")
    axes[1].set_xlabel("Residue")
    axes[1].set_ylabel("Backbone RMSF (Å)")

    axes[2].plot(time_ns, rg[:, 1])
    axes[2].set_xlabel("Analysis time (ns)")
    axes[2].set_ylabel("Radius of gyration (Å)")

    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
