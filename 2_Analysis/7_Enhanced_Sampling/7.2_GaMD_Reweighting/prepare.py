#!/usr/bin/env python3
"""GaMD profile과 simulation metadata로 cpptraj CV input을 생성합니다."""

from __future__ import annotations

import argparse
from pathlib import Path


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=("chignolin", "ligamd3", "pepgamd"))
    parser.add_argument("simulation_work", type=Path)
    parser.add_argument("output_input", type=Path)
    return parser.parse_args()


def metadata(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SystemExit(f"system metadata를 찾을 수 없습니다: {path}")
    return dict(
        line.split("\t", 1)
        for line in path.read_text(encoding="utf-8").splitlines()[1:]
        if line
    )


def main() -> None:
    args = arguments()
    work = args.simulation_work.resolve()
    topology = work / "system.parm7"
    if not topology.is_file():
        raise SystemExit(f"topology를 찾을 수 없습니다: {topology}")

    trajectories = [work / f"production.{segment:03d}.nc" for segment in range(1, 11)]
    missing = [path for path in trajectories if not path.is_file()]
    if missing:
        raise SystemExit(f"production trajectory를 찾을 수 없습니다: {missing[0]}")

    lines = [f'parm "{topology}"']
    lines.extend(f'trajin "{path}"' for path in trajectories)
    lines.append("autoimage")

    cv_output = args.output_input.parent / "cv.dat"
    if args.profile == "chignolin":
        lines.append(f'distance cv :1@CA :10@CA out "{cv_output}"')
    elif args.profile == "ligamd3":
        values = metadata(work / "system_metadata.tsv")
        asp189 = values["asp189_residue"]
        lines.append(
            f'distance cv :BEN&!@H= :{asp189}@OD1,OD2 out "{cv_output}"'
        )
    else:
        values = metadata(work / "system_metadata.tsv")
        receptor_end = values["receptor_residues"]
        peptide_start = values["peptide_start_residue"]
        peptide_end = values["peptide_end_residue"]
        lines.append(f"rms receptor first :1-{receptor_end}@CA,C,N")
        lines.append(
            f'rms peptide first :{peptide_start}-{peptide_end}@CA,C,N nofit out "{cv_output}"'
        )

    lines.extend(["run", "quit"])
    args.output_input.parent.mkdir(parents=True, exist_ok=True)
    args.output_input.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"cpptraj input: {args.output_input}")


if __name__ == "__main__":
    main()
