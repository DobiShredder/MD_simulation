#!/usr/bin/env python3
"""Select ordered umbrella seeds from the ratchet-MD trajectory."""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, "..")
from config_utils import load_config, positive_float, section, string_value  # noqa: E402


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract ordered first-crossing restart files for US windows."
    )
    parser.add_argument("--dry-run", action="store_true", help="validate settings without running cpptraj")
    parser.add_argument("--cpptraj", default="cpptraj", help="cpptraj executable (default: cpptraj)")
    return parser.parse_args()


def read_centers(path: Path) -> list[float]:
    centers: list[float] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 2:
                raise ValueError(f"{path}:{line_number}: expected CENTER_A FORCE")
            center = float(fields[0])
            force = float(fields[1])
            if center <= 0 or force <= 0:
                raise ValueError(f"{path}:{line_number}: center and force must be positive")
            centers.append(center)
    if not centers:
        raise ValueError(f"No umbrella windows found: {path}")
    if centers != sorted(centers) or len(centers) != len(set(centers)):
        raise ValueError("Window centers must be unique and increasing")
    return centers


def run_cpptraj(executable: str, topology: Path, commands: str) -> None:
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
    mask_1: str,
    mask_2: str,
) -> list[tuple[int, float]]:
    run_cpptraj(
        executable,
        topology,
        f"trajin {trajectory}\n"
        f"distance reaction_coordinate {mask_1} {mask_2} out {output} noimage\n"
        "run\n",
    )
    values: list[tuple[int, float]] = []
    for raw_line in output.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        values.append((int(float(fields[0])), float(fields[1])))
    if not values:
        raise RuntimeError("cpptraj reaction-coordinate output is empty")
    return values


def select_crossings(
    values: list[tuple[int, float]],
    centers: list[float],
    maximum_error: float,
) -> list[tuple[int, float, float]]:
    selected: list[tuple[int, float, float]] = []
    start = 0
    for center in centers:
        crossing = next(
            (index for index in range(start, len(values)) if values[index][1] >= center),
            None,
        )
        candidates = list(range(start, len(values))) if crossing is None else [crossing]
        if crossing is not None and crossing > start:
            candidates.append(crossing - 1)
        if not candidates:
            raise RuntimeError(f"Trajectory has no ordered frame for {center:.3f} Å")
        best = min(candidates, key=lambda index: abs(values[index][1] - center))
        frame, observed = values[best]
        error = abs(observed - center)
        if error > maximum_error:
            raise RuntimeError(
                f"No ordered frame is within {maximum_error:.3f} Å of "
                f"{center:.3f} Å; nearest is frame {frame} at {observed:.3f} Å"
            )
        selected.append((frame, observed, error))
        start = best + 1
    return selected


def extract_restarts(
    executable: str,
    topology: Path,
    trajectory: Path,
    output: Path,
    selected: list[tuple[int, float, float]],
) -> None:
    commands = [f"trajin {trajectory}"]
    for window_number, (frame, _, _) in enumerate(selected, 1):
        commands.append(
            f"trajout {output / f'seed_{window_number:03d}.rst7'} restart onlyframes {frame}"
        )
    commands.append("run")
    run_cpptraj(executable, topology, "\n".join(commands) + "\n")


def write_metadata(
    path: Path,
    centers: list[float],
    selected: list[tuple[int, float, float]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["window", "target_A", "frame", "observed_A", "error_A"])
        for window_number, (center, selection) in enumerate(zip(centers, selected), 1):
            frame, observed, error = selection
            writer.writerow(
                [window_number, f"{center:.3f}", frame, f"{observed:.6f}", f"{error:.6f}"]
            )


def main() -> int:
    args = parse_arguments()
    root = Path("..")
    config_path = root / "work/resolved_config.toml"
    topology = root / "work/system.parm7"
    trajectory = Path("work/ratchet.nc")
    output = Path("work/seeds")

    try:
        config = load_config(config_path)
        umbrella = section(config, "umbrella")
        windows = root / string_value(umbrella, "windows_file")
        centers = read_centers(windows)
        mask_1 = string_value(umbrella, "atom_mask_1")
        mask_2 = string_value(umbrella, "atom_mask_2")
        maximum_error = positive_float(umbrella, "seed_max_error")
    except (OSError, ValueError) as error:
        raise SystemExit(f"Config error: {error}") from None

    if args.dry_run:
        print(f"topology: {topology}")
        print(f"trajectory: {trajectory}")
        print(f"seed output: {output} ({len(centers)} windows)")
        return 0
    if shutil.which(args.cpptraj) is None:
        raise SystemExit(f"cpptraj not found: {args.cpptraj}")
    for path in (topology, trajectory, windows):
        if not path.is_file():
            raise SystemExit(f"Required input not found: {path}")
    if output.exists():
        raise SystemExit(f"Output directory already exists: {output}")

    output.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory(prefix="us_seed_") as temporary:
            distance_output = Path(temporary) / "distance.dat"
            values = calculate_distances(
                args.cpptraj,
                topology.resolve(),
                trajectory.resolve(),
                distance_output,
                mask_1,
                mask_2,
            )
        selected = select_crossings(values, centers, maximum_error)
        extract_restarts(
            args.cpptraj,
            topology.resolve(),
            trajectory.resolve(),
            output.resolve(),
            selected,
        )
        write_metadata(output / "seeds.tsv", centers, selected)
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"Error: {error}") from None

    print(f"Created {len(centers)} US seed restarts: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
