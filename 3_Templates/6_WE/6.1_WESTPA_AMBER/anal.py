#!/usr/bin/env python3
"""Report weight conservation and progress-coordinate sampling from WESTPA."""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from config_utils import load_config  # noqa: E402


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write WESTPA weight, bin-occupancy, and target-state summaries."
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(os.environ.get("WORK_DIR", "work")),
        help="WESTPA work directory (default: WORK_DIR or work)",
    )
    return parser.parse_args()


def read_boundaries(config_file: Path) -> list[float]:
    config = load_config(config_file)
    raw = config.get("weighted_ensemble", {}).get("bin_boundaries")
    if not isinstance(raw, list) or len(raw) < 2:
        raise SystemExit(f"Invalid bin_boundaries in {config_file}")
    boundaries = [float(value) for value in raw]
    if boundaries != sorted(set(boundaries)):
        raise SystemExit(f"bin_boundaries must be unique and increasing: {config_file}")
    return boundaries


def read_target_values(target_file: Path) -> list[float]:
    values: list[float] = []
    for line_number, raw in enumerate(target_file.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 2:
            raise SystemExit(f"{target_file}:{line_number}: expected LABEL VALUE")
        try:
            values.append(float(fields[1]))
        except ValueError:
            raise SystemExit(f"{target_file}:{line_number}: target value is not numeric") from None
    if not values:
        raise SystemExit(f"No target state was found: {target_file}")
    return values


def make_bins(boundaries: list[float]) -> list[tuple[float, float]]:
    return list(zip(boundaries, boundaries[1:] + [math.inf]))


def target_bin_indices(
    bins: list[tuple[float, float]], target_values: list[float]
) -> set[int]:
    indices: set[int] = set()
    for value in target_values:
        for index, (lower, upper) in enumerate(bins):
            if lower <= value < upper:
                indices.add(index)
                break
        else:
            raise SystemExit(f"Target value {value:g} is below the first bin boundary")
    return indices


def main() -> None:
    args = parse_arguments()
    work = args.work_dir
    west_file = work / "west.h5"
    config_file = work / "resolved_config.toml"
    target_file = work / "tstate.file"
    for required in (west_file, config_file, target_file):
        if not required.is_file():
            raise SystemExit(f"Required WESTPA file not found: {required}")

    try:
        import h5py
    except ImportError:
        raise SystemExit("h5py is required to analyze WESTPA output") from None

    bins = make_bins(read_boundaries(config_file))
    target_bins = target_bin_indices(bins, read_target_values(target_file))
    iteration_rows: list[list[str]] = []
    occupancy_rows: list[list[str]] = []
    target_rows: list[list[str]] = []

    with h5py.File(west_file, "r") as handle:
        iterations = handle.get("iterations")
        if iterations is None:
            raise SystemExit("west.h5 is missing the iterations group")
        current_iteration = int(handle.attrs.get("west_current_iteration", 0))

        for iteration_name in sorted(iterations):
            group = iterations[iteration_name]
            iteration_number = int(iteration_name.split("_")[-1])
            if iteration_number >= current_iteration:
                continue
            if "seg_index" not in group or "pcoord" not in group:
                continue
            segment_index = group["seg_index"][:]
            pcoord = group["pcoord"][:]
            weights = [float(record["weight"]) for record in segment_index]
            if not weights:
                continue
            final_coordinates = [float(values[-1][0]) for values in pcoord]
            if len(final_coordinates) != len(weights):
                raise SystemExit(f"{iteration_name}: segment and pcoord counts differ")

            total_weight = sum(weights)
            squared_weight_sum = sum(weight * weight for weight in weights)
            if squared_weight_sum == 0.0:
                raise SystemExit(f"{iteration_name}: walker weights sum to zero")
            effective_walkers = total_weight * total_weight / squared_weight_sum
            members_by_bin: list[list[int]] = []
            for lower, upper in bins:
                members_by_bin.append([
                    index
                    for index, value in enumerate(final_coordinates)
                    if lower <= value < upper
                ])
            target_members = sorted({
                member
                for bin_index in target_bins
                for member in members_by_bin[bin_index]
            })
            target_weight = sum(weights[index] for index in target_members)

            iteration_rows.append([
                str(iteration_number), str(len(weights)), f"{total_weight:.12f}",
                f"{effective_walkers:.6f}", f"{min(final_coordinates):.6f}",
                f"{max(final_coordinates):.6f}", str(len(target_members)),
                f"{target_weight:.12e}",
            ])
            target_rows.append([
                str(iteration_number), str(len(target_members)), f"{target_weight:.12e}"
            ])

            for bin_index, ((lower, upper), members) in enumerate(
                zip(bins, members_by_bin)
            ):
                occupancy_rows.append([
                    str(iteration_number), str(bin_index), f"{lower:.6f}",
                    "inf" if math.isinf(upper) else f"{upper:.6f}",
                    str(len(members)),
                    f"{sum(weights[index] for index in members):.12e}",
                    "yes" if bin_index in target_bins else "no",
                ])

    if not iteration_rows:
        raise SystemExit("No completed WESTPA iteration was found")

    with (work / "iteration_summary.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow([
            "iteration", "segments", "total_weight", "effective_walkers",
            "min_pcoord_A", "max_pcoord_A", "target_segments", "target_weight",
        ])
        writer.writerows(iteration_rows)
    with (work / "bin_occupancy.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow([
            "iteration", "bin", "lower_A", "upper_A", "segments", "weight",
            "target_bin",
        ])
        writer.writerows(occupancy_rows)
    with (work / "target_events.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["iteration", "target_segments", "target_weight"])
        writer.writerows(target_rows)

    print(f"WESTPA weight diagnostics: {work / 'iteration_summary.tsv'}")


if __name__ == "__main__":
    main()
