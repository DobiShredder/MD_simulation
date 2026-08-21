#!/usr/bin/env python3
"""Check the logged boost distribution in a LiGaMD3 production log."""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

WORK = Path("work")
COMPONENT_COUNT = 2
EXPECTED_FRAMES = 100
TEMPERATURE_K = 300.0
GAS_CONSTANT = 0.00198720425864083


def parse_log(path: Path) -> list[tuple[int, list[float]]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    column_names = None

    for line in lines:
        stripped = line.lstrip()
        if not stripped.startswith("#") or "total_nstep" not in stripped:
            continue
        column_names = [field.strip() for field in stripped.lstrip("#").split(",")]
        break

    if column_names is None:
        raise SystemExit(f"{path.name}: GaMD column header was not found.")

    normalized_names = [
        re.sub(r"[^a-z0-9]", "", name.lower()) for name in column_names
    ]
    try:
        step_index = normalized_names.index("totalnstep")
    except ValueError as error:
        raise SystemExit(f"{path.name}: total_nstep column was not found.") from error

    boost_indices = [
        index
        for index, name in enumerate(normalized_names)
        if "boost" in name and "energy" in name and "unboosted" not in name
    ]
    if len(boost_indices) != COMPONENT_COUNT:
        raise SystemExit(
            f"{path.name}: expected {COMPONENT_COUNT} boost-energy columns, "
            f"found {len(boost_indices)}: {', '.join(column_names)}"
        )

    records = []
    malformed = []
    last_required_index = max(step_index, *boost_indices)
    for line_number, line in enumerate(lines, start=1):
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        if len(fields) <= last_required_index:
            malformed.append((line_number, line))
            continue
        try:
            step = int(float(fields[step_index]))
            components = [float(fields[index]) for index in boost_indices]
        except ValueError:
            malformed.append((line_number, line))
            continue
        if not all(math.isfinite(value) for value in components):
            malformed.append((line_number, line))
            continue
        records.append((step, components))

    if malformed:
        line_number, line = malformed[0]
        raise SystemExit(
            f"{path.name}: malformed GaMD record at line {line_number}: {line.strip()}"
        )
    if len(records) != EXPECTED_FRAMES:
        raise SystemExit(f"{path.name}: {EXPECTED_FRAMES} GaMD records is required: {len(records)}")
    if any(current[0] <= previous[0] for previous, current in zip(records, records[1:])):
        raise SystemExit(f"{path.name}: timestep does not increase.")
    return records


def anharmonicity(values: list[float]) -> float:
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    if variance <= 0.0:
        return 0.0
    bin_count = min(50, max(5, int(math.sqrt(len(values)))))
    low, high = min(values), max(values)
    width = (high - low) / bin_count
    if width <= 0.0:
        return 0.0
    counts = [0] * bin_count
    for value in values:
        counts[min(int((value - low) / width), bin_count - 1)] += 1
    probabilities = [count / len(values) for count in counts if count]
    entropy = -sum(p * math.log(p / width) for p in probabilities)
    return max(0.0, 0.5 * math.log(2.0 * math.pi * math.e * variance) - entropy)


def effective_sample_size(values: list[float]) -> float:
    beta = 1.0 / (GAS_CONSTANT * TEMPERATURE_K)
    logs = [beta * value for value in values]
    offset = max(logs)
    weights = [math.exp(value - offset) for value in logs]
    return sum(weights) ** 2 / sum(value * value for value in weights)


def main() -> None:
    frame_rows = []
    summary_rows = []
    for segment in (1,):
        path = WORK / "production.gamd.log"
        if not path.is_file():
            raise SystemExit(f"GaMD log not found: {path}")
        records = parse_log(path)
        series = {
            "potential_boost": [components[0] for _, components in records],
            "dihedral_boost": [components[1] for _, components in records],
        }
        series["total"] = [sum(components) for _, components in records]
        for component, values in series.items():
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            summary_rows.append([f"{segment:03d}", component, len(values), min(values), mean, math.sqrt(variance), max(values), anharmonicity(values), effective_sample_size(values)])
        for frame, (step, components) in enumerate(records, start=1):
            frame_rows.append([f"{segment:03d}", frame, step, *components, sum(components)])

    with (WORK / "boost_frames.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow([
            "segment",
            "frame",
            "step",
            "potential_boost_kcal_mol",
            "dihedral_boost_kcal_mol",
            "total_boost_kcal_mol",
        ])
        writer.writerows([[*row[:3], *[f"{value:.6f}" for value in row[3:]]] for row in frame_rows])
    with (WORK / "boost_summary.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["segment", "component", "frames", "min_kcal_mol", "mean_kcal_mol", "std_kcal_mol", "max_kcal_mol", "anharmonicity", "effective_sample_size"])
        writer.writerows([[row[0], row[1], row[2], *[f"{value:.6f}" for value in row[3:]]] for row in summary_rows])
    print(f"LiGaMD3 boost diagnostics: {WORK / 'boost_summary.tsv'}")


if __name__ == "__main__":
    main()
