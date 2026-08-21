#!/usr/bin/env python3
"""Generate T-REMD, REST2, or REST3 states from config and topology."""

from __future__ import annotations

import argparse
import math
import re
import secrets
import sys
from pathlib import Path

import parmed

sys.dont_write_bytecode = True
sys.path.insert(0, "../../common")
from config_utils import (  # noqa: E402
    load_config,
    positive_float,
    positive_int,
    section,
    string_value,
)
from temperature_ladder import LadderRow, generate_temperature_ladder  # noqa: E402

WATER_NAMES = {"WAT", "HOH", "TIP3", "TIP3P", "OPC"}
ION_NAMES = {
    "NA", "NA+", "SOD", "K", "K+", "POT", "CL", "CL-", "CLA",
    "CA", "CA2", "MG", "MG2", "ZN", "ZN2",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate replica temperatures and REST scaling factors from a topology."
    )
    parser.add_argument(
        "method",
        choices=("remd", "rest2", "rest3"),
        help="Replica-exchange method that determines atom counting and state columns",
    )
    parser.add_argument("config", type=Path, help="TOML configuration file")
    parser.add_argument("topology", type=Path, help="AMBER topology used to count atoms")
    parser.add_argument("output", type=Path, help="Output states.tsv file")
    return parser.parse_args()


def count_system(topology_path: Path) -> dict[str, int]:
    topology = parmed.load_file(str(topology_path))
    counts = {
        "total_atoms": len(topology.atoms),
        "solute_atoms": 0,
        "water_molecules": 0,
        "water_atoms": 0,
        "ion_atoms": 0,
    }
    for residue in topology.residues:
        name = residue.name.upper()
        atoms = len(residue.atoms)
        if name in WATER_NAMES:
            counts["water_molecules"] += 1
            counts["water_atoms"] += atoms
        elif name in ION_NAMES:
            counts["ion_atoms"] += atoms
        else:
            counts["solute_atoms"] += atoms
    if counts["solute_atoms"] == 0 or counts["water_molecules"] == 0:
        raise ValueError("topology must contain solute atoms and explicit water")
    return counts


def read_number_list(path: Path, label: str) -> list[float]:
    if not path.is_file():
        raise ValueError(f"{label} file not found: {path}")
    parts: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts.extend(re.split(r"[,;|\s]+", line.split("#", 1)[0].strip()))
    try:
        values = [float(part) for part in parts if part]
    except ValueError as error:
        raise ValueError(f"{label} file contains a nonnumeric value: {path}") from error
    return values


def read_temperatures(path: Path) -> list[float]:
    values = read_number_list(path, "temperature")
    if len(values) < 2 or values != sorted(set(values)) or values[0] <= 0:
        raise ValueError("temperatures must contain at least two unique increasing values")
    return values


def state_seeds(value: object, count: int) -> list[int]:
    if value == "random":
        seeds: set[int] = set()
        while len(seeds) < count:
            seeds.add(secrets.randbelow(900_000_000) + 1)
        return list(seeds)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("random_seed must be 'random' or a positive integer")
    return [value + 7919 * index for index in range(count)]


def kappa_values(config: dict[str, object], temperatures: list[float]) -> list[float]:
    values = section(config, "rest3_kappa")
    mode = string_value(values, "mode")
    if mode == "file":
        path = Path(string_value(values, "file"))
        parsed = read_number_list(path, "kappa")
        if len(parsed) != len(temperatures):
            raise ValueError("kappa and temperature lists must have the same length")
        if any(value < 1.0 for value in parsed):
            raise ValueError("kappa values must be 1.0 or greater")
        return parsed
    if mode != "linear":
        raise ValueError("rest3_kappa.mode must be linear or file")
    onset = positive_float(values, "onset_temperature")
    maximum_temperature = positive_float(values, "maximum_temperature")
    maximum_kappa = positive_float(values, "maximum_kappa")
    if maximum_temperature <= onset or maximum_kappa < 1.0:
        raise ValueError("invalid linear kappa range")
    result = []
    for temperature in temperatures:
        if temperature <= onset:
            result.append(1.0)
        else:
            fraction = min(1.0, (temperature - onset) / (maximum_temperature - onset))
            result.append(1.0 + fraction * (maximum_kappa - 1.0))
    return result


