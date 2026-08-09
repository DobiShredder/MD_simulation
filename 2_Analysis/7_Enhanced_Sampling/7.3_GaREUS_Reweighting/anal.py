#!/usr/bin/env python3
"""MBAR와 2차 cumulant expansion으로 GaREUS 1D PMF를 계산합니다."""

from __future__ import annotations

import csv
from importlib.metadata import version
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


TUTORIAL_DIR = Path.cwd()
OUTPUT_DIR = TUTORIAL_DIR / "output"

TEMPERATURE_KELVIN = 300.0
PMF_MIN_ANGSTROM = 5.0
PMF_MAX_ANGSTROM = 26.0
BIN_WIDTH_ANGSTROM = 0.2

GAS_CONSTANT_KCAL_MOL_K = 0.00198720425864083


def read_inputs(
    output_dir: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    summary_file = output_dir / "summary.tsv"
    if not summary_file.is_file():
        raise ValueError("./run.sh를 먼저 실행해야 합니다: output/summary.tsv")

    with summary_file.open(encoding="utf-8", newline="") as handle:
        states = list(csv.DictReader(handle, delimiter="\t"))

    centers = []
    forces = []
    sample_counts = []
    distances = []
    boosts = []

    for state in states:
        window = state["window"]
        path = output_dir / "series" / f"window_{window}.tsv"
        if not path.is_file():
            raise ValueError(f"window series를 찾을 수 없습니다: {path}")

        data = np.loadtxt(path, skiprows=1, usecols=(2, 3), ndmin=2)
        if data.shape[0] == 0 or not np.all(np.isfinite(data)):
            raise ValueError(f"window series가 비었거나 유효하지 않습니다: {path}")

        centers.append(float(state["center_A"]))
        forces.append(float(state["amber_rk_kcal_mol_A2"]))
        sample_counts.append(data.shape[0])
        distances.extend(data[:, 0])
        boosts.extend(data[:, 1])

    return (
        np.asarray(centers),
        np.asarray(forces),
        np.asarray(sample_counts, dtype=int),
        np.asarray(distances),
        np.asarray(boosts),
    )


def umbrella_weights(
    centers: np.ndarray,
    forces: np.ndarray,
    sample_counts: np.ndarray,
    distances: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    try:
        import pymbar
    except ImportError as error:
        raise ValueError(
            "PyMBAR가 필요합니다. conda install -c conda-forge 'pymbar>=4,<5'"
        ) from error

    beta = 1.0 / (GAS_CONSTANT_KCAL_MOL_K * TEMPERATURE_KELVIN)
    umbrella_energy = forces[:, None] * (distances[None, :] - centers[:, None]) ** 2
    reduced_energy = beta * umbrella_energy

    sampled_mbar = pymbar.MBAR(reduced_energy, sample_counts, verbose=False)
    overlap = np.asarray(sampled_mbar.compute_overlap()["matrix"], dtype=float)

    # 마지막 state는 umbrella bias가 없는 target이며 sample 수는 0입니다.
    reduced_energy_with_target = np.vstack(
        [reduced_energy, np.zeros(len(distances))]
    )
    counts_with_target = np.append(sample_counts, 0)
    target_mbar = pymbar.MBAR(
        reduced_energy_with_target,
        counts_with_target,
        verbose=False,
    )

    weights = np.asarray(target_mbar.W_nk[:, -1], dtype=float)
    weights /= weights.sum()
    return weights, overlap


def weighted_moments(values: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    normalized = weights / weights.sum()
    mean = float(np.sum(normalized * values))
    variance = float(np.sum(normalized * (values - mean) ** 2))
    return mean, variance


def calculate_pmf(
    distances: np.ndarray,
    boosts: np.ndarray,
    weights: np.ndarray,
) -> tuple[np.ndarray, list[dict[str, float]]]:
    edges = np.arange(
        PMF_MIN_ANGSTROM,
        PMF_MAX_ANGSTROM + BIN_WIDTH_ANGSTROM * 0.5,
        BIN_WIDTH_ANGSTROM,
    )
    bin_centers = 0.5 * (edges[:-1] + edges[1:])
    bin_index = np.digitize(distances, edges) - 1

    if np.any((bin_index < 0) | (bin_index >= len(bin_centers))):
        raise ValueError("PMF 범위 밖의 frame이 있습니다. PMF_MIN/MAX를 수정하십시오.")

    beta = 1.0 / (GAS_CONSTANT_KCAL_MOL_K * TEMPERATURE_KELVIN)
    rows = []
    log_reweighted_probability = np.full(len(bin_centers), -np.inf)
    mbar_probability = np.zeros(len(bin_centers))

    for index, center in enumerate(bin_centers):
        selected = bin_index == index
        count = int(np.sum(selected))
        if count == 0:
            rows.append({"center": center, "count": 0})
            continue

        bin_weights = weights[selected]
        bin_probability = float(bin_weights.sum())
        mean, variance = weighted_moments(boosts[selected], bin_weights)
        cumulant = beta * mean + 0.5 * beta * beta * variance
        effective_sample_size = float(bin_probability**2 / np.sum(bin_weights**2))

        mbar_probability[index] = bin_probability
        log_reweighted_probability[index] = np.log(bin_probability) + cumulant
        rows.append(
            {
                "center": center,
                "count": count,
                "mbar_probability": bin_probability,
                "boost_mean": mean,
                "boost_variance": variance,
                "effective_sample_size": effective_sample_size,
            }
        )

    occupied = np.isfinite(log_reweighted_probability)
    maximum = np.max(log_reweighted_probability[occupied])
    reweighted_probability = np.zeros(len(bin_centers))
    reweighted_probability[occupied] = np.exp(
        log_reweighted_probability[occupied] - maximum
    )
    reweighted_probability /= reweighted_probability.sum()

    mbar_probability /= mbar_probability.sum()
    for index, row in enumerate(rows):
        if row["count"] == 0:
            continue
        row["mbar_probability"] = mbar_probability[index]
        row["reweighted_probability"] = reweighted_probability[index]

    return bin_centers, rows


def write_outputs(
    output_dir: Path,
    rows: list[dict[str, float]],
    centers: np.ndarray,
    sample_counts: np.ndarray,
    distances: np.ndarray,
    boosts: np.ndarray,
    weights: np.ndarray,
    overlap: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    beta = 1.0 / (GAS_CONSTANT_KCAL_MOL_K * TEMPERATURE_KELVIN)
    mbar_pmf = np.full(len(rows), np.nan)
    reweighted_pmf = np.full(len(rows), np.nan)

    occupied = np.asarray([row["count"] > 0 for row in rows])
    mbar_values = np.asarray([row.get("mbar_probability", np.nan) for row in rows])
    reweighted_values = np.asarray(
        [row.get("reweighted_probability", np.nan) for row in rows]
    )
    mbar_pmf[occupied] = -np.log(mbar_values[occupied]) / beta
    reweighted_pmf[occupied] = -np.log(reweighted_values[occupied]) / beta
    mbar_pmf[occupied] -= np.min(mbar_pmf[occupied])
    reweighted_pmf[occupied] -= np.min(reweighted_pmf[occupied])

    with (output_dir / "pmf.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "distance_A",
                "count",
                "mbar_probability",
                "reweighted_probability",
                "mbar_pmf_kcal_mol",
                "reweighted_pmf_kcal_mol",
                "boost_mean_kcal_mol",
                "boost_variance_kcal2_mol2",
                "mbar_effective_sample_size",
            ]
        )
        for index, row in enumerate(rows):
            if row["count"] == 0:
                writer.writerow(
                    [f"{row['center']:.6f}", 0, 0, 0, "nan", "nan", "nan", "nan", 0]
                )
                continue

            writer.writerow(
                [
                    f"{row['center']:.6f}",
                    row["count"],
                    f"{row['mbar_probability']:.10e}",
                    f"{row['reweighted_probability']:.10e}",
                    f"{mbar_pmf[index]:.6f}",
                    f"{reweighted_pmf[index]:.6f}",
                    f"{row['boost_mean']:.6f}",
                    f"{row['boost_variance']:.6f}",
                    f"{row['effective_sample_size']:.3f}",
                ]
            )

    with (output_dir / "mbar_weights.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            ["window", "frame", "distance_A", "boost_kcal_mol", "mbar_weight"]
        )
        offset = 0
        for state_index, count in enumerate(sample_counts):
            for frame in range(count):
                sample = offset + frame
                writer.writerow(
                    [
                        f"{state_index:03d}",
                        frame + 1,
                        f"{distances[sample]:.8f}",
                        f"{boosts[sample]:.8f}",
                        f"{weights[sample]:.12e}",
                    ]
                )
            offset += count

    with (output_dir / "overlap_matrix.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["window"] + [f"{index:03d}" for index in range(len(centers))])
        for index, values in enumerate(overlap):
            writer.writerow([f"{index:03d}"] + [f"{value:.8f}" for value in values])

    total_ess = float(1.0 / np.sum(weights**2))
    with (output_dir / "mbar_diagnostics.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "pymbar_version",
                "frames",
                "weight_sum",
                "effective_sample_size",
                "maximum_weight",
            ]
        )
        writer.writerow(
            [
                version("pymbar"),
                len(weights),
                f"{weights.sum():.12f}",
                f"{total_ess:.3f}",
                f"{weights.max():.12e}",
            ]
        )

    bin_centers = np.asarray([row["center"] for row in rows])
    return bin_centers, mbar_pmf, reweighted_pmf


def plot_pmf(
    bin_centers: np.ndarray,
    mbar_pmf: np.ndarray,
    reweighted_pmf: np.ndarray,
) -> None:
    plt.plot(bin_centers, mbar_pmf, label="REUS bias removed")
    plt.plot(bin_centers, reweighted_pmf, label="REUS + GaMD biases removed")
    plt.xlabel("Terminal Cα distance (Å)")
    plt.ylabel("Relative PMF (kcal/mol)")
    plt.legend()
    plt.tight_layout()
    plt.show()


def main() -> None:
    try:
        centers, forces, sample_counts, distances, boosts = read_inputs(OUTPUT_DIR)
        weights, overlap = umbrella_weights(centers, forces, sample_counts, distances)
        _, rows = calculate_pmf(distances, boosts, weights)
        bin_centers, mbar_pmf, reweighted_pmf = write_outputs(
            OUTPUT_DIR,
            rows,
            centers,
            sample_counts,
            distances,
            boosts,
            weights,
            overlap,
        )
    except (OSError, KeyError, ValueError) as error:
        raise SystemExit(f"GaREUS reweighting에 실패했습니다: {error}") from error

    print(f"GaREUS 1D PMF를 계산했습니다: {OUTPUT_DIR}/pmf.tsv")
    plot_pmf(bin_centers, mbar_pmf, reweighted_pmf)


if __name__ == "__main__":
    main()
