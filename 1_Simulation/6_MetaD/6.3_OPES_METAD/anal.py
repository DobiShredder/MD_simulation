#!/usr/bin/env python3
"""Summarize OPES_METAD bias and adaptive-kernel state."""

from pathlib import Path
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
    work_dir = Path("work")
    from helpers.writer_guard import protect_python_entry
    protect_python_entry(work_dir, reads=(work_dir,), writes=(work_dir / "analysis",))
    print(f"Reading bias-analysis inputs: {work_dir}", flush=True)
    for filename in ("COLVAR", "KERNELS", "opes.state"):
        path = work_dir / filename
        if not path.is_file():
            raise ValueError(f"Production output not found: {path}")

    output_dir = work_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Calculating COLVAR diagnostics: {work_dir / 'COLVAR'}", flush=True)
    values = read_colvar(work_dir / "COLVAR")
    required = {"time", "phi", "psi", "opes.bias", "opes.neff", "opes.nker"}
    if not required.issubset(values):
        raise ValueError(f"Required COLVAR fields are missing: {work_dir / 'COLVAR'}")

    with (output_dir / "production_summary.tsv").open("w", encoding="utf-8") as handle:
        handle.write(
            "frames\tphi_min\tphi_max\tpsi_min\tpsi_max\t"
            "bias_min_kj_mol\tbias_max_kj_mol\tneff_final\tnker_final\n"
        )
        row = (
            len(values["time"]),
            values["phi"].min(), values["phi"].max(),
            values["psi"].min(), values["psi"].max(),
            values["opes.bias"].min(), values["opes.bias"].max(),
            values["opes.neff"][-1], values["opes.nker"][-1],
        )
        handle.write("\t".join(map(str, row)) + "\n")
    print(f"OPES_METAD diagnostics results: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
