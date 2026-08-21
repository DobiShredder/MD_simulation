#!/usr/bin/env python3
"""Summarize segmented MetaD and OPES bias output."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from config_utils import load_config  # noqa: E402


METHODS = ("wt-metad", "funnel-metad", "opes-metad", "opes-expanded")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize completed MetaD or OPES production segments."
    )
    parser.add_argument("method", choices=METHODS, help="MetaD or OPES method")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(os.environ.get("WORK_DIR", "work")),
        help="Simulation directory (default: WORK_DIR or work)",
    )
    parser.add_argument(
        "--skip-fes",
        action="store_true",
        help="Skip plumed sum_hills for WT-MetaD and Funnel-MetaD",
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
        raise SystemExit("numpy is required to analyze MetaD output") from None

    colvar = work / "COLVAR"
    if not colvar.is_file():
        raise SystemExit(f"COLVAR output not found: {colvar}")
    values = read_colvar(colvar, numpy)
    require_fields(values, {"time"}, colvar)
    output_dir = work / "analysis"
    output_dir.mkdir(exist_ok=True)
    rows: list[tuple[str, object, str]] = [("frames", len(values["time"]), "count")]

    if args.method == "wt-metad":
        arguments = list(config["collective_variable"]["arguments"])
        require_fields(values, {"time", "metad.bias", "metad.rbias", *arguments}, colvar)
        for argument in arguments:
            rows.extend([
                (f"{argument}_min", values[argument].min(), "CV unit"),
                (f"{argument}_max", values[argument].max(), "CV unit"),
            ])
        rows.extend([
            ("bias_min", values["metad.bias"].min(), "kJ/mol"),
            ("bias_max", values["metad.bias"].max(), "kJ/mol"),
        ])
        hills = work / "HILLS"
    elif args.method == "funnel-metad":
        required = {
            "time", "fps.lp", "fps.ld", "funnel.bias", "lower.bias",
            "upper.bias", "metad.bias", "metad.rbias",
        }
        require_fields(values, required, colvar)
        rows.extend([
            ("lp_min", values["fps.lp"].min(), "nm"),
            ("lp_max", values["fps.lp"].max(), "nm"),
            ("ld_min", values["fps.ld"].min(), "nm"),
            ("ld_max", values["fps.ld"].max(), "nm"),
            ("funnel_bias_max", values["funnel.bias"].max(), "kJ/mol"),
            ("metad_bias_max", values["metad.bias"].max(), "kJ/mol"),
        ])
        hills = work / "HILLS"
    elif args.method == "opes-metad":
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
        hills = None
    else:
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
    if hills is not None and not args.skip_fes:
        if not hills.is_file():
            raise SystemExit(f"HILLS output not found: {hills}")
        plumed = os.environ.get("PLUMED", "plumed")
        if shutil.which(plumed) is None:
            raise SystemExit(f"plumed not found: {plumed}; use --skip-fes")
        subprocess.run([
            plumed, "sum_hills", "--hills", str(hills),
            "--outfile", str(output_dir / "fes.dat"), "--mintozero",
        ], check=True)
    print(f"MetaD diagnostics: {output_dir / 'production_summary.tsv'}")


if __name__ == "__main__":
    main()
