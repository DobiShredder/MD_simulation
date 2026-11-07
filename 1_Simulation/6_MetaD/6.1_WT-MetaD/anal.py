#!/usr/bin/env python3
"""Summarize the WT-MetaD production run and sampled range."""

import argparse
import os
from pathlib import Path

from helpers.result_generation import result_generation
import shutil
import subprocess

import numpy as np


def read_colvar(path: Path) -> dict[str, np.ndarray]:
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
            if not np.isfinite(row).all():
                raise ValueError(f"COLVAR contains nonfinite data: {path}:{line_number}")
            rows.append(row)
    if fields is None or not rows:
        raise ValueError(f"COLVAR header or data not found: {path}")
    data = np.asarray(rows, dtype=float)
    return {name: data[:, index] for index, name in enumerate(fields)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-fes",
        action="store_true",
        help="Create only the diagnostic TSV without running plumed sum_hills.",
    )
    args = parser.parse_args()

    work_dir = Path("work")
    from helpers.writer_guard import protect_python_entry
    protect_python_entry(work_dir, reads=(work_dir,), writes=(work_dir / "analysis",))
    print(f"Reading bias-analysis inputs: {work_dir}", flush=True)
    for filename in ("COLVAR", "HILLS"):
        path = work_dir / filename
        if not path.is_file():
            raise ValueError(f"Production output not found: {path}")

    output_dir = work_dir / "analysis"
    completed_output_dir = output_dir
    with result_generation(completed_output_dir) as output_dir:
        print(f"Calculating COLVAR diagnostics: {work_dir / 'COLVAR'}", flush=True)
        values = read_colvar(work_dir / "COLVAR")
        required = {"time", "phi", "psi", "metad.bias", "metad.rbias"}
        if not required.issubset(values):
            raise ValueError(f"Required COLVAR fields are missing: {work_dir / 'COLVAR'}")
        if np.any(np.diff(values["time"]) <= 0):
            raise ValueError(f"Time does not increase within the production COLVAR file: {work_dir / 'COLVAR'}")

        phi = values["phi"]
        psi = values["psi"]
        bias = values["metad.bias"]
        with (output_dir / "production_summary.tsv").open("w", encoding="utf-8") as handle:
            handle.write(
                "frames\tphi_min\tphi_max\tpsi_min\tpsi_max\t"
                "bias_min_kj_mol\tbias_max_kj_mol\n"
            )
            row = (
                len(phi),
                phi.min(),
                phi.max(),
                psi.min(),
                psi.max(),
                bias.min(),
                bias.max(),
            )
            handle.write("\t".join(map(str, row)) + "\n")

        phi_crossings = int(np.count_nonzero(np.signbit(phi[1:]) != np.signbit(phi[:-1])))
        psi_crossings = int(np.count_nonzero(np.signbit(psi[1:]) != np.signbit(psi[:-1])))
        with (output_dir / "sampling_summary.tsv").open("w", encoding="utf-8") as handle:
            handle.write(
                "frames\tphi_min\tphi_max\tpsi_min\tpsi_max\t"
                "phi_zero_crossings\tpsi_zero_crossings\n"
            )
            handle.write(
                f"{len(phi)}\t{phi.min()}\t{phi.max()}\t{psi.min()}\t{psi.max()}\t"
                f"{phi_crossings}\t{psi_crossings}\n"
            )

        if not args.skip_fes:
            plumed = os.environ.get("PLUMED", "plumed")
            if shutil.which(plumed) is None:
                message = (
                    f"plumed not found: {plumed}. "
                    "Use --skip-fes to create only the TSV."
                )
                raise FileNotFoundError(message)
            command = [
                plumed,
                "sum_hills",
                "--hills",
                str(work_dir / "HILLS"),
                "--outfile",
                str(output_dir / "fes.dat"),
                "--mintozero",
            ]
            print(f"Calculating FES: {work_dir / 'HILLS'} -> {output_dir / 'fes.dat'}", flush=True)
            subprocess.run(command, check=True)

            fes = output_dir / "fes.dat"
            if not fes.is_file() or fes.stat().st_size == 0:
                raise ValueError(f"FES calculation: plumed sum_hills did not create a nonempty output: {fes}")
            print(f"FES output: {fes}")
        else:
            print("Skipping FES calculation (--skip-fes).")

    output_dir = completed_output_dir
    print(f"WT-MetaD diagnostics results: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
