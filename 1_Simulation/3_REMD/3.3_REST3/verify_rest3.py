#!/usr/bin/env python3
"""REST3 base identity와 solvent interaction 보존을 검사합니다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
from pathlib import Path

SOLVENT_NAMES = {"WAT", "HOH", "SOL", "TIP3"}
ION_NAMES = {"NA", "NA+", "SOD", "CL", "CL-", "CLA"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def topology_data(path: Path) -> tuple[dict[str, tuple[float, float]], dict[tuple[str, str], tuple[float, float]], str, set[str]]:
    atomtypes: dict[str, tuple[float, float]] = {}
    pairs: dict[tuple[str, str], tuple[float, float]] = {}
    water_type = ""
    ion_types: set[str] = set()
    section = ""

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.split(";", 1)[0].strip()
        if not stripped:
            continue

        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[] ").lower()
            continue

        fields = stripped.split()

        if section == "atomtypes" and len(fields) >= 3:
            try:
                atomtypes[fields[0]] = (float(fields[-2]), float(fields[-1]))
            except ValueError:
                pass

        elif section == "nonbond_params" and len(fields) >= 5:
            try:
                key = tuple(sorted((fields[0], fields[1])))
                pairs[key] = (float(fields[-2]), float(fields[-1]))
            except ValueError:
                pass

        elif section == "atoms" and len(fields) >= 5 and fields[0].isdigit():
            atom_type = fields[1]
            residue_name = fields[3].upper()
            atom_name = fields[4].upper()

            if residue_name in SOLVENT_NAMES and atom_name in {"O", "OW"}:
                water_type = atom_type
            elif residue_name in ION_NAMES:
                ion_types.add(atom_type)

    if not water_type:
        raise SystemExit(f"TIP3P oxygen type을 찾지 못했습니다: {path}")

    return atomtypes, pairs, water_type, ion_types


def pair_parameters(
    atomtypes: dict[str, tuple[float, float]],
    pairs: dict[tuple[str, str], tuple[float, float]],
    first: str,
    second: str,
) -> tuple[float, float]:
    key = tuple(sorted((first, second)))
    if key in pairs:
        return pairs[key]

    sigma_first, epsilon_first = atomtypes[first]
    sigma_second, epsilon_second = atomtypes[second]
    sigma = (sigma_first + sigma_second) / 2.0
    epsilon = math.sqrt(epsilon_first * epsilon_second)
    return sigma, epsilon


def close_pair(reference: tuple[float, float], observed: tuple[float, float]) -> bool:
    return all(
        math.isclose(left, right, rel_tol=1.0e-10, abs_tol=1.0e-12)
        for left, right in zip(reference, observed)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_topology", type=Path)
    parser.add_argument("states", type=Path)
    parser.add_argument("replica_directory", type=Path)
    args = parser.parse_args()

    replica_zero = args.replica_directory / "000" / "topol.top"
    if digest(args.base_topology) != digest(replica_zero):
        raise SystemExit("REST3 replica 000 topology가 base topology와 다릅니다.")

    base_atomtypes, base_pairs, base_water, base_ions = topology_data(
        args.base_topology
    )
    reference_pairs = {
        (base_water, base_water): pair_parameters(
            base_atomtypes, base_pairs, base_water, base_water
        )
    }
    for ion_type in base_ions:
        reference_pairs[(ion_type, base_water)] = pair_parameters(
            base_atomtypes, base_pairs, ion_type, base_water
        )

    with args.states.open(encoding="utf-8", newline="") as handle:
        states = list(csv.DictReader(handle, delimiter="\t"))

    for state in states:
        topology = args.replica_directory / state["replica"] / "topol.top"
        atomtypes, pairs, water_type, ion_types = topology_data(topology)

        if water_type != base_water:
            raise SystemExit(
                f"TIP3P oxygen type이 바뀌었습니다: {state['replica']}"
            )

        if ion_types != base_ions:
            raise SystemExit(f"ion atom type이 바뀌었습니다: {state['replica']}")

        for (first, second), reference in reference_pairs.items():
            observed = pair_parameters(atomtypes, pairs, first, second)
            if not close_pair(reference, observed):
                raise SystemExit(
                    "water–water 또는 ion–water interaction이 바뀌었습니다: "
                    f"replica {state['replica']}, {first}-{second}"
                )

    print("REST3 base identity와 solvent interaction 보존을 확인했습니다.")


if __name__ == "__main__":
    main()

