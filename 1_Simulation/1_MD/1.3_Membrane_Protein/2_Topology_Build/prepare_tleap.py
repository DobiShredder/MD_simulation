#!/usr/bin/env python3
"""Apply the coordinate PDB box and water count to the tleap input."""

from __future__ import annotations

import argparse
from pathlib import Path


SALT_CONCENTRATION_M = 0.15
WATER_CONCENTRATION_M = 55.5


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("coordinate_pdb", type=Path)
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    return parser.parse_args()


def read_box_and_water_count(path: Path) -> tuple[tuple[float, float, float], int]:
    box = None
    water_count = 0

    for line in path.read_text(encoding="ascii").splitlines():
        if line.startswith("CRYST1"):
            box = (
                float(line[6:15]),
                float(line[15:24]),
                float(line[24:33]),
            )
        if (
            line.startswith(("ATOM  ", "HETATM"))
            and line[17:20] == "WAT"
            and line[12:16].strip() == "O"
        ):
            water_count += 1

    if box is None:
        raise SystemExit("Coordinate PDB is missing a CRYST1 box record.")
    if water_count == 0:
        raise SystemExit("Coordinate PDB contains no WAT oxygen atoms.")

    return box, water_count


def main() -> None:
    args = parse_arguments()
    box, water_count = read_box_and_water_count(args.coordinate_pdb)
    salt_pairs = round(water_count * SALT_CONCENTRATION_M / WATER_CONCENTRATION_M)
    text = args.template.read_text(encoding="ascii")
    text = text.replace("BOX_X", f"{box[0]:.3f}")
    text = text.replace("BOX_Y", f"{box[1]:.3f}")
    text = text.replace("BOX_Z", f"{box[2]:.3f}")
    text = text.replace("SALT_PAIRS", str(salt_pairs))
    args.output.write_text(text, encoding="ascii")

    print(
        f"Box={box[0]:.3f}x{box[1]:.3f}x{box[2]:.3f} A, "
        f"WAT={water_count}, KCl pairs={salt_pairs}"
    )


if __name__ == "__main__":
    main()
