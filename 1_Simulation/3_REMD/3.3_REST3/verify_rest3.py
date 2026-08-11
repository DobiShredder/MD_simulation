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

        fields = stripped.replace("\\", " \\ ").split()

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


def cmap_data(path: Path) -> list[tuple[tuple[str, ...], list[float]]]:
    """[ cmaptypes ]에서 atom type과 energy grid를 읽습니다."""
    maps: list[tuple[tuple[str, ...], list[float]]] = []
    section = ""
    atom_types: tuple[str, ...] | None = None
    values: list[float] = []
    expected = 0

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.split(";", 1)[0].strip()
        if not stripped:
            continue

        if stripped.startswith("[") and stripped.endswith("]"):
            if section == "cmaptypes" and expected:
                raise SystemExit(f"CMAP grid 값이 부족합니다: {path}")
            section = stripped.strip("[] ").lower()
            continue

        if section != "cmaptypes":
            continue

        fields = stripped.split()
        is_header = (
            len(fields) >= 8
            and fields[5].isdigit()
            and fields[6].isdigit()
            and fields[7].isdigit()
        )
        if is_header:
            if expected:
                raise SystemExit(f"CMAP grid 값이 부족합니다: {path}")
            atom_types = tuple(fields[:5])
            values = []
            expected = int(fields[6]) * int(fields[7])
            continue

        if atom_types is None:
            raise SystemExit(f"CMAP header를 해석하지 못했습니다: {path}")

        values.extend(float(field) for field in fields if field != "\\")
        if len(values) == expected:
            maps.append((atom_types, values))
            atom_types = None
            values = []
            expected = 0
        elif len(values) > expected:
            raise SystemExit(f"CMAP grid 값이 너무 많습니다: {path}")

    if expected:
        raise SystemExit(f"CMAP grid 값이 부족합니다: {path}")
    if not maps:
        raise SystemExit(f"CMAP map을 찾지 못했습니다: {path}")

    return maps


def verify_cmap_scaling(base: Path, observed: Path, scale: float) -> None:
    base_maps = cmap_data(base)
    observed_maps = cmap_data(observed)

    if len(base_maps) != len(observed_maps):
        raise SystemExit(f"CMAP map 수가 바뀌었습니다: {observed}")

    for (base_types, base_values), (types, values) in zip(base_maps, observed_maps):
        if scale == 1.0:
            expected_types = base_types
        else:
            expected_types = tuple(f"s{name}" for name in base_types)
        if types != expected_types:
            raise SystemExit(f"CMAP atom type이 REST3 hot type과 다릅니다: {observed}")

        for reference, value in zip(base_values, values):
            if not math.isclose(
                reference * scale,
                value,
                rel_tol=1.0e-9,
                abs_tol=1.0e-9,
            ):
                raise SystemExit(f"CMAP energy가 lambda_pp로 scaling되지 않았습니다: {observed}")


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
        verify_cmap_scaling(
            args.base_topology,
            topology,
            float(state["lambda_pp"]),
        )
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

    print("REST3 base identity, CMAP scaling과 solvent interaction 보존을 확인했습니다.")


if __name__ == "__main__":
    main()
