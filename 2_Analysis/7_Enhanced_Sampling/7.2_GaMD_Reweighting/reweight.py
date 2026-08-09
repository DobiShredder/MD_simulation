#!/usr/bin/env python3
"""AMBER GaMD boost와 1D CV를 2차 cumulant expansion으로 reweight합니다."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np

GAS_CONSTANT = 0.00198720425864083


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cv", required=True, type=Path)
    parser.add_argument("--log-directory", required=True, type=Path)
    parser.add_argument("--components", required=True, type=int, choices=(2, 3))
    parser.add_argument("--temperature", type=float, default=300.0)
    parser.add_argument("--bin-width", type=float, default=0.25)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def read_cv(path: Path) -> np.ndarray:
    values = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split()
        if not fields or fields[0].startswith("#") or len(fields) < 2:
            continue
        try:
            values.append(float(fields[-1]))
        except ValueError:
            continue
    if not values:
        raise SystemExit(f"CV data를 읽지 못했습니다: {path}")
    return np.asarray(values, dtype=float)


def read_boosts(directory: Path, components: int) -> np.ndarray:
    totals = []
    for segment in range(1, 11):
        path = directory / f"production.{segment:03d}.gamd.log"
        if not path.is_file():
            raise SystemExit(f"GaMD log를 찾을 수 없습니다: {path}")
        segment_values = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            fields = line.split()
            if not fields or fields[0].startswith("#") or len(fields) < 6 + components:
                continue
            try:
                segment_values.append(sum(float(fields[6 + index]) for index in range(components)))
            except ValueError:
                continue
        if len(segment_values) != 100:
            raise SystemExit(f"{path.name}: 100 GaMD records가 필요합니다: {len(segment_values)}")
        totals.extend(segment_values)
    return np.asarray(totals, dtype=float)


def stable_ess(log_weights: np.ndarray) -> float:
    shifted = log_weights - np.max(log_weights)
    weights = np.exp(shifted)
    return float(np.sum(weights) ** 2 / np.sum(weights * weights))


def main() -> None:
    args = arguments()
    if args.temperature <= 0.0 or args.bin_width <= 0.0:
        raise SystemExit("temperature와 bin width는 positive value여야 합니다.")

    cv = read_cv(args.cv)
    boosts = read_boosts(args.log_directory, args.components)
    if len(cv) != len(boosts):
        raise SystemExit(f"CV와 GaMD frame 수가 다릅니다: {len(cv)} != {len(boosts)}")
    if not np.all(np.isfinite(cv)) or not np.all(np.isfinite(boosts)):
        raise SystemExit("CV 또는 boost data에 non-finite value가 있습니다.")

    low = math.floor(float(np.min(cv)) / args.bin_width) * args.bin_width
    high = math.ceil(float(np.max(cv)) / args.bin_width) * args.bin_width
    if high <= low:
        high = low + args.bin_width
    edges = np.arange(low, high + args.bin_width * 1.01, args.bin_width)
    bin_index = np.digitize(cv, edges, right=False) - 1
    bin_index = np.clip(bin_index, 0, len(edges) - 2)

    beta = 1.0 / (GAS_CONSTANT * args.temperature)
    rows = []
    log_unbiased = []
    for index in range(len(edges) - 1):
        selected = boosts[bin_index == index]
        if len(selected) == 0:
            continue
        count = len(selected)
        mean = float(np.mean(selected))
        variance = float(np.var(selected))
        log_factor = beta * mean + 0.5 * beta * beta * variance
        log_unbiased.append(math.log(count) + log_factor)
        rows.append(
            {
                "center": 0.5 * (edges[index] + edges[index + 1]),
                "count": count,
                "biased_probability": count / len(cv),
                "boost_mean": mean,
                "boost_variance": variance,
                "ess": stable_ess(beta * selected),
            }
        )

    log_normalizer = float(np.max(log_unbiased))
    unnormalized = np.exp(np.asarray(log_unbiased) - log_normalizer)
    probabilities = unnormalized / np.sum(unnormalized)
    biased_pmf = -np.log(np.asarray([row["biased_probability"] for row in rows])) / beta
    unbiased_pmf = -np.log(probabilities) / beta
    biased_pmf -= np.min(biased_pmf)
    unbiased_pmf -= np.min(unbiased_pmf)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow([
            "bin_center", "count", "biased_probability", "reweighted_probability",
            "biased_pmf_kcal_mol", "reweighted_pmf_kcal_mol",
            "boost_mean_kcal_mol", "boost_variance_kcal2_mol2", "effective_sample_size",
        ])
        for index, row in enumerate(rows):
            writer.writerow([
                f"{row['center']:.6f}", row["count"], f"{row['biased_probability']:.8e}",
                f"{probabilities[index]:.8e}", f"{biased_pmf[index]:.6f}",
                f"{unbiased_pmf[index]:.6f}", f"{row['boost_mean']:.6f}",
                f"{row['boost_variance']:.6f}", f"{row['ess']:.3f}",
            ])
    print(f"2차 cumulant PMF: {args.output}")


if __name__ == "__main__":
    main()
