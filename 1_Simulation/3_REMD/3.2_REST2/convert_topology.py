#!/usr/bin/env python3
"""AMBER topology와 restart file을 GROMACS 형식으로 변환합니다."""

from __future__ import annotations

import argparse
from pathlib import Path

import parmed


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
    structure.save(str(args.output_topology), overwrite=True)
    structure.save(str(args.output_coordinates), overwrite=True)

    print(
        "GROMACS 변환 결과: "
        f"{args.output_topology}, {args.output_coordinates}"
    )


if __name__ == "__main__":
    main()

