#!/usr/bin/env python3
"""Align per-window GaREUS distances and GaMD boosts by frame."""

from __future__ import annotations

import csv
from pathlib import Path


TUTORIAL_DIR = Path.cwd()
SIMULATION_WORK = TUTORIAL_DIR / "../../../1_Simulation/3_REMD/3.5_GaREUS/work"
OUTPUT_DIR = TUTORIAL_DIR / "output"

PRODUCTION_SEGMENTS = 1
GAMD_COMPONENTS = 2
RESTRAINT_FORCE_KCAL_MOL_A2 = 10.0


def read_last_column(path: Path) -> list[float]:
    values = []

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "@")):
            continue

        try:
            values.append(float(line.replace("D", "E").split()[-1]))
        except ValueError:
            continue

    if not values:
        raise ValueError(f"numeric record could not be read: {path}")

    return values


def read_boost(path: Path) -> list[float]:
    values = []

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        fields = line.replace("D", "E").split()
        if len(fields) < 6 + GAMD_COMPONENTS:
            continue

        try:
            boost = 0.0
            for component in range(GAMD_COMPONENTS):
                boost += float(fields[6 + component])
        except ValueError:
            continue

        values.append(boost)

    if not values:
        raise ValueError(f"GaMD boost record could not be read: {path}")

    return values


def read_states(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        states = list(csv.DictReader(handle, delimiter="\t"))

    if len(states) != 20:
        raise ValueError(f"Expected 20 GaREUS states, found {len(states)}")

    return states


def prepare_window(replica: str, replica_dir: Path, output_file: Path) -> int:
    rows = []
    frame = 1

    for segment in range(1, PRODUCTION_SEGMENTS + 1):
        segment_name = f"production.{segment:03d}"
        distance_file = replica_dir / f"restraint.{segment_name}.dat"
        boost_file = replica_dir / f"gamd.{segment_name}.log"

        if not distance_file.is_file():
            raise ValueError(f"restraint output not found: {distance_file}")
        if not boost_file.is_file():
            raise ValueError(f"GaMD log not found: {boost_file}")

        distances = read_last_column(distance_file)
        boosts = read_boost(boost_file)
        if len(distances) != len(boosts):
            raise ValueError(
                f"replica {replica}, segment {segment:03d}: distance and boost record "
                f"counts differ ({len(distances)} != {len(boosts)})."
            )

        for distance, boost in zip(distances, boosts):
            rows.append([frame, segment, f"{distance:.8f}", f"{boost:.8f}"])
            frame += 1

    with output_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["frame", "segment", "distance_A", "boost_kcal_mol"])
        writer.writerows(rows)

    return len(rows)


def prepare_inputs(simulation_work: Path, output_dir: Path) -> int:
    states = read_states(simulation_work / "states.tsv")
    series_dir = output_dir / "series"
    series_dir.mkdir(parents=True, exist_ok=True)

    summary = [["window", "center_A", "amber_rk_kcal_mol_A2", "frames"]]

    for state in states:
        replica = state["replica"]
        replica_dir = simulation_work / replica
        frames = prepare_window(
            replica,
            replica_dir,
            series_dir / f"window_{replica}.tsv",
        )
        summary.append(
            [
                replica,
                state["window_center_A"],
                f"{RESTRAINT_FORCE_KCAL_MOL_A2:.6f}",
                frames,
            ]
        )

    with (output_dir / "summary.tsv").open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, delimiter="\t").writerows(summary)

    return len(states)


def main() -> None:
    try:
        state_count = prepare_inputs(SIMULATION_WORK, OUTPUT_DIR)
    except (OSError, KeyError, ValueError) as error:
        raise SystemExit(f"GaREUS input preparation failed: {error}") from error

    print(f"Organized distances and boosts for {state_count} GaREUS states.")


if __name__ == "__main__":
    main()
