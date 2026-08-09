#!/usr/bin/env python3
"""변환된 frame과 원본 trajectory frame의 mapping을 표시한다."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "output")
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    mapping_path = args.output / "frame_map.tsv"
    with mapping_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise ValueError(f"frame mapping이 비어 있습니다: {mapping_path}")

    figure, axis = plt.subplots(figsize=(8, 4.5))
    source_indices = sorted({int(row["source_index"]) for row in rows})
    for source_index in source_indices:
        selected = [row for row in rows if int(row["source_index"]) == source_index]
        axis.plot(
            [int(row["output_frame"]) for row in selected],
            [int(row["source_frame"]) for row in selected],
            marker=".",
            linestyle="none",
            label=f"Source {source_index}",
        )

    axis.set_xlabel("Output frame")
    axis.set_ylabel("Source frame")
    axis.legend()
    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
