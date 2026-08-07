#!/usr/bin/env python3
"""Calculate adjacent-window histogram overlap coefficients."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=script_dir / "output" / "summary.tsv")
    parser.add_argument("--series", type=Path, default=script_dir / "output" / "series")
    parser.add_argument("--output", type=Path, default=script_dir / "output" / "overlap.tsv")
    parser.add_argument("--bins", type=int, default=50)
    return parser.parse_args()


def read_series(path: Path) -> list[float]:
    values = [float(line.split()[1]) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not values:
        raise ValueError(f"empty series: {path}")
    return values


def histogram(values: list[float], lower: float, upper: float, bins: int) -> list[float]:
    width = (upper - lower) / bins
    counts = [0] * bins
    for value in values:
        index = min(int((value - lower) / width), bins - 1)
        index = max(index, 0)
        counts[index] += 1
    total = sum(counts)
    return [count / total for count in counts]


def main() -> int:
    args = parse_args()
    if args.bins < 2:
        raise SystemExit("--bins는 2 이상이어야 합니다.")

    rows = [line.split() for line in args.summary.read_text(encoding="utf-8").splitlines()[1:] if line.strip()]
    if len(rows) < 2:
        raise SystemExit("overlap 계산에는 두 개 이상의 window가 필요합니다.")

    output = ["left\tright\tleft_center_A\tright_center_A\toverlap"]
    for left, right in zip(rows, rows[1:]):
        left_values = read_series(args.series / f"window_{left[0]}.dat")
        right_values = read_series(args.series / f"window_{right[0]}.dat")
        lower = min(left_values + right_values)
        upper = max(left_values + right_values)
        if upper == lower:
            coefficient = 1.0
        else:
            left_hist = histogram(left_values, lower, upper, args.bins)
            right_hist = histogram(right_values, lower, upper, args.bins)
            coefficient = sum(min(a, b) for a, b in zip(left_hist, right_hist))
        output.append(f"{left[0]}\t{right[0]}\t{left[1]}\t{right[1]}\t{coefficient:.6f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"Neighboring overlap {len(rows) - 1}개를 계산했습니다: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
