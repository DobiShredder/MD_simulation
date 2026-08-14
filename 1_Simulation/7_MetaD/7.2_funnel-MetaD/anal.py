#!/usr/bin/env python3
"""Summarize Funnel MetaD segments, funnel sampling, and bias range."""

from __future__ import annotations

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
    parser.add_argument(
        "work_dir",
        nargs="?",
        type=Path,
        default=Path(__file__).parent / "work",
    )
    parser.add_argument("--skip-fes", action="store_true")
    args = parser.parse_args()

    segment_dirs = sorted((args.work_dir / "production").glob("[0-9][0-9][0-9]"))

    if len(segment_dirs) != 1:
        raise ValueError(f"Expected exactly one production segment: {len(segment_dirs)}")
    for segment_dir in segment_dirs:
        if not (segment_dir / ".complete").is_file():
            raise ValueError(
                f"Production completion marker not found: {segment_dir / '.complete'}"
            )

    required_fields = {
        "time",
        "fps.lp",
        "fps.ld",
        "funnel.bias",
        "lower.bias",
        "upper.bias",
        "metad.bias",
        "metad.rbias",
    }
    summaries = []
    all_lp = []
    all_ld = []
    all_funnel_bias = []

    for segment_dir in segment_dirs:
        values = read_colvar(segment_dir / "COLVAR")

        if not required_fields.issubset(values):
            missing = sorted(required_fields - values.keys())
            raise ValueError(f"{segment_dir.name} Required COLVAR fields are missing: {missing}")

        lp = values["fps.lp"]
        ld = values["fps.ld"]
        funnel_bias = values["funnel.bias"]
        metad_bias = values["metad.bias"]
        all_lp.append(lp)
        all_ld.append(ld)
        all_funnel_bias.append(funnel_bias)
        summaries.append(
            (
                segment_dir.name,
                len(lp),
                lp.min(),
                lp.max(),
                ld.min(),
                ld.max(),
                funnel_bias.max(),
                metad_bias.min(),
                metad_bias.max(),
            )
        )

    output_dir = args.work_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "segment_summary.tsv").open("w", encoding="utf-8") as handle:
        handle.write(
            "segment\tframes\tlp_min_nm\tlp_max_nm\tld_min_nm\tld_max_nm\t"
            "funnel_bias_max_kj_mol\tmetad_bias_min_kj_mol\tmetad_bias_max_kj_mol\n"
        )
        for row in summaries:
            handle.write("\t".join(map(str, row)) + "\n")

    lp = np.concatenate(all_lp)
    ld = np.concatenate(all_ld)
    funnel_bias = np.concatenate(all_funnel_bias)
    cylinder = lp >= 1.8
    cone_cylinder_crossings = int(np.count_nonzero(cylinder[1:] != cylinder[:-1]))
    boundary_frames = int(np.count_nonzero(funnel_bias > 0.0))

    with (output_dir / "sampling_summary.tsv").open("w", encoding="utf-8") as handle:
        handle.write(
            "frames\tlp_min_nm\tlp_max_nm\tld_min_nm\tld_max_nm\t"
            "cone_cylinder_crossings\tcylinder_fraction\tfunnel_boundary_frames\n"
        )
        handle.write(
            f"{len(lp)}\t{lp.min()}\t{lp.max()}\t{ld.min()}\t{ld.max()}\t"
            f"{cone_cylinder_crossings}\t{cylinder.mean()}\t{boundary_frames}\n"
        )

    if not args.skip_fes:
        plumed = os.environ.get("PLUMED", "plumed")

        if shutil.which(plumed) is None:
            raise FileNotFoundError(
                f"plumed not found: {plumed}. --skip-fesuse."
            )

        hills = segment_dirs[-1] / "HILLS"
        subprocess.run(
            [
                plumed,
                "sum_hills",
                "--hills",
                str(hills),
                "--outfile",
                str(output_dir / "fes.dat"),
                "--mintozero",
            ],
            check=True,
        )

    print(f"Funnel MetaD diagnostics results: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
