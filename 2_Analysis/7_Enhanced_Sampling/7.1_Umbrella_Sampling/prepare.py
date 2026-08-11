#!/usr/bin/env python3
"""Prepare per-window distance series from AMBER DUMPAVE files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


TUTORIAL_DIR = Path.cwd()
WINDOWS_DIR = TUTORIAL_DIR / "../../../1_Simulation/2_US/us/work"
OUTPUT_DIR = TUTORIAL_DIR / "output"

TIME_COLUMN = 1
DISTANCE_COLUMN = 8
DISCARD_PS = 100.0


@dataclass(frozen=True)
class Window:
    name: str
    center_angstrom: float
    amber_force: float
    directory: Path


def read_window(directory: Path) -> Window:
    metadata = directory / "window.tsv"
    if not metadata.is_file():
        raise ValueError(f"window metadata not found: {metadata}")

    with metadata.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    if len(rows) != 1:
        raise ValueError(f"Invalid window metadata format: {metadata}")

    row = rows[0]
    return Window(
        name=row["window"],
        center_angstrom=float(row["center_A"]),
        amber_force=float(row["force_kcal_mol_A2"]),
        directory=directory,
    )


def discover_windows(root: Path) -> list[Window]:
    windows = []
    for directory in sorted(root.glob("[0-9][0-9][0-9]")):
        if directory.is_dir():
            windows.append(read_window(directory))

    if not windows:
        raise ValueError(f"umbrella window not found: {root}")

    centers = [window.center_angstrom for window in windows]
    if centers != sorted(centers) or len(centers) != len(set(centers)):
        raise ValueError("Window centers must be unique and increasing.")

    return windows


def read_dumpave(path: Path) -> list[tuple[float, float]]:
    required_columns = max(TIME_COLUMN, DISTANCE_COLUMN)
    values = []

    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith(("#", "@")):
                continue

            fields = line.replace("D", "E").split()
            if len(fields) < required_columns:
                continue

            try:
                time_ps = float(fields[TIME_COLUMN - 1])
                distance_angstrom = float(fields[DISTANCE_COLUMN - 1])
            except ValueError:
                continue

            values.append((time_ps, distance_angstrom))

    if not values:
        raise ValueError(f"DUMPAVE numeric record could not be read: {path}")

    return values


def prepare_windows(windows_dir: Path, output_dir: Path) -> int:
    windows = discover_windows(windows_dir)
    series_dir = output_dir / "series"
    series_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = [
        [
            "window",
            "center_A",
            "amber_rk_kcal_mol_A2",
            "frames",
            "first_time_ps",
            "last_time_ps",
        ]
    ]

    for window in windows:
        source = window.directory / "distance.dat"
        if not source.is_file():
            raise ValueError(f"DUMPAVE output not found: {source}")

        values = read_dumpave(source)
        first_production_time = values[0][0] + DISCARD_PS
        kept = []
        for time_ps, distance_angstrom in values:
            if time_ps >= first_production_time:
                kept.append((time_ps, distance_angstrom))

        if not kept:
            raise ValueError(f"No frames remain after discarding data: {source}")

        series_file = series_dir / f"window_{window.name}.dat"
        with series_file.open("w", encoding="utf-8") as handle:
            handle.write("time_ps\tdistance_A\n")
            for time_ps, distance_angstrom in kept:
                handle.write(f"{time_ps:.6f}\t{distance_angstrom:.8f}\n")

        summary_rows.append(
            [
                window.name,
                f"{window.center_angstrom:.6f}",
                f"{window.amber_force:.6f}",
                str(len(kept)),
                f"{kept[0][0]:.6f}",
                f"{kept[-1][0]:.6f}",
            ]
        )

    with (output_dir / "summary.tsv").open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, delimiter="\t").writerows(summary_rows)

    return len(windows)


def main() -> None:
    try:
        window_count = prepare_windows(WINDOWS_DIR, OUTPUT_DIR)
    except (OSError, KeyError, ValueError) as error:
        raise SystemExit(f"WHAM input preparation failed: {error}") from error

    print(f"Organized {window_count} windows.")


if __name__ == "__main__":
    main()
