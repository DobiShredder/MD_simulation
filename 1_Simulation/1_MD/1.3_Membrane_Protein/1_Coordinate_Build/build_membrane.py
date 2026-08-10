#!/usr/bin/env python3
"""OPM에서 배향한 단백질을 평형화된 Lipid21 bilayer에 삽입한다."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


DEFAULT_COMPOSITION = {"POPC": 90.0, "POPE": 5.0, "CHOL": 5.0}
DEFAULT_XY_PADDING = 25.0
DEFAULT_WATER_PADDING = 20.0
DEFAULT_PROTEIN_LIPID_DISTANCE = 2.0
SOLUTE_WATER_DISTANCE = 3.0
CHOLESTEROL_HEAVY_DISTANCE = 1.8
CHOLESTEROL_ALL_ATOM_DISTANCE = 0.9
STEROL_BOUNDARY_PADDING = 5.0


@dataclass
class Atom:
    name: str
    residue_name: str
    xyz: np.ndarray


@dataclass
class Residue:
    name: str
    atoms: list[Atom]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OPM 배향 단백질을 Lipid21 bilayer patch에 삽입합니다."
    )
    parser.add_argument("protein", type=Path, help="prepare.py로 만든 KcsA PDB")
    parser.add_argument("popc", type=Path, help="Lipid21 POPC.gro")
    parser.add_argument("pope", type=Path, help="Lipid21 POPE.gro")
    parser.add_argument("cholesterol", type=Path, help="Lipid21 CHOL15.gro")
    parser.add_argument("output", type=Path, help="생성할 membrane system PDB")
    parser.add_argument(
        "--composition",
        default="POPC=90,POPE=5,CHOL=5",
        help="leaflet에 적용할 지질 비율(기본값: POPC=90,POPE=5,CHOL=5)",
    )
    parser.add_argument(
        "--xy-padding",
        type=float,
        default=DEFAULT_XY_PADDING,
        help="단백질 x/y 경계와 box 경계 사이의 최소 거리(A)",
    )
    parser.add_argument(
        "--water-padding",
        type=float,
        default=DEFAULT_WATER_PADDING,
        help="단백질 z 경계와 box 경계 사이의 최소 거리(A)",
    )
    parser.add_argument(
        "--protein-lipid-distance",
        type=float,
        default=DEFAULT_PROTEIN_LIPID_DISTANCE,
        help="삭제할 protein-lipid heavy-atom overlap 거리(A)",
    )
    return parser.parse_args()


def parse_composition(text: str) -> dict[str, float]:
    """POPC=90,POPE=5,CHOL=5 형식을 비율로 변환한다."""
    values: dict[str, float] = {}

    for field in text.split(","):
        try:
            name, value = field.split("=", 1)
            values[name.strip().upper()] = float(value)
        except ValueError as error:
            raise SystemExit(f"지질 비율 형식이 잘못되었습니다: {field}") from error

    if set(values) != set(DEFAULT_COMPOSITION):
        raise SystemExit("composition에는 POPC, POPE, CHOL을 각각 적어야 합니다.")
    if any(value < 0.0 for value in values.values()) or sum(values.values()) <= 0.0:
        raise SystemExit("지질 비율은 0 이상이고 합은 0보다 커야 합니다.")

    total = sum(values.values())
    return {name: value / total for name, value in values.items()}


def read_gro(path: Path) -> tuple[list[Residue], np.ndarray]:
    """GROMACS coordinate를 residue 목록과 box 길이(angstrom)로 읽는다."""
    lines = path.read_text(encoding="ascii").splitlines()
    atom_count = int(lines[1])
    atom_lines = lines[2 : 2 + atom_count]
    box = np.array([float(value) for value in lines[2 + atom_count].split()[:3]])
    box *= 10.0

    residues: list[Residue] = []
    previous_number = None

    for line in atom_lines:
        residue_number = int(line[:5])
        residue_name = line[5:10].strip()
        atom_name = line[10:15].strip()
        xyz = np.array(
            [float(line[20:28]), float(line[28:36]), float(line[36:44])]
        )
        xyz *= 10.0

        if residue_number != previous_number:
            residues.append(Residue(residue_name, []))
            previous_number = residue_number

        residues[-1].atoms.append(Atom(atom_name, residue_name, xyz))

    return residues, box


def copy_residue(residue: Residue) -> Residue:
    atoms = [Atom(atom.name, atom.residue_name, atom.xyz.copy()) for atom in residue.atoms]
    return Residue(residue.name, atoms)


def unwrap_residue(residue: Residue, box: np.ndarray) -> Residue:
    """Periodic boundary를 가로지른 residue의 좌표를 한 덩어리로 모은다."""
    result = copy_residue(residue)
    reference = result.atoms[0].xyz

    for atom in result.atoms[1:]:
        delta = atom.xyz - reference
        delta -= box * np.rint(delta / box)
        atom.xyz = reference + delta

    return result


def collect_lipids(residues: list[Residue], box: np.ndarray) -> list[list[Residue]]:
    """PA-headgroup-OL 세 residue를 POPC 또는 POPE 한 분자로 묶는다."""
    lipids: list[list[Residue]] = []
    index = 0

    while index + 2 < len(residues):
        names = [residues[index + offset].name for offset in range(3)]

        if names not in (["PA", "PC", "OL"], ["PA", "PE", "OL"]):
            index += 1
            continue

        molecule = [
            unwrap_residue(residues[index + offset], box)
            for offset in range(3)
        ]

        # 세 modular residue가 PBC를 서로 다르게 통과한 경우도 모은다.
        reference = molecule[0].atoms[0].xyz
        for residue in molecule[1:]:
            shift = residue.atoms[0].xyz - reference
            shift -= box * np.rint(shift / box)
            shift -= residue.atoms[0].xyz - reference
            for atom in residue.atoms:
                atom.xyz += shift

        lipids.append(molecule)
        index += 3

    return lipids


def collect_cholesterol(residues: list[Residue], box: np.ndarray) -> list[list[Residue]]:
    return [[unwrap_residue(residue, box)] for residue in residues if residue.name == "CHL"]


def collect_water(residues: list[Residue], box: np.ndarray) -> list[Residue]:
    return [unwrap_residue(residue, box) for residue in residues if residue.name == "WAT"]


def find_atom(residues: list[Residue], atom_name: str) -> np.ndarray:
    for residue in residues:
        for atom in residue.atoms:
            if atom.name == atom_name:
                return atom.xyz
    raise ValueError(f"atom을 찾을 수 없습니다: {atom_name}")


def membrane_center(lipids: list[list[Residue]], box: np.ndarray) -> np.ndarray:
    phosphorus = np.array([find_atom(lipid, "P31") for lipid in lipids])
    return np.array([box[0] / 2.0, box[1] / 2.0, phosphorus[:, 2].mean()])


def translate_molecule(molecule: list[Residue], shift: np.ndarray) -> list[Residue]:
    result = [copy_residue(residue) for residue in molecule]
    for residue in result:
        for atom in residue.atoms:
            atom.xyz += shift
    return result


def read_protein(path: Path) -> tuple[list[str], np.ndarray]:
    lines = path.read_text(encoding="ascii").splitlines()
    coordinates = []

    for line in lines:
        if not line.startswith(("ATOM  ", "HETATM")):
            continue
        element = line[76:78].strip() or line[12:16].strip()[0]
        if element.upper() == "H":
            continue
        coordinates.append(
            [float(line[30:38]), float(line[38:46]), float(line[46:54])]
        )

    return lines, np.array(coordinates)


def opm_half_thickness(lines: list[str]) -> float:
    """prepare.py가 남긴 OPM membrane half-thickness를 읽는다."""
    prefix = "REMARK OPM MEMBRANE HALF-THICKNESS"

    for line in lines:
        if line.startswith(prefix):
            return float(line.split()[4])

    raise SystemExit(
        "OPM membrane 배향 기록이 없습니다. "
        "OPM PDB를 prepare.py로 먼저 처리하세요."
    )


def target_box_size(
    protein: np.ndarray,
    source_box: np.ndarray,
    xy_padding: float,
    water_padding: float,
) -> np.ndarray:
    """Bilayer unit cell을 잘라내지 않는 target box를 계산한다."""
    protein_width = np.ptp(protein, axis=0)
    required_xy = protein_width[:2] + 2.0 * xy_padding
    repeats_xy = np.ceil(required_xy / source_box[:2]).astype(int)
    box_xy = repeats_xy * source_box[:2]
    box_z = max(source_box[2], 2.0 * (np.abs(protein[:, 2]).max() + water_padding))
    return np.array([box_xy[0], box_xy[1], box_z])


def molecule_coordinates(molecule: list[Residue]) -> np.ndarray:
    return np.array([atom.xyz for residue in molecule for atom in residue.atoms])


def overlaps_protein(molecule: list[Residue], protein: np.ndarray, cutoff: float) -> bool:
    coordinates = molecule_coordinates(molecule)
    delta = coordinates[:, None, :] - protein[None, :, :]
    distance_squared = np.sum(delta * delta, axis=2)
    return bool(np.any(distance_squared < cutoff * cutoff))


def tile_equilibrated_bilayer(
    lipids: list[list[Residue]],
    source_box: np.ndarray,
    target_box: np.ndarray,
    protein: np.ndarray,
    cutoff: float,
) -> list[list[Residue]]:
    """평형화된 POPC unit cell을 target box 크기만큼 복제한다."""
    center = membrane_center(lipids, source_box)
    result = []
    repeat_x = round(target_box[0] / source_box[0])
    repeat_y = round(target_box[1] / source_box[1])

    for index_x in range(repeat_x):
        shift_x = (index_x + 0.5 - repeat_x / 2.0) * source_box[0]
        for index_y in range(repeat_y):
            shift_y = (index_y + 0.5 - repeat_y / 2.0) * source_box[1]
            shift = np.array([shift_x, shift_y, 0.0]) - center

            for lipid in lipids:
                placed = translate_molecule(lipid, shift)
                if overlaps_protein(placed, protein, cutoff):
                    continue
                result.append(placed)

    return result


def kabsch_transform(source: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """source point를 target point에 겹치는 회전과 이동을 계산한다."""
    source_center = source.mean(axis=0)
    target_center = target.mean(axis=0)
    covariance = (source - source_center).T @ (target - target_center)
    left, _, right = np.linalg.svd(covariance)
    rotation = left @ right

    if np.linalg.det(rotation) < 0.0:
        left[:, -1] *= -1.0
        rotation = left @ right

    translation = target_center - source_center @ rotation
    return rotation, translation


def mutate_to_pope(lipid: list[Residue], pope_template: list[Residue]) -> list[Residue]:
    """POPC의 PC headgroup을 같은 위치의 PE headgroup으로 바꾼다."""
    pa = copy_residue(lipid[0])
    pc = lipid[1]
    ol = copy_residue(lipid[2])
    pe_source = pope_template[1]

    pc_by_name = {atom.name: atom for atom in pc.atoms}
    pe_by_name = {atom.name: atom for atom in pe_source.atoms}
    common_names = sorted(
        name
        for name in pc_by_name.keys() & pe_by_name.keys()
        if not name.startswith("H")
    )
    source = np.array([pe_by_name[name].xyz for name in common_names])
    target = np.array([pc_by_name[name].xyz for name in common_names])
    rotation, translation = kabsch_transform(source, target)

    target_nitrogen = pc_by_name["N31"].xyz
    carbon_to_nitrogen = target_nitrogen - pc_by_name["C32"].xyz
    axis = carbon_to_nitrogen / np.linalg.norm(carbon_to_nitrogen)
    helper = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(axis, helper)) > 0.9:
        helper = np.array([1.0, 0.0, 0.0])
    perpendicular_one = np.cross(axis, helper)
    perpendicular_one /= np.linalg.norm(perpendicular_one)
    perpendicular_two = np.cross(axis, perpendicular_one)

    hydrogen_positions = {}
    for name, angle in zip(("HN1A", "HN1B", "HN1C"), (0.0, 120.0, 240.0)):
        radians = math.radians(angle)
        radial = (
            math.cos(radians) * perpendicular_one
            + math.sin(radians) * perpendicular_two
        )
        direction = axis / 3.0 + math.sqrt(8.0 / 9.0) * radial
        hydrogen_positions[name] = target_nitrogen + 1.01 * direction

    pe_atoms = []
    for atom in pe_source.atoms:
        if atom.name in pc_by_name:
            xyz = pc_by_name[atom.name].xyz.copy()
        elif atom.name in hydrogen_positions:
            xyz = hydrogen_positions[atom.name]
        else:
            xyz = atom.xyz @ rotation + translation
        pe_atoms.append(Atom(atom.name, "PE", xyz))

    return [pa, Residue("PE", pe_atoms), ol]


def rotation_around_z(angle: float) -> np.ndarray:
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return np.array(
        [[cosine, -sine, 0.0], [sine, cosine, 0.0], [0.0, 0.0, 1.0]]
    )


def replace_with_cholesterol(
    lipid: list[Residue],
    template: list[Residue],
    reference_heavy: np.ndarray,
    reference_all: np.ndarray,
    box: np.ndarray,
) -> list[Residue]:
    """POPC 한 분자를 같은 leaflet의 cholesterol 한 분자로 치환한다."""
    result = [copy_residue(template[0])]
    oxygen = find_atom(result, "O1")
    phosphorus = find_atom(lipid, "P31")
    nitrogen = find_atom(lipid, "N31")

    source_direction = find_atom(result, "C4") - oxygen
    target_direction = nitrogen - phosphorus
    source_angle = math.atan2(source_direction[1], source_direction[0])
    target_angle = math.atan2(target_direction[1], target_direction[0])
    base_angle = target_angle - source_angle
    best_distance = -1.0
    best_atom_distance = -1.0
    best_score = -1.0
    best_coordinates = None

    for extra_angle in range(0, 360, 15):
        rotation = rotation_around_z(base_angle + math.radians(extra_angle))
        coordinates = np.array(
            [(atom.xyz - oxygen) @ rotation.T + phosphorus for atom in result[0].atoms]
        )
        heavy = np.array(
            [
                xyz
                for atom, xyz in zip(result[0].atoms, coordinates)
                if not atom.name.startswith("H")
            ]
        )
        delta = heavy[:, None, :] - reference_heavy[None, :, :]
        delta -= box * np.rint(delta / box)
        distance = float(np.sqrt(np.sum(delta * delta, axis=2)).min())
        atom_delta = coordinates[:, None, :] - reference_all[None, :, :]
        atom_delta -= box * np.rint(atom_delta / box)
        atom_distance = float(np.sqrt(np.sum(atom_delta * atom_delta, axis=2)).min())
        score = min(
            distance / CHOLESTEROL_HEAVY_DISTANCE,
            atom_distance / CHOLESTEROL_ALL_ATOM_DISTANCE,
        )

        if score > best_score:
            best_score = score
            best_distance = distance
            best_atom_distance = atom_distance
            best_coordinates = coordinates

    if (
        best_distance < CHOLESTEROL_HEAVY_DISTANCE
        or best_atom_distance < CHOLESTEROL_ALL_ATOM_DISTANCE
    ):
        raise RuntimeError(
            "cholesterol을 겹침 없이 놓지 못했습니다: "
            f"heavy={best_distance:.3f} A, all={best_atom_distance:.3f} A"
        )

    for atom, xyz in zip(result[0].atoms, best_coordinates):
        atom.xyz = xyz

    return result


def evenly_spaced_indices(indices: list[int], count: int, offset: int = 0) -> list[int]:
    """특정 위치에 몰리지 않도록 leaflet 전체에서 index를 고른다."""
    if count == 0:
        return []
    positions = np.linspace(0, len(indices), count, endpoint=False, dtype=int)
    return [indices[(int(position) + offset) % len(indices)] for position in positions]


def apply_composition(
    lipids: list[list[Residue]],
    pope_templates: list[list[Residue]],
    cholesterol_templates: list[list[Residue]],
    composition: dict[str, float],
    box: np.ndarray,
) -> tuple[list[list[Residue]], dict[str, tuple[int, int]]]:
    """각 leaflet에 지정한 POPC, POPE, cholesterol 비율을 적용한다."""
    result = list(lipids)
    counts: dict[str, tuple[int, int]] = {}
    leaflet_indices = {
        sign: [
            index
            for index, lipid in enumerate(lipids)
            if np.sign(find_atom(lipid, "P31")[2]) == sign
        ]
        for sign in (1, -1)
    }

    for leaflet_name, sign in (("upper", 1), ("lower", -1)):
        indices = leaflet_indices[sign]
        indices.sort(
            key=lambda index: math.atan2(
                find_atom(result[index], "P31")[1],
                find_atom(result[index], "P31")[0],
            )
        )

        pope_count = round(len(indices) * composition["POPE"])
        cholesterol_count = round(len(indices) * composition["CHOL"])
        cholesterol_candidates = [
            index
            for index in indices
            if abs(find_atom(result[index], "P31")[0])
            < box[0] / 2.0 - STEROL_BOUNDARY_PADDING
            and abs(find_atom(result[index], "P31")[1])
            < box[1] / 2.0 - STEROL_BOUNDARY_PADDING
        ]
        if len(cholesterol_candidates) < cholesterol_count:
            raise RuntimeError("Box 경계에서 먼 cholesterol 치환 위치가 부족합니다.")
        cholesterol_indices = evenly_spaced_indices(
            cholesterol_candidates, cholesterol_count
        )
        remaining = [index for index in indices if index not in cholesterol_indices]
        pope_indices = evenly_spaced_indices(remaining, pope_count, offset=3)

        pope_template = next(
            template
            for template in pope_templates
            if np.sign(find_atom(template, "P31")[2]) == sign
        )
        cholesterol_template = next(
            template
            for template in cholesterol_templates
            if np.sign(find_atom(template, "O1")[2]) == sign
        )

        for index in pope_indices:
            result[index] = mutate_to_pope(result[index], pope_template)
        for index in cholesterol_indices:
            reference_heavy = np.array(
                [
                    atom.xyz
                    for other_index, other_lipid in enumerate(result)
                    if other_index != index
                    for residue in other_lipid
                    for atom in residue.atoms
                    if not atom.name.startswith("H")
                ]
            )
            reference_all = np.array(
                [
                    atom.xyz
                    for other_index, other_lipid in enumerate(result)
                    if other_index != index
                    for residue in other_lipid
                    for atom in residue.atoms
                ]
            )
            result[index] = replace_with_cholesterol(
                result[index],
                cholesterol_template,
                reference_heavy,
                reference_all,
                box,
            )

        popc_count = len(indices) - pope_count - cholesterol_count
        counts[leaflet_name] = (popc_count, pope_count, cholesterol_count)

    return result, counts


def normalize_templates(
    lipids: list[list[Residue]], source_box: np.ndarray
) -> list[list[Residue]]:
    center = membrane_center(lipids, source_box)
    return [translate_molecule(lipid, -center) for lipid in lipids]


def normalize_cholesterol_templates(
    lipids: list[list[Residue]], source_box: np.ndarray
) -> list[list[Residue]]:
    oxygens = np.array([find_atom(lipid, "O1") for lipid in lipids])
    center = np.array(
        [source_box[0] / 2.0, source_box[1] / 2.0, oxygens[:, 2].mean()]
    )
    return [translate_molecule(lipid, -center) for lipid in lipids]


def tile_water(
    waters: list[Residue],
    source_box: np.ndarray,
    source_center: np.ndarray,
    target_box: np.ndarray,
    protein: np.ndarray,
) -> list[Residue]:
    """평형화된 water slab을 target box까지 반복하고 protein overlap을 제거한다."""
    result: list[Residue] = []
    repeat = np.ceil(target_box / (2.0 * source_box)).astype(int)

    for index_x in range(-repeat[0], repeat[0] + 1):
        shift_x = index_x * source_box[0]
        for index_y in range(-repeat[1], repeat[1] + 1):
            shift_y = index_y * source_box[1]
            for index_z in range(-repeat[2], repeat[2] + 1):
                shift_z = index_z * source_box[2]
                shift = np.array([shift_x, shift_y, shift_z]) - source_center

                for water in waters:
                    oxygen = water.atoms[0].xyz + shift

                    if abs(oxygen[0]) >= target_box[0] / 2.0:
                        continue
                    if abs(oxygen[1]) >= target_box[1] / 2.0:
                        continue
                    if abs(oxygen[2]) >= target_box[2] / 2.0:
                        continue

                    delta = protein - oxygen
                    if np.any(np.sum(delta * delta, axis=1) < SOLUTE_WATER_DISTANCE**2):
                        continue

                    placed = translate_molecule([water], shift)[0]
                    result.append(placed)

    return result


def remove_water_lipid_overlaps(
    waters: list[Residue], lipids: list[list[Residue]], box: np.ndarray
) -> list[Residue]:
    """Lipid 치환으로 새로 생긴 water overlap을 제거한다."""
    cell_counts = np.floor(box / SOLUTE_WATER_DISTANCE).astype(int)
    cells: dict[tuple[int, int, int], list[np.ndarray]] = {}

    for lipid in lipids:
        for residue in lipid:
            for atom in residue.atoms:
                if atom.name.startswith("H"):
                    continue
                wrapped = (atom.xyz + box / 2.0) % box
                cell = tuple(np.floor(wrapped / box * cell_counts).astype(int))
                cells.setdefault(cell, []).append(atom.xyz)

    kept = []

    for water in waters:
        oxygen = water.atoms[0].xyz
        wrapped = (oxygen + box / 2.0) % box
        cell = tuple(np.floor(wrapped / box * cell_counts).astype(int))
        overlap = False

        for offset_x in (-1, 0, 1):
            for offset_y in (-1, 0, 1):
                for offset_z in (-1, 0, 1):
                    neighbor = (
                        (cell[0] + offset_x) % cell_counts[0],
                        (cell[1] + offset_y) % cell_counts[1],
                        (cell[2] + offset_z) % cell_counts[2],
                    )
                    for atom_xyz in cells.get(neighbor, []):
                        delta = oxygen - atom_xyz
                        delta -= box * np.rint(delta / box)
                        if np.dot(delta, delta) < SOLUTE_WATER_DISTANCE**2:
                            overlap = True
                            break
                    if overlap:
                        break
                if overlap:
                    break
            if overlap:
                break

        if overlap:
            continue

        kept.append(water)

    return kept


def remove_water_water_overlaps(
    waters: list[Residue], box: np.ndarray
) -> list[Residue]:
    """Source water patch가 새 box boundary에서 겹치는 경우 한쪽을 제거한다."""
    cutoff = 2.4
    cell_counts = np.floor(box / cutoff).astype(int)
    cells: dict[tuple[int, int, int], list[np.ndarray]] = {}
    kept = []

    for water in waters:
        oxygen = water.atoms[0].xyz
        wrapped = (oxygen + box / 2.0) % box
        cell = tuple(np.floor(wrapped / box * cell_counts).astype(int))
        overlap = False

        for offset_x in (-1, 0, 1):
            for offset_y in (-1, 0, 1):
                for offset_z in (-1, 0, 1):
                    neighbor = (
                        (cell[0] + offset_x) % cell_counts[0],
                        (cell[1] + offset_y) % cell_counts[1],
                        (cell[2] + offset_z) % cell_counts[2],
                    )
                    for other in cells.get(neighbor, []):
                        delta = oxygen - other
                        delta -= box * np.rint(delta / box)
                        if np.dot(delta, delta) < cutoff * cutoff:
                            overlap = True
                            break
                    if overlap:
                        break
                if overlap:
                    break
            if overlap:
                break

        if overlap:
            continue

        cells.setdefault(cell, []).append(oxygen)
        kept.append(water)

    return kept


def pdb_atom_line(
    serial: int,
    atom_name: str,
    residue_name: str,
    chain: str,
    residue_number: int,
    xyz: np.ndarray,
) -> str:
    x, y, z = xyz
    element = "".join(character for character in atom_name if character.isalpha())[0]
    serial = (serial - 1) % 99999 + 1
    residue_number = (residue_number - 1) % 9999 + 1
    return (
        f"ATOM  {serial:5d} {atom_name:^4s} {residue_name:>3s} {chain}"
        f"{residue_number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}"
        f"  1.00  0.00          {element:>2s}"
    )


def write_system(
    protein_lines: list[str],
    lipids: list[list[Residue]],
    waters: list[Residue],
    box: np.ndarray,
    output: Path,
) -> None:
    box_x, box_y, box_z = box
    lines = [
        f"CRYST1{box_x:9.3f}{box_y:9.3f}{box_z:9.3f}"
        f"{90.0:7.2f}{90.0:7.2f}{90.0:7.2f} P 1           1"
    ]
    serial = 1
    residue_number = 0

    for line in protein_lines:
        if line.startswith(("ATOM  ", "HETATM")):
            lines.append(f"{line[:6]}{serial:5d}{line[11:]}")
            serial += 1
            residue_number = max(residue_number, int(line[22:26]))
        elif line.startswith("TER"):
            lines.append("TER")

    for lipid in lipids:
        for residue in lipid:
            residue_number += 1
            for atom in residue.atoms:
                lines.append(
                    pdb_atom_line(
                        serial,
                        atom.name,
                        residue.name,
                        "L",
                        residue_number,
                        atom.xyz,
                    )
                )
                serial += 1
        lines.append("TER")

    for water in waters:
        residue_number += 1
        for atom in water.atoms:
            lines.append(
                pdb_atom_line(
                    serial,
                    atom.name,
                    "WAT",
                    "W",
                    residue_number,
                    atom.xyz,
                )
            )
            serial += 1

    lines.append("END")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> None:
    args = parse_arguments()
    for path in (args.protein, args.popc, args.pope, args.cholesterol):
        if not path.is_file():
            raise SystemExit(f"input file을 찾을 수 없습니다: {path}")

    if args.xy_padding <= 0.0 or args.water_padding <= 0.0:
        raise SystemExit("xy-padding과 water-padding은 0보다 커야 합니다.")
    if args.protein_lipid_distance <= 0.0:
        raise SystemExit("protein-lipid-distance는 0보다 커야 합니다.")

    composition = parse_composition(args.composition)
    protein_lines, protein_heavy = read_protein(args.protein)
    half_thickness = opm_half_thickness(protein_lines)
    popc_residues, popc_box = read_gro(args.popc)
    pope_residues, pope_box = read_gro(args.pope)
    cholesterol_residues, cholesterol_box = read_gro(args.cholesterol)

    target_box = target_box_size(
        protein_heavy,
        popc_box,
        args.xy_padding,
        args.water_padding,
    )

    popc_lipids = collect_lipids(popc_residues, popc_box)
    pope_lipids = normalize_templates(collect_lipids(pope_residues, pope_box), pope_box)
    cholesterol_lipids = normalize_cholesterol_templates(
        collect_cholesterol(cholesterol_residues, cholesterol_box),
        cholesterol_box,
    )

    source_center = membrane_center(popc_lipids, popc_box)
    lipids = tile_equilibrated_bilayer(
        popc_lipids,
        popc_box,
        target_box,
        protein_heavy,
        args.protein_lipid_distance,
    )
    lipids, counts = apply_composition(
        lipids,
        pope_lipids,
        cholesterol_lipids,
        composition,
        target_box,
    )

    source_waters = collect_water(popc_residues, popc_box)
    waters = tile_water(
        source_waters,
        popc_box,
        source_center,
        target_box,
        protein_heavy,
    )
    waters = remove_water_lipid_overlaps(waters, lipids, target_box)
    waters = remove_water_water_overlaps(waters, target_box)

    write_system(protein_lines, lipids, waters, target_box, args.output)

    print(f"Membrane coordinate: {args.output}")
    print(f"OPM membrane half-thickness: {half_thickness:.1f} A")
    print(
        "Box: "
        f"{target_box[0]:.3f} x {target_box[1]:.3f} x {target_box[2]:.3f} A"
    )
    for leaflet, (popc, pope, cholesterol) in counts.items():
        print(
            f"{leaflet}: POPC={popc}, POPE={pope}, "
            f"cholesterol={cholesterol}"
        )
    print(f"Bulk water: {len(waters)}")


if __name__ == "__main__":
    main()
