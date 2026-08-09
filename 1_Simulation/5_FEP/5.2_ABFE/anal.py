#!/usr/bin/env python3
"""ABFE leg를 적분하고 standard-state 및 leading PME correction을 조합합니다."""

from __future__ import annotations

import csv
import math
import os
import re
from pathlib import Path

import parmed


ROOT = Path(__file__).resolve().parent
WORK = Path(os.environ.get("WORK_DIR", ROOT / "work"))
TEMPERATURE_K = 300.0
GAS_CONSTANT = 0.00198720425864083
STANDARD_VOLUME_A3 = 1660.539
DVDL_PATTERN = re.compile(r"DV/DL\s*=\s*([-+0-9.Ee]+)")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def output_values(directory: Path, pattern: re.Pattern[str]) -> list[float]:
    values: list[float] = []
    for segment in (1, 2):
        path = directory / f"production.{segment:03d}.out"
        if not path.is_file():
            raise SystemExit(f"production output을 찾을 수 없습니다: {path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        values.extend(float(match.group(1)) for match in pattern.finditer(text))
    return values


def vector(a: object, b: object) -> list[float]:
    return [float(b[index] - a[index]) for index in range(3)]


def dot(a: list[float], b: list[float]) -> float:
    return sum(left * right for left, right in zip(a, b))


def cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def norm(a: list[float]) -> float:
    return math.sqrt(dot(a, a))


def coordinate_value(kind: str, points: list[object]) -> float:
    if kind == "distance":
        return norm(vector(points[0], points[1]))
    if kind.startswith("angle"):
        left, right = vector(points[1], points[0]), vector(points[1], points[2])
        cosine = max(-1.0, min(1.0, dot(left, right) / (norm(left) * norm(right))))
        return math.degrees(math.acos(cosine))
    first, middle, last = vector(points[1], points[0]), vector(points[1], points[2]), vector(points[2], points[3])
    normal1, normal2 = cross(first, middle), cross(middle, last)
    return math.degrees(math.atan2(dot(cross(normal1, normal2), middle) / norm(middle), dot(normal1, normal2)))


def periodic_difference(value: float, reference: float) -> float:
    return (value - reference + 180.0) % 360.0 - 180.0


def restraint_derivatives(directory: Path, restraints: list[dict[str, str]]) -> list[float]:
    values: list[float] = []
    for segment in (1, 2):
        trajectory_path = directory / f"production.{segment:03d}.nc"
        if not trajectory_path.is_file():
            raise SystemExit(f"restraint trajectory를 찾을 수 없습니다: {trajectory_path}")
        trajectory = parmed.amber.NetCDFTraj.open_old(str(trajectory_path))
        for frame in trajectory.coordinates:
            energy = 0.0
            for restraint in restraints:
                kind = restraint["restraint"]
                indices = [int(value) - 1 for value in restraint["atom_indices"].split(",")]
                points = [frame[index] for index in indices]
                current = coordinate_value(kind, points)
                reference = float(restraint["reference"])
                force = float(restraint["force_constant"])
                if kind == "distance":
                    displacement = current - reference
                else:
                    displacement = math.radians(periodic_difference(current, reference))
                energy += force * displacement * displacement
            values.append(energy)
    return values


def mean_and_error(values: list[float]) -> tuple[float, float]:
    if not values:
        raise SystemExit("분석할 energy record가 없습니다.")
    mean = sum(values) / len(values)
    if len(values) == 1:
        return mean, math.nan
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return mean, math.sqrt(variance / len(values))


def integrate(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for left, right in zip(points, points[1:]):
        total += (right[0] - left[0]) * (left[1] + right[1]) / 2.0
    return total


def standard_state_correction(restraints: list[dict[str, str]]) -> float:
    references = {row["restraint"]: float(row["reference"]) for row in restraints}
    amber_forces = {
        row["restraint"]: float(row["force_constant"])
        for row in restraints
    }
    spring_constants = {
        restraint: 2.0 * force
        for restraint, force in amber_forces.items()
    }
    distance_ref = references["distance"]
    angle_a = math.radians(references["angle_a"])
    angle_b = math.radians(references["angle_b"])
    force_product = math.prod(spring_constants.values())
    thermal = 2.0 * math.pi * GAS_CONSTANT * TEMPERATURE_K
    ratio = (
        8.0 * math.pi**2 * STANDARD_VOLUME_A3 * math.sqrt(force_product)
        / (distance_ref**2 * math.sin(angle_a) * math.sin(angle_b) * thermal**3)
    )
    return -GAS_CONSTANT * TEMPERATURE_K * math.log(ratio)


def box_length(path: Path) -> float:
    restart = parmed.load_file(str(path))
    if restart.box is None:
        raise SystemExit(f"Periodic box 정보를 읽지 못했습니다: {path}")
    volume = float(restart.box[0] * restart.box[1] * restart.box[2])
    return volume ** (1.0 / 3.0)


def leading_charge_correction(length_angstrom: float) -> float:
    q = 1.0
    ewald_constant = -2.837297
    coulomb = 332.06371
    water_dielectric = 78.5
    return -(q * q * ewald_constant * coulomb / (2.0 * length_angstrom)) * (1.0 - 1.0 / water_dielectric)


def combine_binding_free_energy(
    contributions: dict[str, float],
    standard_state: float,
    finite_size: float,
) -> tuple[float, float]:
    raw_binding = (
        contributions["solvent_charge"]
        + contributions["solvent_vdw"]
        - contributions["complex_charge"]
        - contributions["complex_vdw"]
        - contributions["restraint"]
        + standard_state
    )
    return raw_binding, raw_binding + finite_size


def main() -> None:
    profiles: dict[str, list[tuple[float, float]]] = {}
    summary: list[list[str]] = []
    restraints = read_tsv(WORK / "restraints.tsv")

    for state in read_tsv(WORK / "states.tsv"):
        stage = state["stage"]
        lambda_value = float(state["lambda"])
        directory = Path(state["directory"])
        if stage == "restraint":
            derivative_values = restraint_derivatives(directory, restraints)
        else:
            derivative_values = output_values(directory, DVDL_PATTERN)
        mean, error = mean_and_error(derivative_values)
        profiles.setdefault(stage, []).append((lambda_value, mean))
        summary.append([stage, state["window"], state["lambda"], str(len(derivative_values)), f"{mean:.8f}", f"{error:.8f}"])

    with (WORK / "window_summary.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["stage", "window", "lambda", "samples", "mean_derivative_kcal_mol", "sem_kcal_mol"])
        writer.writerows(summary)

    contributions = {stage: integrate(sorted(points)) for stage, points in profiles.items()}
    standard = standard_state_correction(restraints)
    complex_charge = leading_charge_correction(box_length(WORK / "build" / "complex.rst7"))
    solvent_charge = leading_charge_correction(box_length(WORK / "build" / "solvent.rst7"))
    finite_size = solvent_charge - complex_charge
    raw_binding, corrected_binding = combine_binding_free_energy(
        contributions,
        standard,
        finite_size,
    )

    with (WORK / "free_energy.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["quantity", "value_kcal_mol"])
        for stage in ("restraint", "complex_charge", "complex_vdw", "solvent_charge", "solvent_vdw"):
            writer.writerow([stage, f"{contributions[stage]:.8f}"])
        writer.writerow([
            "bound_restraint_cycle_contribution",
            f"{-contributions['restraint']:.8f}",
        ])
        writer.writerow(["standard_state_correction", f"{standard:.8f}"])
        writer.writerow(["leading_pme_net_charge_correction", f"{finite_size:.8f}"])
        writer.writerow(["raw_standard_binding_delta_g", f"{raw_binding:.8f}"])
        writer.writerow(["corrected_standard_binding_delta_g", f"{corrected_binding:.8f}"])

    print(f"ABFE TI 결과: {WORK / 'free_energy.tsv'}")


if __name__ == "__main__":
    main()
