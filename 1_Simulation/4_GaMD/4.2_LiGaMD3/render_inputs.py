#!/usr/bin/env python3
"""Find the LiGaMD3 receptor atom range in the final topology and generate inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import parmed


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("topology", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("template_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    structure = parmed.load_file(str(args.topology))
    labels = [residue.name for residue in structure.residues]

    ben_indices = [index for index, label in enumerate(labels) if label == "BEN"]
    if len(ben_indices) != 1:
        raise SystemExit(f"Expected exactly one BEN residue, found {ben_indices}")
    ben_index = ben_indices[0]
    receptor_first_atom = 1
    receptor_last_atom = structure.residues[ben_index].atoms[0].idx

    metadata = dict(
        line.split("\t", 1)
        for line in args.metadata.read_text(encoding="utf-8").splitlines()[1:]
        if line
    )
    if ben_index != int(metadata["receptor_residues"]):
        raise SystemExit("Receptor residue count before BEN differs from the preparation metadata.")

    args.output_directory.mkdir(parents=True, exist_ok=True)
    replacements = {
        "@RECEPTOR_FIRST_ATOM@": str(receptor_first_atom),
        "@RECEPTOR_LAST_ATOM@": str(receptor_last_atom),
    }
    for name in ("gamd_prepare.in", "production.in"):
        template = (args.template_directory / f"{name}.template").read_text(encoding="utf-8")
        for marker, value in replacements.items():
            template = template.replace(marker, value)
        (args.output_directory / name).write_text(template, encoding="utf-8")

    metadata["receptor_first_atom"] = str(receptor_first_atom)
    metadata["receptor_last_atom"] = str(receptor_last_atom)
    (args.output_directory.parent / "system_metadata.tsv").write_text(
        "key\tvalue\n" + "".join(f"{key}\t{value}\n" for key, value in metadata.items()),
        encoding="utf-8",
    )
    print(f"LiGaMD3 receptor atoms: {receptor_first_atom}-{receptor_last_atom}")


if __name__ == "__main__":
    main()
