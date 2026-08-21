#!/usr/bin/env python3
"""Generate an initial replica-exchange temperature ladder.

This is a Python implementation of the MIT-licensed temperature predictor by
Patriksson and van der Spoel. The empirical model was calibrated for
temperature REMD with OPLS/AA and GROMACS; REST ladders remain an approximation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

A0 = -59.2194
A1 = 0.07594
B0 = -22.8396
B1 = 0.01347
D0 = 1.1677
D1 = 0.002976
KB = 0.008314
MAX_ITERATIONS = 100


@dataclass(frozen=True)
class LadderRow:
    temperature_kelvin: float
    mean_energy_kj_mol: float
    sigma_energy_kj_mol: float
    pair_mean_kj_mol: float | None
    pair_sigma_kj_mol: float | None
    predicted_probability: float | None


def _numerical_integral(mean: float, sigma: float, coefficient: float) -> float:
    upper = mean + 5.0 * sigma
    step = upper / 100.0
    total = 0.0
    for index in range(100):
        value = (index + 0.5) * step
        exponent = -coefficient * value - (value - mean) ** 2 / (2.0 * sigma**2)
        total += math.exp(exponent)
    return step * total / (sigma * math.sqrt(2.0 * math.pi))


def _predictor_erfc(value: float) -> float:
    """Reproduce the Abramowitz-Stegun approximation used by the source."""
    sign = -1.0 if value < 0.0 else 1.0
    value = abs(value)
    scale = 1.0 / (1.0 + 0.3275911 * value)
    polynomial = (
        (((((1.061405429 * scale - 1.453152027) * scale) + 1.421413741)
          * scale - 0.284496736) * scale + 0.254829592)
        * scale
        * math.exp(-(value**2))
    )
    return sign * polynomial


def _pair_probability(
    first_temperature: float,
    second_temperature: float,
    protein_atoms: int,
    water_molecules: int,
    degrees_of_freedom: int,
    flexible_energy: float,
    protein_atoms_for_energy: int,
) -> tuple[float, float, float]:
    pair_mean = (second_temperature - first_temperature) * (
        A1 * water_molecules + B1 * protein_atoms_for_energy - flexible_energy
    )
    coefficient = (1.0 / KB) * (
        (1.0 / first_temperature) - (1.0 / second_temperature)
    )
    variance = degrees_of_freedom * (
        D1**2 * (first_temperature**2 + second_temperature**2)
        + 2.0 * D1 * D0 * (first_temperature + second_temperature)
        + 2.0 * D0**2
    )
    pair_sigma = math.sqrt(variance)
    integral_1 = 0.5 * _predictor_erfc(
        pair_mean / (pair_sigma * math.sqrt(2.0))
    )
    integral_2 = _numerical_integral(pair_mean, pair_sigma, coefficient)
    return integral_1 + integral_2, pair_mean, pair_sigma


def generate_temperature_ladder(
    *,
    protein_atoms: int,
    water_molecules: int,
    minimum_kelvin: float,
    maximum_kelvin: float,
    target_probability: float,
    tolerance: float,
    protein_constraint_mode: str = "h-bonds",
    water_constraints_per_molecule: int = 3,
) -> list[LadderRow]:
    if protein_atoms <= 0:
        raise ValueError("protein_atoms must be positive")
    if water_molecules < 0:
        raise ValueError("water_molecules must be zero or greater")
    if minimum_kelvin <= 0 or maximum_kelvin <= minimum_kelvin:
        raise ValueError("temperature range must satisfy 0 < minimum < maximum")
    if not 0.0 < target_probability < 1.0:
        raise ValueError("target_probability must be between zero and one")
    if tolerance <= 0:
        raise ValueError("tolerance must be greater than zero")
    if water_constraints_per_molecule not in {0, 1, 2, 3}:
        raise ValueError("water_constraints_per_molecule must be between 0 and 3")

    hydrogen_atoms = round(protein_atoms * 0.5134)
    if protein_constraint_mode == "none":
        protein_constraints = 0
    elif protein_constraint_mode == "h-bonds":
        protein_constraints = hydrogen_atoms
    elif protein_constraint_mode == "all-bonds":
        protein_constraints = protein_atoms
    else:
        raise ValueError("protein_constraint_mode must be none, h-bonds, or all-bonds")

    degrees_of_freedom = (
        (9 - water_constraints_per_molecule) * water_molecules
        + 3 * protein_atoms
        - protein_constraints
    )
    if degrees_of_freedom <= 0:
        raise ValueError("derived degrees of freedom must be positive")
    flexible_energy = 0.5 * KB * (
        protein_constraints + water_constraints_per_molecule * water_molecules
    )

    temperatures = [minimum_kelvin]
    pair_values: list[tuple[float, float, float]] = []
    while temperatures[-1] < maximum_kelvin:
        first = temperatures[-1]
        second = min(first + 1.0, maximum_kelvin)
        low = first
        high = maximum_kelvin
        forward = True
        probability = 0.0
        pair_mean = 0.0
        pair_sigma = 0.0

        for _ in range(MAX_ITERATIONS):
            probability, pair_mean, pair_sigma = _pair_probability(
                first,
                second,
                protein_atoms,
                water_molecules,
                degrees_of_freedom,
                flexible_energy,
                protein_atoms,
            )
            if abs(target_probability - probability) <= tolerance:
                break
            if probability > target_probability:
                if forward:
                    second += 1.0
                else:
                    low = second
                    second = low + (high - low) / 2.0
                second = min(second, maximum_kelvin)
            else:
                if forward:
                    forward = False
                    low = second - 1.0
                high = second
                second = low + (high - low) / 2.0

        if second <= first:
            raise ValueError("temperature generator did not advance")
        temperatures.append(second)
        pair_values.append((probability, pair_mean, pair_sigma))

    rows: list[LadderRow] = []
    for index, temperature in enumerate(temperatures):
        sigma = math.sqrt(degrees_of_freedom) * (D0 + D1 * temperature)
        mean = (
            (A0 + A1 * temperature) * water_molecules
            + (B0 + B1 * temperature) * protein_atoms
            - temperature * flexible_energy
        )
        if index == 0:
            pair_probability = pair_mean = pair_sigma = None
        else:
            pair_probability, pair_mean, pair_sigma = pair_values[index - 1]
        rows.append(
            LadderRow(
                temperature,
                mean,
                sigma,
                pair_mean,
                pair_sigma,
                pair_probability,
            )
        )
    return rows
