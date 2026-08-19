#!/usr/bin/env python3
"""Generate a REST2 states.tsv file from an effective-temperature list."""

import argparse
import csv
import math
import re
import sys
from pathlib import Path


REFERENCE_TEMPERATURE_K = 300.0
SEED_BASE = 310001
SEED_STRIDE = 7919
SEPARATORS = re.compile(r"[,;|\s]+")


def read_temperatures(path):
    temperatures = []

    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        content = line.split("#", 1)[0].strip()
        if not content:
            continue

        for token in SEPARATORS.split(content):
            if not token:
                continue
            try:
                temperature = float(token)
            except ValueError as error:
                raise ValueError(
                    f"{path}: line {line_number}: expected a temperature, found {token!r}"
                ) from error
            if not math.isfinite(temperature):
                raise ValueError(
                    f"{path}: line {line_number}: temperature must be finite, found {token!r}"
                )
            temperatures.append(temperature)

    if len(temperatures) < 2:
        raise ValueError(f"{path}: at least two temperatures are required")
    if len(temperatures) > 1000:
        raise ValueError(f"{path}: at most 1000 temperatures are supported")
    if not math.isclose(temperatures[0], REFERENCE_TEMPERATURE_K, abs_tol=1.0e-6):
        raise ValueError(f"{path}: the first temperature must be 300 K")

    for index in range(1, len(temperatures)):
        if temperatures[index] <= temperatures[index - 1]:
            raise ValueError(
                f"{path}: temperatures must increase strictly: "
                f"{temperatures[index - 1]} then {temperatures[index]}"
            )

    return temperatures


def write_states(temperatures, handle):
    writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
    writer.writerow(
        ["replica", "effective_temperature_K", "lambda_pp", "lambda_pw", "seed"]
    )

    for replica_index, temperature in enumerate(temperatures):
        lambda_pp = REFERENCE_TEMPERATURE_K / temperature
        lambda_pw = math.sqrt(lambda_pp)
        seed = SEED_BASE + SEED_STRIDE * replica_index
        writer.writerow(
            [
                f"{replica_index:03d}",
                f"{temperature:.3f}",
                f"{lambda_pp:.8f}",
                f"{lambda_pw:.8f}",
                seed,
            ]
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "temperatures", type=Path, help="effective-temperature input file"
    )
    parser.add_argument("output", nargs="?", type=Path, help="output states.tsv file")
    parser.add_argument(
        "--count", action="store_true", help="print only the number of temperature states"
    )
    args = parser.parse_args()

    try:
        temperatures = read_temperatures(args.temperatures)
        if args.count:
            if args.output is not None:
                raise ValueError("an output file cannot be used with --count")
            print(len(temperatures))
            return

        if args.output is None:
            write_states(temperatures, sys.stdout)
        else:
            with args.output.open("w", encoding="utf-8", newline="") as handle:
                write_states(temperatures, handle)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
