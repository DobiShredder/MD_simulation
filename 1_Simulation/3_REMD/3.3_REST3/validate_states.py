#!/usr/bin/env python3
"""Validate the temperature and kappa schedule used to build REST3 replicas."""

import argparse
import csv
import re
from pathlib import Path


HEADER = ["replica", "effective_temperature_K", "lambda_pp", "lambda_pw", "kappa", "seed"]
DECIMAL = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
REPLICA = re.compile(r"^[0-9]{3}$")
POSITIVE_INTEGER = re.compile(r"^[0-9]+$")


def fail(path, row_number, column, message):
    raise ValueError(f"{path}: row {row_number}, column {column}: {message}")


def parse_decimal(path, row_number, column, value):
    if not DECIMAL.fullmatch(value):
        fail(path, row_number, column, f"expected a non-negative decimal, found {value!r}")
    return float(value)


def validate(path):
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))

    if not rows:
        raise ValueError(f"{path}: state table is empty")
    if rows[0] != HEADER:
        expected = "\t".join(HEADER)
        raise ValueError(f"{path}: invalid header; expected {expected}")
    if len(rows) < 3:
        raise ValueError(f"{path}: at least two replica rows are required")

    seen_replicas = set()
    previous_temperature = None

    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) != len(HEADER):
            raise ValueError(
                f"{path}: row {row_number}: expected {len(HEADER)} tab-separated columns, found {len(row)}"
            )

        replica, temperature_text, lambda_pp_text, lambda_pw_text, kappa_text, seed = row
        if not REPLICA.fullmatch(replica):
            fail(path, row_number, "replica", f"expected a three-digit index, found {replica!r}")
        if replica in seen_replicas:
            fail(path, row_number, "replica", f"duplicate replica {replica}")
        seen_replicas.add(replica)

        temperature = parse_decimal(path, row_number, "effective_temperature_K", temperature_text)
        lambda_pp = parse_decimal(path, row_number, "lambda_pp", lambda_pp_text)
        lambda_pw = parse_decimal(path, row_number, "lambda_pw", lambda_pw_text)
        kappa = parse_decimal(path, row_number, "kappa", kappa_text)

        if temperature < 300.0:
            fail(path, row_number, "effective_temperature_K", "must be at least 300 K")
        if previous_temperature is not None and temperature <= previous_temperature:
            fail(path, row_number, "effective_temperature_K", "must increase between replica rows")
        if not 0.0 < lambda_pp <= 1.0:
            fail(path, row_number, "lambda_pp", "must be greater than 0 and at most 1")
        if abs(lambda_pp - 300.0 / temperature) > 1.0e-5:
            fail(path, row_number, "lambda_pp", "must equal 300/effective_temperature_K")
        if not 0.0 < lambda_pw <= 1.0:
            fail(path, row_number, "lambda_pw", "must be greater than 0 and at most 1")
        if abs(lambda_pw * lambda_pw - lambda_pp) > 1.0e-5:
            fail(path, row_number, "lambda_pw", "lambda_pw squared must equal lambda_pp")
        if kappa <= 0.0:
            fail(path, row_number, "kappa", "must be greater than 0")
        if not POSITIVE_INTEGER.fullmatch(seed) or int(seed) <= 0:
            fail(path, row_number, "seed", "must be a positive integer")

        if row_number == 2:
            if replica != "000" or abs(temperature - 300.0) > 1.0e-6:
                fail(path, row_number, "replica", "the first state must be replica 000 at 300 K")
            if abs(kappa - 1.0) > 1.0e-6:
                fail(path, row_number, "kappa", "the 300 K reference state must use kappa=1")
        previous_temperature = temperature


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("states", type=Path, help="REST3 states.tsv file")
    args = parser.parse_args()

    try:
        validate(args.states)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
