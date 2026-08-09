#!/usr/bin/env python3
"""WT-MetaD segment와 sampling 범위를 요약한다."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np


def read_colvar(path: Path) -> dict[str, np.ndarray]:
    fields = None
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#! FIELDS"):
            fields = line.split()[2:]
        elif line and not line.startswith("#"):
            rows.append([float(value) for value in line.split()])
    if fields is None or not rows:
        raise ValueError(f"COLVAR header 또는 data가 없습니다: {path}")
    data = np.asarray(rows, dtype=float)
    return {name: data[:, index] for index, name in enumerate(fields)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", nargs="?", type=Path, default=Path(__file__).parent / "work")
    parser.add_argument(
        "--skip-fes",
        action="store_true",
        help="plumed sum_hills를 실행하지 않고 diagnostic TSV만 만듭니다.",
    )
    args = parser.parse_args()

    segment_dirs = sorted((args.work_dir / "production").glob("[0-9][0-9][0-9]"))
    if len(segment_dirs) != 10:
        raise ValueError(
            f"완료된 production segment가 10개가 아닙니다: {len(segment_dirs)}"
        )

    output_dir = args.work_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    all_phi = []
    all_psi = []

    for segment_dir in segment_dirs:
        values = read_colvar(segment_dir / "COLVAR")
        required = {"time", "phi", "psi", "metad.bias", "metad.rbias"}
        if not required.issubset(values):
            raise ValueError(f"COLVAR field가 부족합니다: {segment_dir / 'COLVAR'}")
        if np.any(np.diff(values["time"]) <= 0):
            raise ValueError(
                f"segment 내부 time이 증가하지 않습니다: {segment_dir.name}"
            )

        phi = values["phi"]
        psi = values["psi"]
        bias = values["metad.bias"]
        all_phi.append(phi)
        all_psi.append(psi)
        summaries.append((
            segment_dir.name,
            len(phi),
            phi.min(),
            phi.max(),
            psi.min(),
            psi.max(),
            bias.min(),
            bias.max(),
        ))

    with (output_dir / "segment_summary.tsv").open("w", encoding="utf-8") as handle:
        handle.write(
            "segment\tframes\tphi_min\tphi_max\tpsi_min\tpsi_max\t"
            "bias_min_kj_mol\tbias_max_kj_mol\n"
        )
        for row in summaries:
            handle.write("\t".join(map(str, row)) + "\n")

    phi = np.concatenate(all_phi)
    psi = np.concatenate(all_psi)
    phi_crossings = int(np.count_nonzero(np.signbit(phi[1:]) != np.signbit(phi[:-1])))
    psi_crossings = int(np.count_nonzero(np.signbit(psi[1:]) != np.signbit(psi[:-1])))
    with (output_dir / "sampling_summary.tsv").open("w", encoding="utf-8") as handle:
        handle.write(
            "frames\tphi_min\tphi_max\tpsi_min\tpsi_max\t"
            "phi_zero_crossings\tpsi_zero_crossings\n"
        )
        handle.write(
            f"{len(phi)}\t{phi.min()}\t{phi.max()}\t{psi.min()}\t{psi.max()}\t"
            f"{phi_crossings}\t{psi_crossings}\n"
        )

    if not args.skip_fes:
        plumed = os.environ.get("PLUMED", "plumed")
        if shutil.which(plumed) is None:
            message = (
                f"plumed를 찾을 수 없습니다: {plumed}. "
                "--skip-fes로 TSV만 만들 수 있습니다."
            )
            raise FileNotFoundError(message)
        for segment_number in (1, 5, 10):
            hills = args.work_dir / "production" / f"{segment_number:03d}" / "HILLS"
            output = output_dir / f"fes.{segment_number:03d}.dat"
            command = [
                plumed,
                "sum_hills",
                "--hills",
                str(hills),
                "--outfile",
                str(output),
                "--mintozero",
            ]
            subprocess.run(command, check=True)

    print(f"WT-MetaD 진단 결과: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
