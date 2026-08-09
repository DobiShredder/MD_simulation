#!/usr/bin/env python3
"""GaMD production log의 boost distribution과 segment continuity를 점검합니다."""

from __future__ import annotations

import csv
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = Path(os.environ.get("WORK_DIR", ROOT / "work"))
COMPONENT_COUNT = 2
EXPECTED_SEGMENTS = 1
EXPECTED_FRAMES = 100
TEMPERATURE_K = 300.0
GAS_CONSTANT = 0.00198720425864083


def parse_log(path: Path) -> list[tuple[int, list[float]]]:
    records: list[tuple[int, list[float]]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split()
        if not fields or fields[0].startswith("#") or len(fields) < 6 + COMPONENT_COUNT:
            continue
        try:
            step = int(float(fields[1]))
            components = [float(fields[6 + index]) for index in range(COMPONENT_COUNT)]
        except ValueError:
            continue
        records.append((step, components))

    if len(records) != EXPECTED_FRAMES:
        raise SystemExit(
            f"{path.name}: {EXPECTED_FRAMES} GaMD records가 필요합니다: {len(records)}"
        )
    if any(current[0] <= previous[0] for previous, current in zip(records, records[1:])):
        raise SystemExit(f"{path.name}: timestep이 증가하지 않습니다.")
    return records


def anharmonicity(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    if variance <= 0.0:
        return 0.0

    bin_count = min(50, max(5, int(math.sqrt(len(values)))))
    low, high = min(values), max(values)
    if high == low:
        return 0.0
    width = (high - low) / bin_count
    counts = [0] * bin_count
    for value in values:
        index = min(int((value - low) / width), bin_count - 1)
        counts[index] += 1
    probabilities = [count / len(values) for count in counts if count]
    entropy = -sum(p * math.log(p / width) for p in probabilities)
    gaussian_entropy = 0.5 * math.log(2.0 * math.pi * math.e * variance)
    return max(0.0, gaussian_entropy - entropy)


def effective_sample_size(values: list[float]) -> float:
    beta = 1.0 / (GAS_CONSTANT * TEMPERATURE_K)
    log_weights = [beta * value for value in values]
    offset = max(log_weights)
    weights = [math.exp(value - offset) for value in log_weights]
    return sum(weights) ** 2 / sum(weight * weight for weight in weights)


def main() -> None:
    all_records: list[tuple[int, int, list[float]]] = []
    summaries: list[list[str]] = []

    for segment in range(1, EXPECTED_SEGMENTS + 1):
        path = WORK / f"production.{segment:03d}.gamd.log"
        if not path.is_file():
            raise SystemExit(f"GaMD log를 찾을 수 없습니다: {path}")
        records = parse_log(path)
        series = {
            f"boost_{index + 1}": [components[index] for _, components in records]
            for index in range(COMPONENT_COUNT)
        }
        series["total"] = [sum(components) for _, components in records]
        for component, values in series.items():
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            summaries.append(
                [
                    f"{segment:03d}", component, str(len(values)),
                    f"{min(values):.6f}", f"{mean:.6f}",
                    f"{math.sqrt(variance):.6f}", f"{max(values):.6f}",
                    f"{anharmonicity(values):.6f}",
                    f"{effective_sample_size(values):.3f}",
                ]
            )
        for frame, (step, components) in enumerate(records, start=1):
            all_records.append((segment, frame, [float(step), *components, sum(components)]))

    with (WORK / "boost_frames.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["segment", "frame", "step", "boost_1_kcal_mol", "boost_2_kcal_mol", "total_boost_kcal_mol"])
        for segment, frame, values in all_records:
            writer.writerow([f"{segment:03d}", frame, *[f"{value:.6f}" for value in values]])

    with (WORK / "boost_summary.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["segment", "component", "frames", "min_kcal_mol", "mean_kcal_mol", "std_kcal_mol", "max_kcal_mol", "anharmonicity", "effective_sample_size"])
        writer.writerows(summaries)

    print(f"GaMD boost 진단: {WORK / 'boost_summary.tsv'}")


if __name__ == "__main__":
    main()
