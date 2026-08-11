#!/usr/bin/env python3
"""GROMACS topology의 ff19SB CMAP type과 energy grid를 scaling합니다."""

from __future__ import annotations

import argparse
from pathlib import Path


def section_bounds(lines: list[str], name: str) -> tuple[int, int]:
    start = -1

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not (stripped.startswith("[") and stripped.endswith("]")):
            continue

        section = stripped.strip("[] ").lower()
        if section == name:
            start = index
            continue

        if start >= 0:
            return start, index

    if start >= 0:
        return start, len(lines)

    raise ValueError(f"[{name}] section을 찾지 못했습니다.")


def scaled_cmap_section(
    lines: list[str], scale: float, type_prefix: str, type_suffix: str
) -> tuple[list[str], int]:
    start, end = section_bounds(lines, "cmaptypes")
    output = ["[ cmaptypes ]\n"]
    remaining = 0
    map_count = 0

    for line in lines[start + 1 : end]:
        stripped = line.strip()

        if not stripped or stripped.startswith(";"):
            output.append(line if line.endswith("\n") else line + "\n")
            continue

        fields = stripped.replace("\\", " \\ ").split()
        is_header = (
            len(fields) >= 8
            and fields[5].isdigit()
            and fields[6].isdigit()
            and fields[7].isdigit()
        )
        if is_header:
            if remaining:
                raise ValueError("CMAP grid가 끝나기 전에 다음 header가 나타났습니다.")

            atom_types = []
            for name in fields[:5]:
                atom_type, separator, residue_type = name.partition("-")
                marked_type = f"{type_prefix}{atom_type}{type_suffix}"
                atom_types.append(
                    f"{marked_type}{separator}{residue_type}" if separator else marked_type
                )
            remaining = int(fields[6]) * int(fields[7])
            map_count += 1
            output.append(" ".join(atom_types + fields[5:]) + "\n")
            continue

        if remaining == 0:
            raise ValueError(f"CMAP header가 아닌 값을 해석할 수 없습니다: {stripped}")

        values: list[str] = []
        continuation = False
        for field in fields:
            if field == "\\":
                continuation = True
                continue
            if remaining == 0:
                raise ValueError("CMAP grid 값이 예상한 개수보다 많습니다.")
            values.append(f"{float(field) * scale:.12g}")
            remaining -= 1

        if continuation:
            values.append("\\")
        output.append(" ".join(values) + "\n")

    if remaining:
        raise ValueError(f"CMAP grid 값 {remaining}개가 부족합니다.")
    if map_count == 0:
        raise ValueError("CMAP map을 찾지 못했습니다.")

    return output, map_count


def install_scaled_cmap(
    source: Path,
    target: Path,
    scale: float,
    type_prefix: str = "",
    type_suffix: str = "",
) -> int:
    source_lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    target_lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    cmap_lines, map_count = scaled_cmap_section(
        source_lines, scale, type_prefix, type_suffix
    )

    try:
        start, end = section_bounds(target_lines, "cmaptypes")
        output = target_lines[:start] + cmap_lines + target_lines[end:]
    except ValueError:
        insert_at, _ = section_bounds(target_lines, "moleculetype")
        output = target_lines[:insert_at] + cmap_lines + ["\n"] + target_lines[insert_at:]

    target.write_text("".join(output), encoding="utf-8")
    return map_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("scale", type=float)
    parser.add_argument("--type-prefix", default="")
    parser.add_argument("--type-suffix", default="")
    args = parser.parse_args()

    count = install_scaled_cmap(
        args.source,
        args.target,
        args.scale,
        args.type_prefix,
        args.type_suffix,
    )
    print(f"CMAP {count}개를 scaling했습니다: {args.target}")


if __name__ == "__main__":
    main()
