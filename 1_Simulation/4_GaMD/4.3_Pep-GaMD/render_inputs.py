#!/usr/bin/env python3
"""1CKB preparation metadata로 Pep-GaMD mask를 채웁니다."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", type=Path)
    parser.add_argument("template_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()

    metadata = dict(
        line.split("\t", 1)
        for line in args.metadata.read_text(encoding="utf-8").splitlines()[1:]
        if line
    )
    start = int(metadata["peptide_start_residue"])
    end = int(metadata["peptide_end_residue"])
    if metadata["peptide_sequence"] != "PPPVPPRR" or end - start + 1 != 8:
        raise SystemExit("Pep-GaMD peptide metadata가 PPPVPPRR 8 residues와 다릅니다.")

    mask = f":{start}-{end}"
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for name in ("gamd_prepare.in", "production.in"):
        text = (args.template_directory / f"{name}.template").read_text(encoding="utf-8")
        (args.output_directory / name).write_text(
            text.replace("@PEPTIDE_MASK@", mask), encoding="utf-8"
        )
    print(f"Pep-GaMD peptide mask: {mask}")


if __name__ == "__main__":
    main()