def main() -> None:
    args = parse_arguments()
    try:
        config = load_config(args.config)
        exchange = section(config, "replica_exchange")
        mode = string_value(exchange, "temperature_mode")
        counts = count_system(args.topology)

        diagnostic_rows: list[LadderRow] = []
        if mode == "auto":
            minimum = positive_float(exchange, "minimum_temperature")
            maximum = positive_float(exchange, "maximum_temperature")
            target = positive_float(exchange, "target_exchange_probability")
            tolerance = positive_float(exchange, "generator_tolerance")
            if args.method == "remd":
                predictor_atoms = counts["solute_atoms"] + counts["ion_atoms"]
                predictor_waters = counts["water_molecules"]
            else:
                predictor_atoms = counts["solute_atoms"]
                predictor_waters = 0
            diagnostic_rows = generate_temperature_ladder(
                protein_atoms=predictor_atoms,
                water_molecules=predictor_waters,
                minimum_temperature=minimum,
                maximum_temperature=maximum,
                target_probability=target,
                tolerance=tolerance,
            )
            temperatures = [row.temperature for row in diagnostic_rows]
        elif mode == "file":
            temperatures = read_temperatures(
                Path(string_value(exchange, "temperature_file"))
            )
            predictor_atoms = (
                counts["solute_atoms"] + counts["ion_atoms"]
                if args.method == "remd"
                else counts["solute_atoms"]
            )
            predictor_waters = counts["water_molecules"] if args.method == "remd" else 0
        else:
            raise ValueError("temperature_mode must be auto or file")

        base_temperature = positive_float(section(config, "run"), "temperature")
        if not math.isclose(temperatures[0], base_temperature, abs_tol=1.0e-6):
            raise ValueError(
                "the first state temperature must equal run.temperature"
            )

        seeds = state_seeds(exchange.get("random_seed"), len(temperatures))
        kappas = kappa_values(config, temperatures) if args.method == "rest3" else None
        positive_int(exchange, "exchange_interval_steps")
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None

    args.output.mkdir(parents=True, exist_ok=True)
    if args.method == "remd":
        lines = ["replica\ttemperature_K\tseed"]
        for index, (temperature, seed) in enumerate(zip(temperatures, seeds)):
            lines.append(f"{index:03d}\t{temperature:.8f}\t{seed}")
    else:
        header = "replica\teffective_temperature_K\tlambda_pp\tlambda_pw"
        if kappas is not None:
            header += "\tkappa"
        header += "\tseed"
        lines = [header]
        for index, (temperature, seed) in enumerate(zip(temperatures, seeds)):
            lambda_pp = base_temperature / temperature
            fields = [
                f"{index:03d}", f"{temperature:.8f}", f"{lambda_pp:.8f}",
                f"{math.sqrt(lambda_pp):.8f}",
            ]
            if kappas is not None:
                fields.append(f"{kappas[index]:.6f}")
            fields.append(str(seed))
            lines.append("\t".join(fields))
    (args.output / "states.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    count_lines = ["quantity\tvalue"]
    count_lines.extend(f"{key}\t{value}" for key, value in counts.items())
    count_lines.extend(
        [
            f"predictor_atoms\t{predictor_atoms}",
            f"predictor_water_molecules\t{predictor_waters}",
        ]
    )
    (args.output / "system_counts.tsv").write_text(
        "\n".join(count_lines) + "\n", encoding="utf-8"
    )

    if diagnostic_rows:
        diagnostic = [
            "replica\ttemperature_K\tmean_energy_kJ_mol\tsigma_energy_kJ_mol\t"
            "pair_mean_kJ_mol\tpair_sigma_kJ_mol\tpredicted_pair_probability"
        ]
        for index, row in enumerate(diagnostic_rows):
            optional = (
                ["", "", ""]
                if row.predicted_probability is None
                else [
                    f"{row.pair_mean_kj_mol:.8f}",
                    f"{row.pair_sigma_kj_mol:.8f}",
                    f"{row.predicted_probability:.8f}",
                ]
            )
            diagnostic.append(
                "\t".join(
                    [
                        f"{index:03d}", f"{row.temperature:.8f}",
                        f"{row.mean_energy_kj_mol:.8f}",
                        f"{row.sigma_energy_kj_mol:.8f}", *optional,
                    ]
                )
            )
        (args.output / "temperature_generator.tsv").write_text(
            "\n".join(diagnostic) + "\n", encoding="utf-8"
        )

    print(
        f"Generated {len(temperatures)} {args.method.upper()} states: "
        f"{temperatures[0]:.2f}-{temperatures[-1]:.2f} K"
    )


if __name__ == "__main__":
    main()
