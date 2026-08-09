#!/usr/bin/env python3
"""Analysis tutorial plotting에 공통으로 사용하는 작은 file parser."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def read_cpptraj_table(path: Path) -> tuple[list[str], np.ndarray]:
    """cpptraj text output의 header와 numeric data를 읽는다."""
    header: list[str] = []
    rows: list[list[float]] = []

    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                candidate = line.lstrip("#").strip().split()
                if candidate:
                    header = candidate
                continue
            try:
                rows.append([float(value) for value in line.split()])
            except ValueError:
                continue

    if not rows:
        raise ValueError(f"numeric data가 없습니다: {path}")

    data = np.asarray(rows, dtype=float)
    if data.ndim == 1:
        data = data.reshape(1, -1)

    if len(header) != data.shape[1]:
        header = [f"column_{index + 1}" for index in range(data.shape[1])]

    return header, data


def read_run_metadata(output_dir: Path) -> dict[str, str]:
    """run.sh가 기록한 key-value metadata를 읽는다."""
    metadata_path = output_dir / "run_metadata.tsv"
    metadata: dict[str, str] = {}

    with metadata_path.open(encoding="utf-8") as handle:
        next(handle, None)
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if not line:
                continue
            key, value = line.split("\t", maxsplit=1)
            metadata[key] = value

    return metadata


def analysis_time_ns(frame_count: int, metadata: dict[str, str]) -> np.ndarray:
    """선택된 첫 frame을 0으로 둔 analysis time을 ns로 반환한다."""
    interval_ps = float(metadata["effective_frame_interval_ps"])
    return np.arange(frame_count, dtype=float) * interval_ps / 1000.0


def require_same_rows(named_tables: dict[str, np.ndarray]) -> int:
    """관련 output의 row 수가 같은지 확인한다."""
    counts = {name: table.shape[0] for name, table in named_tables.items()}
    if len(set(counts.values())) != 1:
        raise ValueError(f"frame 수가 일치하지 않습니다: {counts}")
    return next(iter(counts.values()))
