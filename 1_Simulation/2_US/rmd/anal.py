#!/usr/bin/env python3
"""Ratchet MD trajectory에서 순서가 유지된 umbrella seed를 선택한다."""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import tempfile
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    """Command-line argument와 tutorial 기본 경로를 읽는다."""
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="증가하는 US center에 가까운 frame을 선택해 AMBER restart로 추출합니다."
    )
    parser.add_argument(
        "--topology",
        type=Path,
        default=script_dir.parent / "work" / "system.parm7",
    )
    parser.add_argument(
        "--trajectory",
        type=Path,
        default=script_dir / "work" / "ratchet.nc",
    )
    parser.add_argument(
        "--windows",
        type=Path,
        default=script_dir.parent / "us" / "windows.tsv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=script_dir / "work" / "seeds",
    )
    parser.add_argument("--cpptraj", default="cpptraj")
    parser.add_argument(
        "--max-error",
        dest="max_error_angstrom",
        type=float,
        default=0.75,
        help="target center와 frame distance 차이의 허용치 (Å)",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_centers(path: Path) -> list[float]:
    """Window center를 읽고 양수·중복·순서를 확인한다."""
    centers: list[float] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 2:
                raise ValueError(f"{path}:{line_number}: CENTER_A FORCE 두 열이 필요합니다.")
            center = float(fields[0])
            force = float(fields[1])
            if center <= 0 or force <= 0:
                raise ValueError(f"{path}:{line_number}: center와 force는 양수여야 합니다.")
            centers.append(center)
    if not centers:
        raise ValueError(f"window center가 없습니다: {path}")
    if centers != sorted(centers) or len(centers) != len(set(centers)):
        raise ValueError("window center는 중복 없이 증가해야 합니다.")
    return centers


def run_cpptraj(executable: str, topology: Path, commands: str) -> None:
    """Command block을 cpptraj stdin으로 넘기고 실패 output을 보존한다."""
    result = subprocess.run(
        [executable, "-p", str(topology)],
        input=commands,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"cpptraj 실행에 실패했습니다: {detail}")


def calculate_distances(
    executable: str,
    topology: Path,
    trajectory: Path,
    output: Path,
) -> list[tuple[int, float]]:
    """Trajectory의 frame별 terminal Cα distance를 계산한다."""
    commands = (
        f"trajin {trajectory}\n"
        f"distance end_to_end :1@CA :10@CA out {output} noimage\n"
        "run\n"
    )
    run_cpptraj(executable, topology, commands)

    values: list[tuple[int, float]] = []
    with output.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            values.append((int(float(fields[0])), float(fields[1])))
    if not values:
        raise RuntimeError("cpptraj end-to-end distance output이 비어 있습니다.")
    return values


def select_crossings(
    values: list[tuple[int, float]],
    centers_angstrom: list[float],
    max_error_angstrom: float,
) -> list[tuple[int, float, float]]:
    """Center 순서를 유지하며 first-crossing 주변 frame을 선택한다."""
    selected: list[tuple[int, float, float]] = []
    start = 0

    for center_angstrom in centers_angstrom:
        crossing = None
        for index in range(start, len(values)):
            if values[index][1] >= center_angstrom:
                crossing = index
                break

        if crossing is None:
            candidates = range(start, len(values))
        else:
            candidates = [crossing]
            if crossing > start:
                candidates.append(crossing - 1)

        try:
            best = min(
                candidates,
                key=lambda index: abs(values[index][1] - center_angstrom),
            )
        except ValueError as exc:
            raise RuntimeError(
                f"trajectory에 {center_angstrom:.3f} Å window의 frame이 없습니다."
            ) from exc

        frame, observed = values[best]
        error = abs(observed - center_angstrom)

        if error > max_error_angstrom:
            raise RuntimeError(
                f"center {center_angstrom:.3f} Å의 허용 오차 "
                f"{max_error_angstrom:.3f} Å 안에 frame이 없습니다. "
                f"가장 가까운 ordered frame은 {frame}번, {observed:.3f} Å입니다."
            )
        selected.append((frame, observed, error))
        start = best + 1

    return selected


def extract_restarts(
    executable: str,
    topology: Path,
    trajectory: Path,
    output_dir: Path,
    selected: list[tuple[int, float, float]],
) -> None:
    """Selected frame을 window별 AMBER restart file로 추출한다."""
    commands = [f"trajin {trajectory}"]
    for window, (frame, _, _) in enumerate(selected, start=1):
        seed = output_dir / f"seed_{window:03d}.rst7"
        commands.append(f"trajout {seed} restart onlyframes {frame}")
    commands.append("run")
    run_cpptraj(executable, topology, "\n".join(commands) + "\n")

    missing = [
        output_dir / f"seed_{window:03d}.rst7"
        for window in range(1, len(selected) + 1)
        if not (output_dir / f"seed_{window:03d}.rst7").is_file()
    ]
    if missing:
        raise RuntimeError(f"cpptraj seed restart가 생성되지 않았습니다: {missing[0]}")


def write_metadata(
    path: Path,
    centers_angstrom: list[float],
    selected: list[tuple[int, float, float]],
) -> None:
    """Window target과 선택한 frame·distance·error를 TSV로 저장한다."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["window", "target_A", "frame", "observed_A", "error_A"])
        for window, (center, selection) in enumerate(
            zip(centers_angstrom, selected),
            start=1,
        ):
            frame, observed, error = selection
            writer.writerow(
                [window, f"{center:.3f}", frame, f"{observed:.6f}", f"{error:.6f}"]
            )


def main() -> int:
    args = parse_arguments()

    if not args.windows.is_file():
        raise SystemExit(f"window 설정을 찾을 수 없습니다: {args.windows}")

    if args.max_error_angstrom <= 0:
        raise SystemExit("--max-error는 0보다 커야 합니다.")

    try:
        centers_angstrom = read_centers(args.windows)
    except (OSError, ValueError) as error:
        raise SystemExit(f"window 설정 오류: {error}") from None

    if args.dry_run:
        print(f"topology: {args.topology}")
        print(f"trajectory: {args.trajectory}")
        print(f"seed output: {args.output} ({len(centers_angstrom)} windows)")
        return 0

    if shutil.which(args.cpptraj) is None:
        raise SystemExit(f"cpptraj을 찾을 수 없습니다: {args.cpptraj}")
    for path in (args.topology, args.trajectory, args.windows):
        if not path.is_file():
            raise SystemExit(f"필수 input을 찾을 수 없습니다: {path}")
    if args.output.exists():
        raise SystemExit(f"output directory가 이미 존재합니다: {args.output}")

    args.output.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory(prefix="us_seed_") as temp_dir:
            distances = Path(temp_dir) / "distance.dat"
            values = calculate_distances(
                args.cpptraj, args.topology.resolve(), args.trajectory.resolve(), distances
            )
        selected = select_crossings(
            values,
            centers_angstrom,
            args.max_error_angstrom,
        )
        extract_restarts(
            args.cpptraj,
            args.topology.resolve(),
            args.trajectory.resolve(),
            args.output.resolve(),
            selected,
        )
        write_metadata(args.output / "seeds.tsv", centers_angstrom, selected)
    except (OSError, RuntimeError, ValueError) as error:
        if args.output.exists() and not any(args.output.iterdir()):
            args.output.rmdir()
        raise SystemExit(f"오류: {error}") from None

    print(f"US seed restart {len(centers_angstrom)}개를 생성했습니다: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
