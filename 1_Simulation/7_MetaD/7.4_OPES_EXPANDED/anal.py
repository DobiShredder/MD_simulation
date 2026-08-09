#!/usr/bin/env python3
"""OPES Expanded multithermal bias와 energy 범위를 요약한다."""

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
        raise ValueError(f"COLVAR header 또는 data가 없습니다: {path}")
    data = np.asarray(rows)
    return {name: data[:, index] for index, name in enumerate(fields)}


def count_deltafs_states(path: Path) -> int:
    fields = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#! FIELDS"):
            fields = line.split()[2:]
            break
    if fields is None:
        raise ValueError(f"DELTAFS header가 없습니다: {path}")
    return max(0, len(fields) - 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", nargs="?", type=Path, default=Path(__file__).parent / "work")
    args = parser.parse_args()
    segments = sorted((args.work_dir / "production").glob("[0-9][0-9][0-9]"))
    if len(segments) != 1:
        raise ValueError(f"완료된 production segment가 1개가 아닙니다: {len(segments)}")

    output_dir = args.work_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for segment in segments:
        values = read_colvar(segment / "COLVAR")
        required = {"time", "ene", "ecv.ene", "opes.bias"}
        if not required.issubset(values):
            raise ValueError(f"COLVAR field가 부족합니다: {segment / 'COLVAR'}")
        rows.append((
            segment.name, len(values["time"]),
            values["ene"].min(), values["ene"].max(),
            values["ecv.ene"].min(), values["ecv.ene"].max(),
            values["opes.bias"].min(), values["opes.bias"].max(),
            count_deltafs_states(segment / "DELTAFS"),
        ))

    with (output_dir / "segment_summary.tsv").open("w", encoding="utf-8") as handle:
        handle.write(
            "segment\tframes\tenergy_min_kj_mol\tenergy_max_kj_mol\t"
            "ecv_min\tecv_max\tbias_min_kj_mol\tbias_max_kj_mol\t"
            "deltafs_states\n"
        )
        for row in rows:
            handle.write("\t".join(map(str, row)) + "\n")
    print(f"OPES Expanded 진단 결과: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
