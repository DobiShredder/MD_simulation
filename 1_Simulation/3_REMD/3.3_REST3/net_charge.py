#!/usr/bin/env python3
"""Compute the net charge GROMACS should report for each REST replica.

REST scales the charges of hot atoms by sqrt(lambda_pp) and leaves solvent and
ions unscaled. Replica i therefore carries

    Q_i = Q_ref + q_hot * (sqrt(lambda_pp_i) - 1)

where Q_ref is the total charge of the unscaled topology and q_hot is the
unscaled charge of the hot atoms. Without --states, only Q_ref is printed.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


# REST2: mark_hot.py appends this suffix to the atom types that
# `plumed partial_tempering` scales.
HOT_TYPE_SUFFIX = "_"
TABLE_HEADER = [
    "replica",
    "lambda_pp",
    "reference_charge_e",
    "hot_charge_e",
    "expected_charge_e",
]


# One [ moleculetype ]: its name and the (atom type, charge) of each atom.
Definition = tuple[str, list[tuple[str, float]]]


def read_topology(path: Path) -> tuple[list[Definition], list[tuple[str, int]]]:
    """Return molecule definitions and [ molecules ] rows of a flat topology."""
    definitions: list[Definition] = []
    molecule_rows: list[tuple[str, int]] = []
    section = ""
    conditional_depth = 0

    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        data = line.split(";", 1)[0].strip()
        if not data:
            continue

        # ParmEd writes #ifdef FLEXIBLE blocks for water bonds. Charges are
        # only trusted when no directive can change the [ atoms ] records.
        if data.startswith("#"):
            directive = data.split()[0]
            if directive == "#include":
                raise ValueError(f"{path}: line {line_number}: #include is not supported; use a flat topology")
            if directive in ("#ifdef", "#ifndef", "#if"):
                conditional_depth += 1
            elif directive == "#endif":
                conditional_depth -= 1
            continue

        if data.startswith("["):
            section = data.strip("[] ").lower()
            continue

        if section not in ("moleculetype", "atoms", "molecules"):
            continue
        if conditional_depth:
            raise ValueError(
                f"{path}: line {line_number}: [ {section} ] record inside a preprocessor conditional"
            )

        fields = data.split()
        if section == "moleculetype":
            definitions.append((fields[0], []))
        elif section == "atoms":
            if not definitions:
                raise ValueError(f"{path}: line {line_number}: [ atoms ] before [ moleculetype ]")
            if len(fields) < 7:
                raise ValueError(f"{path}: line {line_number}: atom record has no explicit charge")
            try:
                charge = float(fields[6])
            except ValueError as error:
                raise ValueError(f"{path}: line {line_number}: invalid atom charge {fields[6]!r}") from error
            definitions[-1][1].append((fields[1], charge))
        else:
            molecule_rows.append((fields[0], int(fields[1])))

    if not definitions or not molecule_rows:
        raise ValueError(f"{path}: [ moleculetype ] or [ molecules ] not found")
    return definitions, molecule_rows


def charge_totals(
    path: Path,
    hot_molecule_indices: list[int] | None = None,
) -> tuple[float, float, int]:
    """Return Q_ref, q_hot and the hot-atom count over every molecule copy.

    Hot atoms are the marked REST2 types, or every atom of the REST3 molecule
    definitions listed in hot_molecule_indices.
    """
    definitions, molecule_rows = read_topology(path)

    names = [name for name, _ in definitions]
    if len(set(names)) != len(names):
        raise ValueError(f"{path}: duplicate [ moleculetype ] names")
    for hot_molecule_index in hot_molecule_indices or []:
        if not 0 <= hot_molecule_index < len(definitions):
            raise ValueError(f"{path}: hot molecule index {hot_molecule_index} is out of range")

    reference_charge = 0.0
    hot_charge = 0.0
    hot_atom_count = 0
    for name, count in molecule_rows:
        if name not in names:
            raise ValueError(f"{path}: [ molecules ] lists undefined molecule {name}")
        definition_index = names.index(name)
        for atom_type, charge in definitions[definition_index][1]:
            reference_charge += count * charge
            if hot_molecule_indices is None:
                is_hot = atom_type.endswith(HOT_TYPE_SUFFIX)
            else:
                is_hot = definition_index in hot_molecule_indices
            if is_hot:
                hot_charge += count * charge
                hot_atom_count += count

    return reference_charge, hot_charge, hot_atom_count


def write_charge_table(states: Path, output: Path, reference_charge: float, hot_charge: float) -> None:
    with states.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows or "lambda_pp" not in rows[0]:
        raise ValueError(f"{states}: lambda_pp column not found")

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(TABLE_HEADER)
        for row in rows:
            lambda_pp = float(row["lambda_pp"])
            if not 0.0 < lambda_pp <= 1.0:
                raise ValueError(f"{states}: replica {row['replica']}: lambda_pp must be in (0, 1]")
            expected_charge = reference_charge + hot_charge * (math.sqrt(lambda_pp) - 1.0)
            writer.writerow(
                [
                    row["replica"],
                    row["lambda_pp"],
                    f"{reference_charge:.6f}",
                    f"{hot_charge:.6f}",
                    f"{expected_charge:.6f}",
                ]
            )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("topology", type=Path, help="flat GROMACS topology (for example grompp -pp output)")
    parser.add_argument("--states", type=Path, help="states.tsv with replica and lambda_pp columns")
    parser.add_argument("--output", type=Path, help="expected-charge table to write with --states")
    hot = parser.add_mutually_exclusive_group()
    hot.add_argument(
        "--hot-marked-types",
        action="store_true",
        help=f"REST2: hot atoms have types ending in '{HOT_TYPE_SUFFIX}'",
    )
    hot.add_argument(
        "--hot-molecule-index",
        type=int,
        nargs="+",
        metavar="INDEX",
        help="REST3: 0-based [ moleculetype ] indices passed to the parser as hot_molecules",
    )
    args = parser.parse_args()

    if (args.states is None) != (args.output is None):
        parser.error("--states and --output must be used together")
    if args.states is not None and not args.hot_marked_types and args.hot_molecule_index is None:
        parser.error("--states requires --hot-marked-types or --hot-molecule-index")
    return args


def main() -> None:
    args = parse_arguments()

    try:
        reference_charge, hot_charge, hot_atom_count = charge_totals(
            args.topology, args.hot_molecule_index
        )
        if args.states is None:
            print(f"{reference_charge:.6f}")
            return

        if hot_atom_count == 0:
            raise ValueError(f"{args.topology}: no hot atoms found")
        write_charge_table(args.states, args.output, reference_charge, hot_charge)
    except (OSError, ValueError) as error:
        raise SystemExit(f"Error: {error}")


if __name__ == "__main__":
    main()
