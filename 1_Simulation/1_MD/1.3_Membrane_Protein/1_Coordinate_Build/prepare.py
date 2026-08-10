#!/usr/bin/env python3
"""1K4C.pdb1에서 neutral-pH KcsA tetramer와 pore 성분을 추출한다."""

from __future__ import annotations

import argparse
from pathlib import Path


Coordinate = tuple[float, float, float]

# Fixed-charge neutral-pH baseline을 PDB residue name으로 명시한다.
# E71과 D80은 filter 뒤쪽의 쌍을 이루며, 이 tutorial은
# protonated E71과 deprotonated D80을 사용한다.
PROTONATION_NAMES = {
    25: "HIE",
    71: "GLH",
    80: "ASP",
    118: "GLU",
    120: "GLU",
}

# 1K4C biological assembly에서 pore 주변에 배치된 결정수이다.
# Assembly model 네 개의 대칭 좌표를 모두 유지한다.
PORE_WATER_RESIDUES = {3008, 3009, 3010, 3011}


def parse_arguments() -> argparse.Namespace:
    """Command-line argument를 읽는다."""
    parser = argparse.ArgumentParser(
        description=(
            "PDB 1K4C에서 neutral-pH tetramer, filter ion과 "
            "pore water를 추출하고 중심을 맞춥니다."
        )
    )
    parser.add_argument("assembly_pdb", type=Path, help="다운로드한 1K4C assembly PDB")
    parser.add_argument("output_pdb", type=Path, help="전처리 결과 KcsA tetramer PDB")

    return parser.parse_args()


def read_coordinates(line: str) -> Coordinate:
    """PDB record의 x, y, z coordinate를 읽는다."""
    x = float(line[30:38])
    y = float(line[38:46])
    z = float(line[46:54])

    return x, y, z


def rewrite_record(
    line: str,
    serial: int,
    chain: str,
    coordinates: Coordinate,
    residue_number: int | None = None,
) -> str:
    """PDB record의 serial, chain, residue number와 coordinate를 바꾼다."""
    x, y, z = coordinates
    residue_field = line[22:26]

    if residue_number is not None:
        residue_field = f"{residue_number:4d}"

    return (
        f"{line[:6]}{serial:5d}{line[11:21]}{chain}{residue_field}{line[26:30]}"
        f"{x:8.3f}{y:8.3f}{z:8.3f}{line[54:]}"
    )


def rename_residue(line: str, residue_name: str) -> str:
    """PDB residue name을 AMBER에서 인식하는 이름으로 바꾼다."""
    return f"{line[:17]}{residue_name:>3}{line[20:]}"


def collect_assembly_records(
    lines: list[str],
) -> tuple[dict[int, list[str]], list[str], list[str]]:
    """KcsA, model 1 filter K+와 model별 pore water를 선택한다."""
    protein_models: dict[int, list[str]] = {}
    potassium_records: list[str] = []
    water_records: list[str] = []
    model_id = 0

    for line in lines:
        if line.startswith("MODEL "):
            model_id = int(line.split()[1])
            continue

        if line.startswith("ATOM  ") and line[21:22] == "C":
            alternate_location = line[16:17]
            residue_number = int(line[22:26])

            # H124는 imidazole side chain 좌표가 없어 tutorial model에서 제외한다.
            if alternate_location in {" ", "A"} and residue_number != 124:
                protein_models.setdefault(model_id, []).append(line)

            continue

        is_filter_potassium = (
            model_id == 1
            and line.startswith("HETATM")
            and line[17:20] == "  K"
        )

        if is_filter_potassium:
            potassium_records.append(line)

        is_pore_water = (
            line.startswith("HETATM")
            and line[17:20] == "HOH"
            and line[21:22] == "C"
            and int(line[22:26]) in PORE_WATER_RESIDUES
        )

        if is_pore_water:
            water_records.append(line)

    return protein_models, potassium_records, water_records


def count_residues(protein_models: dict[int, list[str]]) -> int:
    """Assembly model의 protein residue 수를 계산한다."""
    residue_count = 0

    for records in protein_models.values():
        residue_keys = {
            (line[22:26], line[26:27])
            for line in records
        }
        residue_count += len(residue_keys)

    return residue_count


