#!/usr/bin/env python3
"""Check weight conservation and progress-coordinate sampling in WESTPA HDF5."""

from __future__ import annotations

import csv
from pathlib import Path

import h5py
import math
import numbers


WORK = Path("work")
TARGET_RMSD_ANGSTROM = 3.0
# WESTPA Segment.SEG_STATUS_COMPLETE in the HDF5 seg_index schema.
SEG_STATUS_COMPLETE = 2
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
    from helpers.writer_guard import protect_python_entry
    protect_python_entry(WORK, writes=(WORK,))
    west_file = WORK / "west.h5"
    print(f"Reading WESTPA weight and pcoord data: {west_file}", flush=True)
    if not west_file.is_file():
        raise SystemExit(f"WESTPA HDF5 not found: {west_file}")

    iteration_rows: list[list[str]] = []
    occupancy_rows: list[list[str]] = []
    target_rows: list[list[str]] = []

    with h5py.File(west_file, "r") as handle:
        iterations = handle.get("iterations")
        if iterations is None:
            raise SystemExit(f"WESTPA analysis: {west_file} is missing the iterations group.")

        current_iteration = handle.attrs.get("west_current_iteration")
        if not isinstance(current_iteration, numbers.Integral) or current_iteration < 1:
            raise SystemExit(f"WESTPA analysis: invalid west_current_iteration in {west_file}")

        for iteration_name in sorted(iterations):
            iteration_number = int(iteration_name.split("_")[-1])
            if iteration_number >= current_iteration:
                continue
            group = iterations[iteration_name]
            if "seg_index" not in group or "pcoord" not in group:
                raise SystemExit(f"WESTPA analysis: {west_file}, {iteration_name}: completed iteration data is missing")
            segment_index = group["seg_index"][:]
            pcoord = group["pcoord"][:]
            if segment_index.ndim != 1 or not segment_index.dtype.names or "weight" not in segment_index.dtype.names:
                raise SystemExit(f"WESTPA analysis: {west_file}, {iteration_name}: invalid segment weight schema")
            if "status" not in segment_index.dtype.names or segment_index["status"].dtype.kind not in "iu":
                raise SystemExit(f"WESTPA analysis: {west_file}, {iteration_name}: invalid segment status schema")
            if not all(status == SEG_STATUS_COMPLETE for status in segment_index["status"]):
                raise SystemExit(f"WESTPA analysis: {west_file}, {iteration_name}: not all segments are complete")
            if pcoord.ndim != 3 or pcoord.shape[0] != len(segment_index) or pcoord.shape[1] == 0 or pcoord.shape[2] != 1:
                raise SystemExit(f"WESTPA analysis: {west_file}, {iteration_name}: expected one-dimensional pcoord for each segment")
            if pcoord.dtype.kind not in "fiu" or segment_index["weight"].dtype.kind not in "fiu":
                raise SystemExit(f"WESTPA analysis: {west_file}, {iteration_name}: weights and pcoord must be numeric")
            if not all(math.isfinite(float(value)) for value in pcoord.flat):
                raise SystemExit(f"WESTPA analysis: {west_file}, {iteration_name}: nonfinite pcoord")
            weights = [float(record["weight"]) for record in segment_index]
            if not all(math.isfinite(weight) and weight >= 0 for weight in weights):
                raise SystemExit(f"WESTPA analysis: {west_file}, {iteration_name}: weights must be finite and nonnegative")
            if not weights:
                continue
            final_coordinates = [float(values[-1][0]) for values in pcoord]
            if len(final_coordinates) != len(weights):
                raise SystemExit(f"WESTPA analysis: {west_file}, {iteration_name}: segment and pcoord counts differ.")
            total_weight = sum(weights)
            squared_weight_sum = sum(weight * weight for weight in weights)
            if not math.isfinite(total_weight) or not math.isfinite(squared_weight_sum) or total_weight <= 0:
                raise SystemExit(f"WESTPA analysis: {west_file}, {iteration_name}: invalid total walker weight")
            if squared_weight_sum == 0.0:
                raise SystemExit(f"WESTPA analysis: {west_file}, {iteration_name}: could not calculate the total walker weight.")
            ess = total_weight * total_weight / squared_weight_sum
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
        raise SystemExit(f"No completed WESTPA iteration was found in {west_file}.")

    print(f"Writing WESTPA diagnostics: {WORK}", flush=True)
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

    print(f"WESTPA weight diagnostics: {WORK / 'iteration_summary.tsv'}")


if __name__ == "__main__":
    main()
