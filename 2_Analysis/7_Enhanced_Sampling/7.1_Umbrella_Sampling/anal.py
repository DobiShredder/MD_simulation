#!/usr/bin/env python3
"""NumPy로 1D WHAM PMF와 neighboring-window overlap을 계산합니다."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


TUTORIAL_DIR = Path.cwd()
OUTPUT_DIR = TUTORIAL_DIR / "output"

TEMPERATURE_KELVIN = 300.0
PMF_MIN_ANGSTROM = 5.0
PMF_MAX_ANGSTROM = 25.0
PMF_BINS = 100
WHAM_TOLERANCE_KCAL_MOL = 1.0e-8
WHAM_MAX_ITERATIONS = 100000
OVERLAP_BINS = 50

GAS_CONSTANT_KCAL_MOL_K = 0.00198720425864083


def logsumexp(values: np.ndarray, axis: int | None = None) -> np.ndarray:
    maximum = np.max(values, axis=axis, keepdims=True)
    result = maximum + np.log(np.sum(np.exp(values - maximum), axis=axis, keepdims=True))
    if axis is None:
        return np.asarray(result.squeeze())
    return np.squeeze(result, axis=axis)


def read_inputs(
    output_dir: Path,
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray], list[str]]:
    summary = output_dir / "summary.tsv"
    if not summary.is_file():
        raise ValueError("./run.sh를 먼저 실행해야 합니다: output/summary.tsv")

    with summary.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    if len(rows) < 2:
        raise ValueError("WHAM에는 두 개 이상의 window가 필요합니다.")

    centers = []
    forces = []
    series = []
    names = []

    for row in rows:
        name = row["window"]
        path = output_dir / "series" / f"window_{name}.dat"
        if not path.is_file():
            raise ValueError(f"distance series를 찾을 수 없습니다: {path}")

        values = np.loadtxt(path, skiprows=1, usecols=1, ndmin=1)
        if values.size == 0 or not np.all(np.isfinite(values)):
            raise ValueError(f"distance series가 비었거나 유효하지 않습니다: {path}")

        names.append(name)
        centers.append(float(row["center_A"]))
        forces.append(float(row["amber_rk_kcal_mol_A2"]))
        series.append(values)

    return np.asarray(centers), np.asarray(forces), series, names


def solve_wham(
    centers: np.ndarray,
    forces: np.ndarray,
    series: list[np.ndarray],
    temperature_kelvin: float,
    edges: np.ndarray,
    tolerance_kcal_mol: float,
    maximum_iterations: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, float]:
    if temperature_kelvin <= 0.0:
        raise ValueError("temperature는 positive value여야 합니다.")
    if tolerance_kcal_mol <= 0.0 or maximum_iterations < 1:
        raise ValueError("WHAM tolerance와 maximum iterations를 확인하십시오.")

    counts = np.asarray(
        [np.histogram(values, bins=edges)[0] for values in series],
        dtype=float,
    )
    sample_counts = counts.sum(axis=1)
    expected_counts = np.asarray([len(values) for values in series], dtype=float)

    if not np.array_equal(sample_counts, expected_counts):
        raise ValueError("PMF 범위 밖의 frame이 있습니다. PMF_MIN/MAX를 수정하십시오.")
    if np.any(sample_counts == 0):
        raise ValueError("sample이 없는 window가 있습니다.")

    bin_centers = 0.5 * (edges[:-1] + edges[1:])
    bias = forces[:, None] * (bin_centers[None, :] - centers[:, None]) ** 2
    beta = 1.0 / (GAS_CONSTANT_KCAL_MOL_K * temperature_kelvin)
    offsets = np.zeros(len(centers), dtype=float)
    occupied = counts.sum(axis=0) > 0

    for iteration in range(1, maximum_iterations + 1):
        log_denominator = logsumexp(
            np.log(sample_counts)[:, None] + beta * (offsets[:, None] - bias),
            axis=0,
        )

        log_probability = np.full(len(bin_centers), -np.inf)
        log_probability[occupied] = (
            np.log(counts[:, occupied].sum(axis=0)) - log_denominator[occupied]
        )
        log_probability[occupied] -= logsumexp(log_probability[occupied])

        new_offsets = -logsumexp(log_probability[None, :] - beta * bias, axis=1) / beta
        new_offsets -= new_offsets[0]
        residual = float(np.max(np.abs(new_offsets - offsets)))
        offsets = new_offsets

        if residual < tolerance_kcal_mol:
            probability = np.zeros(len(bin_centers), dtype=float)
            probability[occupied] = np.exp(log_probability[occupied])
            return bin_centers, probability, counts, offsets, iteration, residual

    raise ValueError(
        f"WHAM이 {maximum_iterations} iterations 안에 수렴하지 않았습니다. "
        f"마지막 residual={residual:.3e} kcal/mol"
    )


def overlap_coefficients(series: list[np.ndarray]) -> list[float]:
    coefficients = []

    for left, right in zip(series, series[1:]):
        lower = min(float(np.min(left)), float(np.min(right)))
        upper = max(float(np.max(left)), float(np.max(right)))

        if upper == lower:
            coefficients.append(1.0)
            continue

        left_counts = np.histogram(left, bins=OVERLAP_BINS, range=(lower, upper))[0]
        right_counts = np.histogram(right, bins=OVERLAP_BINS, range=(lower, upper))[0]
        left_probability = left_counts / left_counts.sum()
        right_probability = right_counts / right_counts.sum()
        coefficients.append(float(np.minimum(left_probability, right_probability).sum()))

    return coefficients


def write_results(
    output_dir: Path,
    bin_centers: np.ndarray,
    probability: np.ndarray,
    counts: np.ndarray,
    offsets: np.ndarray,
    centers: np.ndarray,
    names: list[str],
    overlap: list[float],
    iterations: int,
    residual: float,
) -> np.ndarray:
    occupied = probability > 0.0
    pmf = np.full(len(probability), np.nan)
    pmf[occupied] = (
        -GAS_CONSTANT_KCAL_MOL_K
        * TEMPERATURE_KELVIN
        * np.log(probability[occupied])
    )
    pmf[occupied] -= np.min(pmf[occupied])

    with (output_dir / "pmf.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["distance_A", "count", "probability", "pmf_kcal_mol"])
        for center, count, value, free_energy in zip(
            bin_centers, counts.sum(axis=0), probability, pmf
        ):
            writer.writerow(
                [
                    f"{center:.6f}",
                    int(count),
                    f"{value:.10e}",
                    "nan" if np.isnan(free_energy) else f"{free_energy:.6f}",
                ]
            )

    with (output_dir / "overlap.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["left", "right", "left_center_A", "right_center_A", "overlap"])
        for index, coefficient in enumerate(overlap):
            writer.writerow(
                [
                    names[index],
                    names[index + 1],
                    f"{centers[index]:.6f}",
                    f"{centers[index + 1]:.6f}",
                    f"{coefficient:.6f}",
                ]
            )

    with (output_dir / "window_offsets.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["window", "center_A", "offset_kcal_mol"])
        for name, center, offset in zip(names, centers, offsets):
            writer.writerow([name, f"{center:.6f}", f"{offset:.10f}"])

    with (output_dir / "wham_diagnostics.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "temperature_K",
                "bins",
                "tolerance_kcal_mol",
                "iterations",
                "residual_kcal_mol",
            ]
        )
        writer.writerow(
            [
                f"{TEMPERATURE_KELVIN:.2f}",
                PMF_BINS,
                f"{WHAM_TOLERANCE_KCAL_MOL:.3e}",
                iterations,
                f"{residual:.3e}",
            ]
        )

    return pmf


def plot_results(
    bin_centers: np.ndarray,
    pmf: np.ndarray,
    centers: np.ndarray,
    overlap: list[float],
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(10, 4))

    axes[0].plot(bin_centers, pmf)
    axes[0].set_xlabel("Terminal Cα distance (Å)")
    axes[0].set_ylabel("Relative PMF (kcal/mol)")

    pair_centers = 0.5 * (centers[:-1] + centers[1:])
    axes[1].bar(pair_centers, overlap, width=0.8)
    axes[1].set_xlabel("Neighboring-window midpoint (Å)")
    axes[1].set_ylabel("Histogram overlap")
    axes[1].set_ylim(0.0, 1.0)

    figure.tight_layout()
    plt.show()


def main() -> None:
    try:
        centers, forces, series, names = read_inputs(OUTPUT_DIR)
        edges = np.linspace(PMF_MIN_ANGSTROM, PMF_MAX_ANGSTROM, PMF_BINS + 1)
        result = solve_wham(
            centers,
            forces,
            series,
            TEMPERATURE_KELVIN,
            edges,
            WHAM_TOLERANCE_KCAL_MOL,
            WHAM_MAX_ITERATIONS,
        )
        bin_centers, probability, counts, offsets, iterations, residual = result
        overlap = overlap_coefficients(series)
        pmf = write_results(
            OUTPUT_DIR,
            bin_centers,
            probability,
            counts,
            offsets,
            centers,
            names,
            overlap,
            iterations,
            residual,
        )
    except (OSError, KeyError, ValueError) as error:
        raise SystemExit(f"WHAM 계산에 실패했습니다: {error}") from error

    print(f"WHAM이 {iterations} iterations에서 수렴했습니다: {OUTPUT_DIR}/pmf.tsv")
    plot_results(bin_centers, pmf, centers, overlap)


if __name__ == "__main__":
    main()
