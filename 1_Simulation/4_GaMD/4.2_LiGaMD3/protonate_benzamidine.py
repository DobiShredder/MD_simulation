#!/usr/bin/env python3
"""RCSB neutral BEN SDF에 proton을 하나 추가해 benzamidinium(+1)을 만듭니다."""

from __future__ import annotations

import argparse
import math
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_sdf", type=Path)
    parser.add_argument("output_sdf", type=Path)
    return parser.parse_args()


def atom_element(line: str) -> str:
    return line[31:34].strip()


def bond_record(line: str) -> tuple[int, int, int]:
    return int(line[0:3]), int(line[3:6]), int(line[6:9])


def coordinates(line: str) -> tuple[float, float, float]:
    return float(line[0:10]), float(line[10:20]), float(line[20:30])


def reflected_hydrogen(
    nitrogen: tuple[float, float, float],
    carbon: tuple[float, float, float],
    hydrogen: tuple[float, float, float],
) -> tuple[float, float, float]:
    axis = tuple(carbon[index] - nitrogen[index] for index in range(3))
    axis_norm = math.sqrt(sum(value * value for value in axis))
    unit_axis = tuple(value / axis_norm for value in axis)

    existing = tuple(hydrogen[index] - nitrogen[index] for index in range(3))
    projection = sum(existing[index] * unit_axis[index] for index in range(3))
    reflected = tuple(
        2.0 * projection * unit_axis[index] - existing[index]
        for index in range(3)
    )
    reflected_norm = math.sqrt(sum(value * value for value in reflected))
    bond_length = 1.01

    return tuple(
        nitrogen[index] + bond_length * reflected[index] / reflected_norm
        for index in range(3)
    )


def main() -> None:
    args = parse_arguments()
    lines = args.input_sdf.read_text(encoding="utf-8").splitlines()
    if len(lines) < 5 or "V2000" not in lines[3]:
        raise SystemExit("V2000 BEN SDF만 지원합니다.")

    atom_count = int(lines[3][0:3])
    bond_count = int(lines[3][3:6])
    atom_lines = lines[4 : 4 + atom_count]
    bond_lines = lines[4 + atom_count : 4 + atom_count + bond_count]
    property_lines = lines[4 + atom_count + bond_count :]

    elements = [atom_element(line) for line in atom_lines]
    neighbors: dict[int, list[tuple[int, int]]] = {
        index: [] for index in range(1, atom_count + 1)
    }
    for line in bond_lines:
        left, right, order = bond_record(line)
        neighbors[left].append((right, order))
        neighbors[right].append((left, order))

    central_candidates = []
    for atom_index, element in enumerate(elements, start=1):
        bonded_nitrogens = [
            neighbor
            for neighbor, _ in neighbors[atom_index]
            if elements[neighbor - 1] == "N"
        ]
        if element == "C" and len(bonded_nitrogens) == 2:
            central_candidates.append((atom_index, bonded_nitrogens))

    if len(central_candidates) != 1:
        raise SystemExit("BEN amidine carbon을 하나만 찾지 못했습니다.")

    central_carbon, nitrogens = central_candidates[0]
    imine_candidates = []
    for nitrogen in nitrogens:
        carbon_bond_order = next(
            order for neighbor, order in neighbors[nitrogen]
            if neighbor == central_carbon
        )
        bonded_hydrogens = [
            neighbor
            for neighbor, _ in neighbors[nitrogen]
            if elements[neighbor - 1] == "H"
        ]
        if carbon_bond_order == 2 and len(bonded_hydrogens) == 1:
            imine_candidates.append((nitrogen, bonded_hydrogens[0]))

    if len(imine_candidates) != 1:
        raise SystemExit("Proton을 추가할 imine nitrogen을 하나만 찾지 못했습니다.")

    nitrogen, existing_hydrogen = imine_candidates[0]
    new_xyz = reflected_hydrogen(
        coordinates(atom_lines[nitrogen - 1]),
        coordinates(atom_lines[central_carbon - 1]),
        coordinates(atom_lines[existing_hydrogen - 1]),
    )
    new_atom = (
        f"{new_xyz[0]:10.4f}{new_xyz[1]:10.4f}{new_xyz[2]:10.4f} "
        "H   0  0  0  0  0"
    )
    new_atom_index = atom_count + 1
    new_bond = f"{nitrogen:3d}{new_atom_index:3d}{1:3d}  0  0  0"

    if any(line.startswith("M  CHG") for line in property_lines):
        raise SystemExit("Input SDF에 이미 formal charge가 있습니다.")

    output = lines[:3]
    output.append(f"{new_atom_index:3d}{bond_count + 1:3d}" + lines[3][6:])
    output.extend(atom_lines)
    output.append(new_atom)
    output.extend(bond_lines)
    output.append(new_bond)

    inserted_charge = False
    for line in property_lines:
        if line == "M  END" and not inserted_charge:
            output.append(f"M  CHG  1{nitrogen:4d}{1:4d}")
            inserted_charge = True
        output.append(line)

    if not inserted_charge:
        raise SystemExit("SDF의 M  END record를 찾지 못했습니다.")

    args.output_sdf.parent.mkdir(parents=True, exist_ok=True)
    args.output_sdf.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"Protonated BEN(+1): {args.output_sdf}")


if __name__ == "__main__":
    main()