def validate_assembly(
    protein_models: dict[int, list[str]],
    potassium_records: list[str],
    water_records: list[str],
) -> None:
    """Tutorial에서 사용하는 1K4C assembly 구성을 확인한다."""
    model_ids = sorted(protein_models)

    if model_ids != [1, 2, 3, 4]:
        raise SystemExit(
            f"assembly model 4개가 필요하지만 다음 model을 찾았습니다: {model_ids}"
        )

    residue_count = count_residues(protein_models)

    if (
        residue_count != 408
        or len(potassium_records) != 7
        or len(water_records) != 16
    ):
        raise SystemExit(
            "예상하지 못한 KcsA assembly입니다: "
            f"residues={residue_count}, K={len(potassium_records)}, "
            f"pore waters={len(water_records)}"
        )


def calculate_center(
    protein_models: dict[int, list[str]],
    potassium_records: list[str],
) -> Coordinate:
    """Filter K+ 축의 x/y와 protein의 z 평균으로 이동할 중심을 계산한다."""
    ion_coordinates = [read_coordinates(line) for line in potassium_records]
    center_x = sum(point[0] for point in ion_coordinates) / len(ion_coordinates)
    center_y = sum(point[1] for point in ion_coordinates) / len(ion_coordinates)

    protein_coordinates = [
        read_coordinates(line)
        for records in protein_models.values()
        for line in records
    ]
    center_z = sum(point[2] for point in protein_coordinates) / len(protein_coordinates)

    return center_x, center_y, center_z


def shift_coordinates(coordinates: Coordinate, center: Coordinate) -> Coordinate:
    """Coordinate에서 계산한 assembly center를 뺀다."""
    x, y, z = coordinates
    center_x, center_y, center_z = center

    return x - center_x, y - center_y, z - center_z


def build_output_records(
    protein_models: dict[int, list[str]],
    potassium_records: list[str],
    water_records: list[str],
    center: Coordinate,
) -> list[str]:
    """Tetramer, filter K+와 pore water를 AMBER PDB로 만든다."""
    output_records: list[str] = []
    serial = 1

    for model_id, chain in zip((1, 2, 3, 4), "ABCD"):
        for line in protein_models[model_id]:
            residue_number = int(line[22:26])
            residue_name = PROTONATION_NAMES.get(residue_number)

            if residue_name is not None:
                line = rename_residue(line, residue_name)

            shifted = shift_coordinates(read_coordinates(line), center)
            output_records.append(rewrite_record(line, serial, chain, shifted))
            serial += 1

        output_records.append("TER")

    for line in potassium_records:
        shifted = shift_coordinates(read_coordinates(line), center)
        line = f"{line[:54]}  1.00{line[60:]}"
        output_records.append(rewrite_record(line, serial, "I", shifted))
        serial += 1

    output_records.append("TER")

    for water_number, line in enumerate(water_records, start=1):
        line = rename_residue(line, "WAT")
        shifted = shift_coordinates(read_coordinates(line), center)
        output_records.append(
            rewrite_record(
                line,
                serial,
                "W",
                shifted,
                residue_number=water_number,
            )
        )
        serial += 1

    output_records.append("END")

    return output_records


def main() -> None:
    args = parse_arguments()

    if not args.assembly_pdb.is_file():
        raise SystemExit(f"assembly PDB를 찾을 수 없습니다: {args.assembly_pdb}")

    input_lines = args.assembly_pdb.read_text(encoding="ascii").splitlines()
    protein_models, potassium_records, water_records = collect_assembly_records(
        input_lines
    )

    validate_assembly(protein_models, potassium_records, water_records)

    center = calculate_center(protein_models, potassium_records)
    output_records = build_output_records(
        protein_models,
        potassium_records,
        water_records,
        center,
    )

    args.output_pdb.parent.mkdir(parents=True, exist_ok=True)
    args.output_pdb.write_text("\n".join(output_records) + "\n", encoding="ascii")

    print(
        f"KcsA tetramer 전처리 결과: {args.output_pdb} "
        "(408 residues, K+ 7개, pore water 16개)"
    )
    print(
        "Neutral-pH baseline: E71=GLH, D80=ASP, "
        "H25=HIE, E118/E120=GLU; incomplete H124 omitted"
    )


if __name__ == "__main__":
    main()
