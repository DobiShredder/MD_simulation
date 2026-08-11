#!/usr/bin/env python3
"""Select ordered umbrella seeds from a ratchet MD trajectory."""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import tempfile
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments and tutorial default paths."""
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Select frames near increasing US centers and extract AMBER restart files."
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
        help="Tolerance for the difference between the target center and frame distance (Å)",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_centers(path: Path) -> list[float]:
    """Read window centers and validate positivity, uniqueness, and order."""
    centers: list[float] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 2:
                raise ValueError(f"{path}:{line_number}: expected two columns: CENTER_A FORCE.")
            center = float(fields[0])
            force = float(fields[1])
            if center <= 0 or force <= 0:
                raise ValueError(f"{path}:{line_number}: center and force must be positive.")
            centers.append(center)
    if not centers:
        raise ValueError(f"window center is missing: {path}")
    if centers != sorted(centers) or len(centers) != len(set(centers)):
        raise ValueError("Window centers must be unique and increasing.")
    return centers


def run_cpptraj(executable: str, topology: Path, commands: str) -> None:
    """Pass a command block to cpptraj stdin and preserve failure output."""
    result = subprocess.run(
        [executable, "-p", str(topology)],
        input=commands,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"cpptraj failed: {detail}")


def calculate_distances(
    executable: str,
    topology: Path,
    trajectory: Path,
    output: Path,
) -> list[tuple[int, float]]:
    """Calculate the terminal C-alpha distance for each trajectory frame."""
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
        raise RuntimeError("cpptraj end-to-end distance output is empty.")
    return values


def select_crossings(
    values: list[tuple[int, float]],
    centers_angstrom: list[float],
    max_error_angstrom: float,
) -> list[tuple[int, float, float]]:
    """Select frames near first crossings while preserving center order."""
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
                f"Trajectory has no frame for the {center_angstrom:.3f} Å window."
            ) from exc

        frame, observed = values[best]
        error = abs(observed - center_angstrom)

        if error > max_error_angstrom:
            raise RuntimeError(
                f"No frame is within the {max_error_angstrom:.3f} Å tolerance of "
                f"center {center_angstrom:.3f} Å. The nearest ordered frame is "
                f"{frame} at {observed:.3f} Å."
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
    """Extract selected frames as per-window AMBER restart files."""
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
        raise RuntimeError(f"cpptraj seed restart was not created: {missing[0]}")


def write_metadata(
    path: Path,
    centers_angstrom: list[float],
    selected: list[tuple[int, float, float]],
) -> None:
    """Write window targets, selected frames, distances, and errors as TSV."""
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
        raise SystemExit(f"window settings not found: {args.windows}")

    if args.max_error_angstrom <= 0:
        raise SystemExit("--max-error must be greater than zero.")

    try:
        centers_angstrom = read_centers(args.windows)
    except (OSError, ValueError) as error:
        raise SystemExit(f"window settings Error: {error}") from None

    if args.dry_run:
        print(f"topology: {args.topology}")
        print(f"trajectory: {args.trajectory}")
        print(f"seed output: {args.output} ({len(centers_angstrom)} windows)")
        return 0

    if shutil.which(args.cpptraj) is None:
        raise SystemExit(f"cpptraj not found: {args.cpptraj}")
    for path in (args.topology, args.trajectory, args.windows):
        if not path.is_file():
            raise SystemExit(f"Required input not found: {path}")
    if args.output.exists():
        raise SystemExit(f"Output directory already exists: {args.output}")

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
        raise SystemExit(f"Error: {error}") from None

    print(f"Created {len(centers_angstrom)} US seed restarts: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
