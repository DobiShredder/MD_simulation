#!/usr/bin/env python3
"""Summarize segmented OPES_EXPANDED bias output."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from config_utils import load_config  # noqa: E402




def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize completed OPES_EXPANDED production segments."
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(os.environ.get("WORK_DIR", "work")),
        help="Simulation directory (default: WORK_DIR or work)",
    )
    parser.add_argument(
        "--skip-fes",
        action="store_true",
        help="Accepted for interface compatibility; OPES_EXPANDED does not run sum_hills",
    )
    return parser.parse_args()


def check_segments(work: Path, segments: int) -> None:
    for index in range(1, segments + 1):
        directory = work if segments == 1 else work / f"{index:03d}"
        marker = directory / ".production.complete"
        if not marker.is_file():
            raise SystemExit(f"Production segment is incomplete: {marker}")


def read_colvar(path: Path, numpy) -> dict[str, object]:
    fields: list[str] | None = None
    rows: list[list[float]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("#! FIELDS"):
            candidate = raw.split()[2:]
            if fields is None:
                fields = candidate
            elif candidate != fields:
                raise SystemExit(f"COLVAR fields change within the file: {path}")
        elif raw and not raw.startswith("#"):
            rows.append([float(value) for value in raw.split()])
    if fields is None or not rows:
        raise SystemExit(f"COLVAR header or data not found: {path}")
    data = numpy.asarray(rows, dtype=float)
    if data.ndim != 2 or data.shape[1] != len(fields):
        raise SystemExit(f"COLVAR column count does not match its header: {path}")
    return {name: data[:, index] for index, name in enumerate(fields)}


def require_fields(values: dict[str, object], required: set[str], path: Path) -> None:
    missing = sorted(required - values.keys())
    if missing:
        raise SystemExit(f"Required COLVAR fields are missing from {path}: {missing}")


def deltafs_states(path: Path) -> int:
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("#! FIELDS"):
            return max(0, len(raw.split()[2:]) - 1)
    raise SystemExit(f"DELTAFS header not found: {path}")


def write_metrics(path: Path, rows: list[tuple[str, object, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("metric", "value", "unit"))
        writer.writerows(rows)


def main() -> None:
    args = parse_arguments()
    work = args.work_dir
    config_file = work / "resolved_config.toml"
    if not config_file.is_file():
        raise SystemExit(f"Resolved config not found: {config_file}")
    config = load_config(config_file)
    segments = int(config["run"]["production_segments"])
    check_segments(work, segments)

    try:
        import numpy
    except ImportError:
        raise SystemExit("numpy is required to analyze OPES_EXPANDED output") from None

    colvar = work / "COLVAR"
    if not colvar.is_file():
        raise SystemExit(f"COLVAR output not found: {colvar}")
    values = read_colvar(colvar, numpy)
    require_fields(values, {"time"}, colvar)
    output_dir = work / "analysis"
    output_dir.mkdir(exist_ok=True)
    rows: list[tuple[str, object, str]] = [("frames", len(values["time"]), "count")]

    require_fields(values, {"time", "ene", "ecv.ene", "opes.bias"}, colvar)
    deltafs = work / "DELTAFS"
    if not deltafs.is_file():
        raise SystemExit(f"DELTAFS output not found: {deltafs}")
    rows.extend([
        ("energy_min", values["ene"].min(), "kJ/mol"),
        ("energy_max", values["ene"].max(), "kJ/mol"),
        ("expanded_cv_min", values["ecv.ene"].min(), "dimensionless"),
        ("expanded_cv_max", values["ecv.ene"].max(), "dimensionless"),
        ("bias_min", values["opes.bias"].min(), "kJ/mol"),
        ("bias_max", values["opes.bias"].max(), "kJ/mol"),
        ("deltafs_states", deltafs_states(deltafs), "count"),
    ])
    hills = None

    write_metrics(output_dir / "production_summary.tsv", rows)
    print(f"OPES_EXPANDED diagnostics: {output_dir / 'production_summary.tsv'}")


if __name__ == "__main__":
    main()
