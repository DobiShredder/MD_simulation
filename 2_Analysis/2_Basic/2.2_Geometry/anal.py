#!/usr/bin/env python3
"""Chignolin distance, angle과 residue 5 phi/psi를 표시한다."""

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


def residue_five_columns(header: list[str]) -> tuple[int, int]:
    phi = [
        index
        for index, name in enumerate(header)
        if "phi" in name.lower() and name.endswith(":5")
    ]
    psi = [
        index
        for index, name in enumerate(header)
        if "psi" in name.lower() and name.endswith(":5")
    ]
    if len(phi) != 1 or len(psi) != 1:
        raise ValueError(f"residue 5 phi/psi column을 찾지 못했습니다: {header}")
    return phi[0], psi[0]


def main() -> int:
    args = parse_arguments()
    _, geometry = read_cpptraj_table(args.output / "geometry.dat")
    torsion_header, torsions = read_cpptraj_table(args.output / "phi_psi.dat")
    frame_count = require_same_rows({"geometry": geometry, "torsions": torsions})
    if geometry.shape[1] < 4:
        raise ValueError("geometry.dat column이 부족합니다.")

    metadata = read_run_metadata(args.output)
    time_ns = analysis_time_ns(frame_count, metadata)
    phi_column, psi_column = residue_five_columns(torsion_header)

    figure, axes = plt.subplots(3, 1, figsize=(8, 10))
    axes[0].plot(time_ns, geometry[:, 1], label="Terminal Cα distance")
    axes[0].plot(time_ns, geometry[:, 2], label="Minimum heavy-atom distance")
    axes[0].set_ylabel("Distance (Å)")
    axes[0].legend()

    axes[1].plot(time_ns, geometry[:, 3])
    axes[1].set_xlabel("Analysis time (ns)")
    axes[1].set_ylabel("Cα angle (degree)")

    axes[2].scatter(torsions[:, phi_column], torsions[:, psi_column], s=12, alpha=0.6)
    axes[2].set_xlim(-180, 180)
    axes[2].set_ylim(-180, 180)
    axes[2].set_xlabel("Residue 5 φ (degree)")
    axes[2].set_ylabel("Residue 5 ψ (degree)")

    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
