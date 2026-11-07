#!/usr/bin/env python3
"""Summarize segmented OPES_METAD bias output."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, "helpers")
from config_utils import load_config  # noqa: E402




def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize completed OPES_METAD production segments."
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
        help="Accepted for interface compatibility; OPES_METAD does not run sum_hills",
    )
    return parser.parse_args()


def check_segments(work: Path, segments: int) -> None:
    for index in range(1, segments + 1):
        if index == 1 and (work / ".production.complete").is_file():
            directory = work
        else:
            directory = work / f"{index:03d}"
        marker = directory / ".production.complete"
        if not marker.is_file():
            raise SystemExit(f"Production segment is incomplete: {marker}")


def read_colvar(path: Path, numpy) -> dict[str, object]:
    fields = None
    rows = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if line.startswith("#! FIELDS"):
            candidate = line.split()[2:]
            if not candidate or len(candidate) != len(set(candidate)):
                raise ValueError(f"COLVAR fields are empty or duplicated: {path}:{line_number}")
            if fields is not None and fields != candidate:
                raise ValueError(f"COLVAR header changed: {path}:{line_number}")
            fields = candidate
        elif line and not line.startswith("#"):
            if fields is None:
                raise ValueError(f"COLVAR data precedes its header: {path}:{line_number}")
            values = line.split()
            if len(values) != len(fields):
                raise ValueError(f"COLVAR column count differs from header: {path}:{line_number}")
            try:
                row = [float(value) for value in values]
            except ValueError as error:
                raise ValueError(f"COLVAR contains nonnumeric data: {path}:{line_number}") from error
            if not numpy.isfinite(row).all():
                raise ValueError(f"COLVAR contains nonfinite data: {path}:{line_number}")
            rows.append(row)
    if fields is None or not rows:
        raise ValueError(f"COLVAR header or data not found: {path}")
    data = numpy.asarray(rows, dtype=float)
    return {name: data[:, index] for index, name in enumerate(fields)}


def require_fields(values: dict[str, object], required: set[str], path: Path) -> None:
    missing = sorted(required - values.keys())
    if missing:
        raise SystemExit(f"Required COLVAR fields are missing from {path}: {missing}")



def write_metrics(path: Path, rows: list[tuple[str, object, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("metric", "value", "unit"))
        writer.writerows(rows)


def main() -> None:
    args = parse_arguments()
    work = args.work_dir
    from helpers.writer_guard import protect_python_entry
    protect_python_entry(work, reads=(work,), writes=(work / "analysis",))
    print(f"Reading bias-analysis inputs: {work}", flush=True)
    config_file = work / "resolved_config.toml"
    if not config_file.is_file():
        raise SystemExit(f"Resolved config not found: {config_file}")
    config = load_config(config_file)
    segments = int(config["run"]["production_segments"])
    check_segments(work, segments)

    try:
        import numpy
    except ImportError:
        raise SystemExit("numpy is required to analyze OPES_METAD output") from None

    colvar = work / "COLVAR"
    if not colvar.is_file():
        raise SystemExit(f"COLVAR output not found: {colvar}")
    print(f"Calculating COLVAR diagnostics: {colvar}", flush=True)
    values = read_colvar(colvar, numpy)
    require_fields(values, {"time"}, colvar)
    output_dir = work / "analysis"
    output_dir.mkdir(exist_ok=True)
    rows: list[tuple[str, object, str]] = [("frames", len(values["time"]), "count")]

    arguments = list(config["collective_variable"]["arguments"])
    require_fields(
        values, {"time", "opes.bias", "opes.neff", "opes.nker", *arguments}, colvar
    )
    for argument in arguments:
        rows.extend([
            (f"{argument}_min", values[argument].min(), "CV unit"),
            (f"{argument}_max", values[argument].max(), "CV unit"),
        ])
    rows.extend([
        ("bias_min", values["opes.bias"].min(), "kJ/mol"),
        ("bias_max", values["opes.bias"].max(), "kJ/mol"),
        ("effective_samples_final", values["opes.neff"][-1], "count"),
        ("kernels_final", values["opes.nker"][-1], "count"),
    ])
    write_metrics(output_dir / "production_summary.tsv", rows)
    print(f"OPES_METAD diagnostics: {output_dir / 'production_summary.tsv'}")


if __name__ == "__main__":
    main()
