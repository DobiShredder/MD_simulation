#!/usr/bin/env python3
"""WESTPA HDF5에서 weight 보존과 progress-coordinate sampling을 점검합니다."""

from __future__ import annotations

import csv
import os
from pathlib import Path

import h5py


ROOT = Path(__file__).resolve().parent
WORK = Path(os.environ.get("WORK_DIR", ROOT / "work"))
TARGET_RMSD_ANGSTROM = 3.0
BINS = [
    (0.0, 0.5),
    (0.5, 0.75),
    (0.75, 1.0),
    (1.0, 1.25),
    (1.25, 1.5),
    (1.5, 1.75),
    (1.75, 2.0),
    (2.0, 2.25),
    (2.25, 2.5),
    (2.5, 3.0),
    (3.0, float("inf")),
]


def main() -> None:
    west_file = WORK / "west.h5"
    if not west_file.is_file():
        raise SystemExit(f"WESTPA HDF5를 찾을 수 없습니다: {west_file}")

    iteration_rows: list[list[str]] = []
    occupancy_rows: list[list[str]] = []
    target_rows: list[list[str]] = []

    with h5py.File(west_file, "r") as handle:
        iterations = handle.get("iterations")
        if iterations is None:
            raise SystemExit("west.h5에 iterations group이 없습니다.")

        for iteration_name in sorted(iterations):
            group = iterations[iteration_name]
            if "seg_index" not in group or "pcoord" not in group:
                continue
            segment_index = group["seg_index"][:]
            pcoord = group["pcoord"][:]
            weights = [float(record["weight"]) for record in segment_index]
            if not weights:
                continue
            final_coordinates = [float(values[-1][0]) for values in pcoord]
            if len(final_coordinates) != len(weights):
                raise SystemExit(f"{iteration_name}: segment와 pcoord 수가 다릅니다.")
            total_weight = sum(weights)
            squared_weight_sum = sum(weight * weight for weight in weights)
            if squared_weight_sum == 0.0:
                raise SystemExit(f"{iteration_name}: walker weight 합을 계산할 수 없습니다.")
            ess = total_weight * total_weight / squared_weight_sum
            iteration_number = int(iteration_name.split("_")[-1])
            target_count = sum(
                value >= TARGET_RMSD_ANGSTROM for value in final_coordinates
            )
            target_weight = sum(
                weight for weight, value in zip(weights, final_coordinates)
                if value >= TARGET_RMSD_ANGSTROM
            )
            iteration_rows.append([
                str(iteration_number), str(len(weights)), f"{total_weight:.12f}",
                f"{ess:.6f}", f"{min(final_coordinates):.6f}",
                f"{max(final_coordinates):.6f}", str(target_count), f"{target_weight:.12e}",
            ])
            target_rows.append([str(iteration_number), str(target_count), f"{target_weight:.12e}"])

            for bin_index, (lower, upper) in enumerate(BINS):
                members = [
                    index for index, value in enumerate(final_coordinates)
                    if lower <= value < upper
                ]
                occupancy_rows.append([
                    str(iteration_number), str(bin_index), f"{lower:.3f}",
                    "inf" if upper == float("inf") else f"{upper:.3f}",
                    str(len(members)), f"{sum(weights[index] for index in members):.12e}",
                ])

    if not iteration_rows:
        raise SystemExit("완료된 WESTPA iteration을 찾지 못했습니다.")

    with (WORK / "iteration_summary.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["iteration", "segments", "total_weight", "effective_walkers", "min_ca_rmsd_A", "max_ca_rmsd_A", "target_segments", "target_weight"])
        writer.writerows(iteration_rows)
    with (WORK / "bin_occupancy.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["iteration", "bin", "lower_A", "upper_A", "segments", "weight"])
        writer.writerows(occupancy_rows)
    with (WORK / "target_events.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["iteration", "target_segments", "target_weight"])
        writer.writerows(target_rows)

    print(f"WESTPA weight 진단: {WORK / 'iteration_summary.tsv'}")


if __name__ == "__main__":
    main()
