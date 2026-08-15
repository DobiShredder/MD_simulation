#!/usr/bin/env python3
"""Summarize the WT-MetaD production run and sampled range."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np


def read_colvar(path: Path) -> dict[str, np.ndarray]:
    fields = None
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#! FIELDS"):
            fields = line.split()[2:]
        elif line and not line.startswith("#"):
            rows.append([float(value) for value in line.split()])
    if fields is None or not rows:
        raise ValueError(f"COLVAR header or data not found: {path}")
    data = np.asarray(rows, dtype=float)
    return {name: data[:, index] for index, name in enumerate(fields)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", nargs="?", type=Path, default=Path(__file__).parent / "work")
    parser.add_argument(
        "--skip-fes",
        action="store_true",
        help="Create only the diagnostic TSV without running plumed sum_hills.",
    )
    args = parser.parse_args()

    completion_marker = args.work_dir / ".production.complete"
    if not completion_marker.is_file():
        raise ValueError(f"Production completion marker not found: {completion_marker}")
    for filename in ("COLVAR", "HILLS"):
        path = args.work_dir / filename
        if not path.is_file():
            raise ValueError(f"Production output not found: {path}")

    output_dir = args.work_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    values = read_colvar(args.work_dir / "COLVAR")
    required = {"time", "phi", "psi", "metad.bias", "metad.rbias"}
    if not required.issubset(values):
        raise ValueError(f"Required COLVAR fields are missing: {args.work_dir / 'COLVAR'}")
    if np.any(np.diff(values["time"]) <= 0):
        raise ValueError("Time does not increase within the production COLVAR file.")

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
            str(args.work_dir / "HILLS"),
            "--outfile",
            str(output_dir / "fes.dat"),
            "--mintozero",
        ]
        subprocess.run(command, check=True)

    print(f"WT-MetaD diagnostics results: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
