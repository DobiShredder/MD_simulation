#!/usr/bin/env python3
"""Chignolin 전체 SASA와 residue별 평균 기여도를 표시한다."""

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


def main() -> int:
    args = parse_arguments()
    _, total = read_cpptraj_table(args.output / "sasa_total.dat")
    _, residues = read_cpptraj_table(args.output / "sasa_byres.dat")
    frame_count = require_same_rows({"total": total, "residues": residues})
    if total.shape[1] < 2 or residues.shape[1] != 11:
        raise ValueError("SASA output column이 예상한 Chignolin residue 수와 다릅니다.")

    metadata = read_run_metadata(args.output)
    time_ns = analysis_time_ns(frame_count, metadata)
    mean_residue_sasa = np.mean(residues[:, 1:], axis=0)

    figure, axes = plt.subplots(2, 1, figsize=(8, 8))
    axes[0].plot(time_ns, total[:, 1])
    axes[0].set_xlabel("Analysis time (ns)")
    axes[0].set_ylabel("Protein SASA (Å²)")

    residue_numbers = np.arange(1, 11)
    axes[1].bar(residue_numbers, mean_residue_sasa)
    axes[1].set_xticks(residue_numbers)
    axes[1].set_xlabel("Residue")
    axes[1].set_ylabel("Mean SASA contribution (Å²)")

    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
