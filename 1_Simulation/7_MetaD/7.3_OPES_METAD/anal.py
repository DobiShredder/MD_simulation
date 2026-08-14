#!/usr/bin/env python3
"""Summarize OPES_METAD bias and adaptive-kernel state."""

import argparse
from pathlib import Path
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
    data = np.asarray(rows)
    return {name: data[:, index] for index, name in enumerate(fields)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", nargs="?", type=Path, default=Path(__file__).parent / "work")
    args = parser.parse_args()
    segments = sorted((args.work_dir / "production").glob("[0-9][0-9][0-9]"))
    if len(segments) != 1:
        raise ValueError(f"Expected exactly one completed production segment: {len(segments)}")
    for segment in segments:
        if not (segment / ".complete").is_file():
            raise ValueError(
                f"Production completion marker not found: {segment / '.complete'}"
            )

    output_dir = args.work_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for segment in segments:
        values = read_colvar(segment / "COLVAR")
        required = {"time", "phi", "psi", "opes.bias", "opes.neff", "opes.nker"}
        if not required.issubset(values):
            raise ValueError(f"Required COLVAR fields are missing: {segment / 'COLVAR'}")
        rows.append((
            segment.name,
            len(values["time"]),
            values["phi"].min(), values["phi"].max(),
            values["psi"].min(), values["psi"].max(),
            values["opes.bias"].min(), values["opes.bias"].max(),
            values["opes.neff"][-1], values["opes.nker"][-1],
        ))

    with (output_dir / "segment_summary.tsv").open("w", encoding="utf-8") as handle:
        handle.write(
            "segment\tframes\tphi_min\tphi_max\tpsi_min\tpsi_max\t"
            "bias_min_kj_mol\tbias_max_kj_mol\tneff_final\tnker_final\n"
        )
        for row in rows:
            handle.write("\t".join(map(str, row)) + "\n")
    print(f"OPES_METAD diagnostics results: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
