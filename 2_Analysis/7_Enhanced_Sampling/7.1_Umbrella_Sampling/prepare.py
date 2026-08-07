#!/usr/bin/env python3
"""Prepare AMBER DUMPAVE series and WHAM metadata."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Window:
    name: str
    center: float
    amber_force: float
    directory: Path


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--windows",
        type=Path,
        default=script_dir.parents[2] / "1_Simulation" / "2_US" / "us" / "work" / "windows",
    )
    parser.add_argument("--output", type=Path, default=script_dir / "output")
    parser.add_argument("--time-column", type=int, default=1)
    parser.add_argument("--distance-column", type=int, default=8)
    parser.add_argument("--discard-ps", type=float, default=1000.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_window(directory: Path) -> Window:
    metadata = directory / "window.tsv"
    if not metadata.is_file():
        raise ValueError(f"missing window metadata: {metadata}")
    rows = [line.split() for line in metadata.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 2 or len(rows[1]) != 3:
        raise ValueError(f"unexpected window metadata format: {metadata}")
    name, center, force = rows[1]
    return Window(name=name, center=float(center), amber_force=float(force), directory=directory)


def discover_windows(root: Path) -> list[Window]:
    windows = [read_window(path) for path in sorted(root.glob("[0-9][0-9][0-9]")) if path.is_dir()]
    if not windows:
        raise ValueError(f"no umbrella windows under {root}")
    centers = [window.center for window in windows]
    if centers != sorted(centers) or len(centers) != len(set(centers)):
        raise ValueError("window centers must be unique and increasing")
    return windows


def read_dumpave(path: Path, time_column: int, distance_column: int) -> list[tuple[float, float]]:
    if time_column < 1 or distance_column < 1:
        raise ValueError("column numbers are one-based and must be positive")
    required = max(time_column, distance_column)
    values: list[tuple[float, float]] = []
    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.replace("D", "E").split()
            if len(fields) < required:
                continue
            try:
                time = float(fields[time_column - 1])
                distance = float(fields[distance_column - 1])
            except ValueError:
                continue
            values.append((time, distance))
    if not values:
        raise ValueError(f"no numeric DUMPAVE rows found in {path}")
    return values


def main() -> int:
    args = parse_args()
    windows = discover_windows(args.windows)

    if args.dry_run:
        print(f"window input: {args.windows} ({len(windows)} windows)")
        print(f"output: {args.output}")
        print(
            f"DUMPAVE columns: time={args.time_column}, distance={args.distance_column}; "
            f"discard={args.discard_ps:g} ps"
        )
        return 0

    series_dir = args.output / "series"
    series_dir.mkdir(parents=True, exist_ok=True)
    metadata_rows: list[str] = []
    summary_rows = ["window\tcenter_A\tamber_rm2\twham_k\tframes\tfirst_time_ps\tlast_time_ps"]

    for window in windows:
        source = window.directory / "distance.dat"
        if not source.is_file():
            raise SystemExit(f"DUMPAVE output을 찾을 수 없습니다: {source}")
        values = read_dumpave(source, args.time_column, args.distance_column)
        cutoff = values[0][0] + args.discard_ps
        kept = [(time, distance) for time, distance in values if time >= cutoff]
        if not kept:
            raise SystemExit(f"discard 이후 frame이 없습니다: {source}")

        destination = (series_dir / f"window_{window.name}.dat").resolve()
        with destination.open("w", encoding="utf-8") as handle:
            for time, distance in kept:
                handle.write(f"{time:.6f}\t{distance:.8f}\n")

        wham_force = 2.0 * window.amber_force
        metadata_rows.append(f"{destination}\t{window.center:.6f}\t{wham_force:.6f}")
        summary_rows.append(
            f"{window.name}\t{window.center:.6f}\t{window.amber_force:.6f}\t"
            f"{wham_force:.6f}\t{len(kept)}\t{kept[0][0]:.6f}\t{kept[-1][0]:.6f}"
        )

    (args.output / "metadata.dat").write_text("\n".join(metadata_rows) + "\n", encoding="utf-8")
    (args.output / "summary.tsv").write_text("\n".join(summary_rows) + "\n", encoding="utf-8")
    print(f"WHAM input {len(windows)}개를 생성했습니다: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
