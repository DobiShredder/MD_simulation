#!/usr/bin/env python3
"""AMBER TI output에서 RBFE를 적분하고 sampling 진단을 기록합니다."""

from __future__ import annotations

import csv
import math
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORK = Path(os.environ.get("WORK_DIR", ROOT / "work"))
DVDL_PATTERN = re.compile(r"DV/DL\s*=\s*([-+0-9.Ee]+)")


def read_states() -> list[dict[str, str]]:
    with (WORK / "states.tsv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def parse_dvdl(directory: Path) -> list[float]:
    values: list[float] = []
    for segment in (1, 2):
        path = directory / f"production.{segment:03d}.out"
        if not path.is_file():
            raise SystemExit(f"production output을 찾을 수 없습니다: {path}")
        for match in DVDL_PATTERN.finditer(path.read_text(encoding="utf-8", errors="replace")):
            values.append(float(match.group(1)))
    if not values:
        raise SystemExit(f"DV/DL record를 찾지 못했습니다: {directory}")
    return values


def mean_and_error(values: list[float]) -> tuple[float, float]:
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, math.nan
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return mean, math.sqrt(variance / len(values))


def integrate(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for left, right in zip(points, points[1:]):
        total += (right[0] - left[0]) * (left[1] + right[1]) / 2.0
    return total


def main() -> None:
    rows: list[list[str]] = []
    profiles: dict[str, list[tuple[float, float]]] = {"complex": [], "solvent": []}
    for state in read_states():
        values = parse_dvdl(Path(state["directory"]))
        mean, error = mean_and_error(values)
        profiles[state["leg"]].append((float(state["lambda"]), mean))
        rows.append([state["leg"], state["window"], state["lambda"], str(len(values)), f"{mean:.8f}", f"{error:.8f}"])

    with (WORK / "window_summary.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["leg", "window", "lambda", "samples", "mean_dvdl_kcal_mol", "sem_kcal_mol"])
        writer.writerows(rows)

    complex_dg = integrate(sorted(profiles["complex"]))
    solvent_dg = integrate(sorted(profiles["solvent"]))
    relative_binding = complex_dg - solvent_dg
    with (WORK / "free_energy.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["quantity", "value_kcal_mol"])
        writer.writerow(["complex_delta_g", f"{complex_dg:.8f}"])
        writer.writerow(["solvent_delta_g", f"{solvent_dg:.8f}"])
        writer.writerow(["relative_binding_delta_delta_g", f"{relative_binding:.8f}"])

    print(f"RBFE TI 결과: {WORK / 'free_energy.tsv'}")


if __name__ == "__main__":
    main()
