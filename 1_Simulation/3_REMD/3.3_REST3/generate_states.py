#!/usr/bin/env python3
"""Generate a REST3 states.tsv file from temperature and kappa lists."""

import argparse
import csv
import math
import re
import sys
from pathlib import Path


REFERENCE_TEMPERATURE_K = 300.0
SEED_BASE = 410001
SEED_STRIDE = 7919
SEPARATORS = re.compile(r"[,;|\s]+")


def read_values(path, value_name):
    values = []

    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        content = line.split("#", 1)[0].strip()
        if not content:
            continue

        for token in SEPARATORS.split(content):
            if not token:
                continue
            try:
                value = float(token)
            except ValueError as error:
                raise ValueError(
                    f"{path}: line {line_number}: expected {value_name}, found {token!r}"
                ) from error
            if not math.isfinite(value):
                raise ValueError(
                    f"{path}: line {line_number}: {value_name} must be finite, found {token!r}"
                )
            values.append(value)

    return values


def read_schedule(temperature_path, kappa_path):
    temperatures = read_values(temperature_path, "a temperature")
    kappas = read_values(kappa_path, "a kappa value")

    if len(temperatures) < 2:
        raise ValueError(f"{temperature_path}: at least two temperatures are required")
    if len(temperatures) > 1000:
        raise ValueError(f"{temperature_path}: at most 1000 temperatures are supported")
    if len(kappas) != len(temperatures):
        raise ValueError(
            f"temperature/kappa count mismatch: {len(temperatures)} temperatures and "
            f"{len(kappas)} kappa values"
        )
    if not math.isclose(temperatures[0], REFERENCE_TEMPERATURE_K, abs_tol=1.0e-6):
        raise ValueError(f"{temperature_path}: the first temperature must be 300 K")

    for index in range(1, len(temperatures)):
        if temperatures[index] <= temperatures[index - 1]:
            raise ValueError(
                f"{temperature_path}: temperatures must increase strictly: "
                f"{temperatures[index - 1]} then {temperatures[index]}"
            )

    for index, kappa in enumerate(kappas):
        if kappa <= 0.0:
            raise ValueError(f"{kappa_path}: kappa value {index + 1} must be greater than 0")
    if not math.isclose(kappas[0], 1.0, abs_tol=1.0e-6):
        raise ValueError(f"{kappa_path}: the first kappa value must be 1")

    return temperatures, kappas


def write_states(temperatures, kappas, handle):
    writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
    writer.writerow(
        [
            "replica",
            "effective_temperature_K",
            "lambda_pp",
            "lambda_pw",
            "kappa",
            "seed",
        ]
    )

    for replica_index, (temperature, kappa) in enumerate(zip(temperatures, kappas)):
        lambda_pp = REFERENCE_TEMPERATURE_K / temperature
        lambda_pw = math.sqrt(lambda_pp)
        seed = SEED_BASE + SEED_STRIDE * replica_index
        writer.writerow(
            [
                f"{replica_index:03d}",
                f"{temperature:.3f}",
                f"{lambda_pp:.8f}",
                f"{lambda_pw:.8f}",
                f"{kappa:.3f}",
                seed,
            ]
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("temperatures", type=Path, help="effective-temperature input file")
    parser.add_argument("kappas", type=Path, help="REST3 kappa input file")
    parser.add_argument("output", nargs="?", type=Path, help="output states.tsv file")
    parser.add_argument(
        "--count", action="store_true", help="print only the number of schedule states"
    )
    args = parser.parse_args()

    try:
        temperatures, kappas = read_schedule(args.temperatures, args.kappas)
        if args.count:
            if args.output is not None:
                raise ValueError("an output file cannot be used with --count")
            print(len(temperatures))
            return

        if args.output is None:
            write_states(temperatures, kappas, sys.stdout)
        else:
            with args.output.open("w", encoding="utf-8", newline="") as handle:
                write_states(temperatures, kappas, handle)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
