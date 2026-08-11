#!/usr/bin/env python3
"""AMBER topology와 restart file을 GROMACS 형식으로 변환합니다."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

import parmed


def preserve_residue_specific_cmaps(structure: parmed.Structure) -> int:
    """ff19SB CMAP마다 별도의 C-alpha atom type을 지정합니다."""
    cmap_names: dict[int, str] = {}
    atom_names: dict[int, str] = {}

    for cmap in structure.cmaps:
        cmap_key = id(cmap.type)
        cmap_name = cmap_names.setdefault(cmap_key, f"XC{len(cmap_names)}")
        atom_key = id(cmap.atom3)

        if atom_key in atom_names and atom_names[atom_key] != cmap_name:
            raise SystemExit("하나의 C-alpha atom에 서로 다른 CMAP이 지정되어 있습니다.")

        if atom_key not in atom_names:
            cmap.atom3.atom_type = copy.copy(cmap.atom3.atom_type)
            cmap.atom3.atom_type.name = cmap_name
            cmap.atom3.type = cmap_name
            atom_names[atom_key] = cmap_name

    if structure.cmaps and len(cmap_names) < 2:
        raise SystemExit("ff19SB residue-specific CMAP을 분리하지 못했습니다.")

    return len(cmap_names)


def normalize_cmap_spacing(path: Path) -> None:
    """GROMACS 2025.0이 읽을 수 있도록 cmaptypes의 공백을 정규화합니다."""
    lines = path.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    section = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[] ").lower()

        if section == "cmaptypes" and stripped and not stripped.startswith(";"):
            line = " ".join(stripped.replace("\\", " \\ ").split())

        output.append(line)

    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("topology", type=Path)
    parser.add_argument("coordinates", type=Path)
    parser.add_argument("output_topology", type=Path)
    parser.add_argument("output_coordinates", type=Path)
    args = parser.parse_args()

    for path in (args.topology, args.coordinates):
        if not path.is_file():
            raise SystemExit(f"입력 파일을 찾을 수 없습니다: {path}")

    structure = parmed.load_file(str(args.topology), xyz=str(args.coordinates))
    cmap_count = preserve_residue_specific_cmaps(structure)
    structure.save(str(args.output_topology), overwrite=True)
    structure.save(str(args.output_coordinates), overwrite=True)
    normalize_cmap_spacing(args.output_topology)

    print(
        "GROMACS 변환 결과: "
        f"{args.output_topology}, {args.output_coordinates} "
        f"(CMAP types: {cmap_count})"
    )


if __name__ == "__main__":
    main()
