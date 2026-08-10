#!/usr/bin/env python3
"""OPM 1K4C에서 oriented KcsA tetramer와 pore 성분을 추출한다."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np


OPM_CHAINS = {"C": "A", "F": "B", "I": "C", "L": "D"}
PORE_WATER_RESIDUES = {3008, 3009, 3010, 3011}
PROTONATION_NAMES = {
    25: "HIE",
    71: "GLH",
    80: "ASP",
    118: "GLU",
    120: "GLU",
}
SIDECHAIN_TEMPLATE_CHAIN = "K"
MISSING_ATOMS = {
    22: {"OG"},
    117: {"CG", "CD", "NE", "CZ", "NH1", "NH2"},
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OPM 1K4C에서 oriented KcsA tetramer를 준비합니다."
    )
    parser.add_argument("opm_pdb", type=Path, help="OPM에서 받은 1K4C PDB")
    parser.add_argument("output_pdb", type=Path, help="전처리한 KcsA PDB")
    parser.add_argument(
        "sidechain_template",
        type=Path,
        nargs="?",
        help="missing side chain을 가져올 OPM 3EFF PDB",
    )
    return parser.parse_args()


def membrane_half_thickness(lines: list[str]) -> float:
    for line in lines:
        if not line.startswith("REMARK") or "bilayer thickness" not in line:
            continue

        match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*$", line)
        if match is not None:
            return float(match.group(1))

    raise SystemExit("OPM membrane thickness REMARK를 찾을 수 없습니다.")


def rename_residue(line: str, residue_name: str) -> str:
    return f"{line[:17]}{residue_name:>3}{line[20:]}"


def rewrite_record(
    line: str,
    serial: int,
    chain: str,
    residue_number: int | None = None,
) -> str:
    residue_field = line[22:26]
    if residue_number is not None:
        residue_field = f"{residue_number:4d}"

    return f"{line[:6]}{serial:5d}{line[11:21]}{chain}{residue_field}{line[26:]}"


def collect_protein(lines: list[str]) -> dict[str, list[str]]:
    chains = {chain: [] for chain in OPM_CHAINS}

    for line in lines:
        if not line.startswith("ATOM  "):
            continue

        chain = line[21:22]
        if chain not in OPM_CHAINS:
            continue

        residue_number = int(line[22:26])
        alternate_location = line[16:17]

        # H124에는 imidazole side-chain 좌표가 없어 residue 전체를 제외합니다.
        if residue_number == 124 or alternate_location not in {" ", "A"}:
            continue

        residue_name = PROTONATION_NAMES.get(residue_number)
        if residue_name is not None:
            line = rename_residue(line, residue_name)

        chains[chain].append(line)

    return chains


def atom_coordinates(line: str) -> np.ndarray:
    return np.array(
        [float(line[30:38]), float(line[38:46]), float(line[46:54])]
    )


def replace_coordinates(line: str, xyz: np.ndarray) -> str:
    x, y, z = xyz
    return f"{line[:30]}{x:8.3f}{y:8.3f}{z:8.3f}{line[54:]}"


def residue_atoms(records: list[str], residue_number: int) -> dict[str, str]:
    return {
        line[12:16].strip(): line
        for line in records
        if int(line[22:26]) == residue_number
    }


def collect_template(lines: list[str]) -> list[str]:
    return [
        line
        for line in lines
        if line.startswith("ATOM  ") and line[21:22] == SIDECHAIN_TEMPLATE_CHAIN
    ]


def local_transform(
    source_atoms: dict[str, str], target_atoms: dict[str, str]
) -> tuple[np.ndarray, np.ndarray]:
    fit_names = ["N", "CA", "C", "CB"]
    source = np.array([atom_coordinates(source_atoms[name]) for name in fit_names])
    target = np.array([atom_coordinates(target_atoms[name]) for name in fit_names])
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


def restore_missing_sidechains(
    chains: dict[str, list[str]], template: list[str]
) -> None:
    """3EFF side chain을 1K4C residue의 local backbone에 맞춰 추가한다."""
    for residue_number, missing_names in MISSING_ATOMS.items():
        source_atoms = residue_atoms(template, residue_number)

        for chain, records in chains.items():
            target_atoms = residue_atoms(records, residue_number)
            rotation, translation = local_transform(source_atoms, target_atoms)
            additions = []

            for atom_name in sorted(missing_names):
                source_line = source_atoms[atom_name]
                xyz = atom_coordinates(source_line) @ rotation + translation
                line = replace_coordinates(source_line, xyz)
                line = f"{line[:21]}{chain}{residue_number:4d}{line[26:]}"
                additions.append(line)

            last_index = max(
                index
                for index, line in enumerate(records)
                if int(line[22:26]) == residue_number
            )
            records[last_index + 1 : last_index + 1] = additions


def collect_filter_ions(lines: list[str]) -> list[str]:
    # OPM assembly의 C/F/I/L chain에 같은 ion site가 네 번 겹칩니다.
    return [
        line
        for line in lines
        if line.startswith("HETATM")
        and line[17:20] == "  K"
        and line[21:22] == "C"
    ]


def collect_pore_waters(lines: list[str]) -> list[str]:
    return [
        line
        for line in lines
        if line.startswith("HETATM")
        and line[17:20] == "HOH"
        and line[21:22] in OPM_CHAINS
        and int(line[22:26]) in PORE_WATER_RESIDUES
    ]


def residue_count(chains: dict[str, list[str]]) -> int:
    count = 0
    for records in chains.values():
        count += len({(line[22:26], line[26:27]) for line in records})
    return count


def validate_selection(
    chains: dict[str, list[str]],
    ions: list[str],
    waters: list[str],
    half_thickness: float,
) -> None:
    empty_chains = [chain for chain, records in chains.items() if not records]
    if empty_chains:
        raise SystemExit(f"OPM KcsA chain을 찾을 수 없습니다: {empty_chains}")

    if residue_count(chains) != 408 or len(ions) != 7 or len(waters) != 16:
        raise SystemExit(
            "예상하지 못한 OPM 1K4C 구성입니다: "
            f"residues={residue_count(chains)}, K={len(ions)}, "
            f"pore waters={len(waters)}"
        )

    if abs(half_thickness - 15.0) > 0.1:
        raise SystemExit(
            "OPM membrane half-thickness가 tutorial 기준과 다릅니다: "
            f"{half_thickness:.3f} A"
        )

    for records in chains.values():
        for residue_number, atom_names in MISSING_ATOMS.items():
            present = set(residue_atoms(records, residue_number))
            if not atom_names <= present:
                raise SystemExit(
                    f"residue {residue_number} side chain을 복원하지 못했습니다."
                )


def build_output(
    chains: dict[str, list[str]],
    ions: list[str],
    waters: list[str],
    half_thickness: float,
) -> list[str]:
    output = [f"REMARK OPM MEMBRANE HALF-THICKNESS {half_thickness:.3f} ANGSTROM"]
    serial = 1

    for source_chain, output_chain in OPM_CHAINS.items():
        for line in chains[source_chain]:
            output.append(rewrite_record(line, serial, output_chain))
            serial += 1
        output.append("TER")

    for line in ions:
        output.append(rewrite_record(line, serial, "I"))
        serial += 1
    output.append("TER")

    for water_number, line in enumerate(waters, start=1):
        line = rename_residue(line, "WAT")
        output.append(
            rewrite_record(line, serial, "W", residue_number=water_number)
        )
        serial += 1

    output.append("END")
    return output


def main() -> None:
    args = parse_arguments()
    if not args.opm_pdb.is_file():
        raise SystemExit(f"OPM PDB를 찾을 수 없습니다: {args.opm_pdb}")

    sidechain_template = args.sidechain_template
    if sidechain_template is None:
        sidechain_template = args.opm_pdb.with_name("3EFF-opm.pdb")
    if not sidechain_template.is_file():
        raise SystemExit(
            f"side-chain template을 찾을 수 없습니다: {sidechain_template}"
        )

    lines = args.opm_pdb.read_text(encoding="ascii").splitlines()
    template_lines = sidechain_template.read_text(encoding="ascii").splitlines()
    half_thickness = membrane_half_thickness(lines)
    chains = collect_protein(lines)
    restore_missing_sidechains(chains, collect_template(template_lines))
    ions = collect_filter_ions(lines)
    waters = collect_pore_waters(lines)
    validate_selection(chains, ions, waters, half_thickness)

    output = build_output(chains, ions, waters, half_thickness)
    args.output_pdb.parent.mkdir(parents=True, exist_ok=True)
    args.output_pdb.write_text("\n".join(output) + "\n", encoding="ascii")

    print(f"OPM KcsA 전처리 결과: {args.output_pdb}")
    print(
        "408 residues, filter K+ 7개, pore water 16개, "
        "3EFF side chain, boundary z=±15.0 A"
    )


if __name__ == "__main__":
    main()
