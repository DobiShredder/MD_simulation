#!/usr/bin/env python3
"""MMPBSA.py energy와 residue decomposition을 요약한다."""

from __future__ import annotations

import csv
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
except ModuleNotFoundError as error:
    raise SystemExit("ambertools26 환경에 NumPy와 matplotlib을 설치하세요.") from error


def model_name(line: str) -> str | None:
    lower = line.lower()
    if "generalized born" in lower:
        return "GB"
    if "poisson boltzmann" in lower:
        return "PB"
    return None


def read_energy(path: Path) -> dict[str, tuple[list[str], np.ndarray]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    datasets: dict[str, tuple[list[str], np.ndarray]] = {}
    model: str | None = None
    index = 0

    while index < len(lines):
        detected = model_name(lines[index])
        if detected is not None:
            model = detected

        if lines[index].strip() == "DELTA Energy Terms":
            if model is None:
                raise ValueError("Energy model 이름을 찾지 못했습니다.")
            header = next(csv.reader([lines[index + 1]]))
            rows: list[list[float]] = []
            index += 2
            while index < len(lines) and lines[index].strip():
                rows.append([float(value) for value in next(csv.reader([lines[index]]))])
                index += 1
            datasets[model] = (header, np.asarray(rows, dtype=float))
        index += 1

    if not datasets:
        raise ValueError(f"DELTA Energy Terms가 없습니다: {path}")
    return datasets


def read_decomposition(path: Path) -> dict[str, list[tuple[str, float]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, list[tuple[str, float]]] = {}
    model: str | None = None
    index = 0

    while index < len(lines):
        detected = model_name(lines[index])
        if detected is not None:
            model = detected

        if lines[index].strip() == "DELTAS:":
            if model is None:
                raise ValueError("Decomposition model 이름을 찾지 못했습니다.")
            index += 1
            while index < len(lines) and not lines[index].startswith("Frame #"):
                index += 1
            index += 1
            rows: list[tuple[str, float]] = []
            while index < len(lines) and lines[index].strip():
                fields = next(csv.reader([lines[index]]))
                rows.append((fields[1].strip(), float(fields[-1])))
                index += 1
            values[model] = rows
        index += 1

    if not values:
        raise ValueError(f"DELTA decomposition이 없습니다: {path}")
    return values


def write_energy_outputs(
    output_dir: Path, datasets: dict[str, tuple[list[str], np.ndarray]]
) -> None:
    summary = ["model\tterm\tmean\tstandard_deviation\tframes"]
    running = ["model\tframe\trunning_mean_delta_total"]
    blocks = ["model\tblock\tstart_frame\tend_frame\tmean_delta_total"]

    for model, (header, data) in datasets.items():
        for column, term in enumerate(header[1:], start=1):
            standard_deviation = np.std(data[:, column], ddof=1)
            summary.append(
                f"{model}\t{term}\t{np.mean(data[:, column]):.8f}\t"
                f"{standard_deviation:.8f}\t{len(data)}"
            )

        total_column = header.index("DELTA TOTAL")
        total = data[:, total_column]
        cumulative = np.cumsum(total) / np.arange(1, len(total) + 1)
        for frame, value in zip(data[:, 0], cumulative, strict=True):
            running.append(f"{model}\t{frame:g}\t{value:.8f}")

        for block_number, indices in enumerate(np.array_split(np.arange(len(data)), 5), start=1):
            if len(indices) == 0:
                continue
            blocks.append(
                f"{model}\t{block_number}\t{data[indices[0], 0]:g}\t"
                f"{data[indices[-1], 0]:g}\t{np.mean(total[indices]):.8f}"
            )

    (output_dir / "energy_summary.tsv").write_text(
        "\n".join(summary) + "\n", encoding="utf-8"
    )
    (output_dir / "running_mean.tsv").write_text(
        "\n".join(running) + "\n", encoding="utf-8"
    )
    (output_dir / "block_summary.tsv").write_text(
        "\n".join(blocks) + "\n", encoding="utf-8"
    )


def write_decomposition(
    output_dir: Path, datasets: dict[str, list[tuple[str, float]]]
) -> None:
    output = ["model\tresidue\tmean_total\tstandard_deviation\tframes"]

    for model, rows in datasets.items():
        grouped: dict[str, list[float]] = {}
        for residue, value in rows:
            grouped.setdefault(residue, []).append(value)
        ordered = sorted(
            grouped.items(),
            key=lambda item: abs(float(np.mean(item[1]))),
            reverse=True,
        )
        for residue, values in ordered:
            deviation = np.std(values, ddof=1) if len(values) > 1 else 0.0
            output.append(
                f"{model}\t{residue}\t{np.mean(values):.8f}\t"
                f"{deviation:.8f}\t{len(values)}"
            )

    (output_dir / "decomposition_summary.tsv").write_text(
        "\n".join(output) + "\n", encoding="utf-8"
    )


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    energy = read_energy(output_dir / "energy.csv")
    decomposition = read_decomposition(output_dir / "decomposition.csv")
    write_energy_outputs(output_dir, energy)
    write_decomposition(output_dir, decomposition)

    figure, axis = plt.subplots(figsize=(8, 4.5))
    for model, (header, data) in energy.items():
        total = data[:, header.index("DELTA TOTAL")]
        cumulative = np.cumsum(total) / np.arange(1, len(total) + 1)
        axis.plot(data[:, 0], cumulative, label=model)
    axis.set_xlabel("MMPBSA frame")
    axis.set_ylabel("Running mean ΔTOTAL (kcal/mol)")
    axis.legend()
    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

