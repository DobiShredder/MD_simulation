#!/usr/bin/env python3
"""Prepare per-window distance series from AMBER DUMPAVE files."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


TUTORIAL_DIR = Path.cwd()
WINDOWS_DIR = TUTORIAL_DIR / "../../../1_Simulation/2_US/us/work"
OUTPUT_DIR = TUTORIAL_DIR / "output"

TIME_COLUMN = 1
DISTANCE_COLUMN = 8
DISCARD_PS = 100.0


@dataclass(frozen=True)
class Window:
    name: str
    center_angstrom: float
    amber_force: float
    directory: Path


def read_window(directory: Path) -> Window:
    metadata = directory / "window.tsv"
    if not metadata.is_file():
        raise ValueError(f"window metadata not found: {metadata}")

    with metadata.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    if len(rows) != 1:
        raise ValueError(f"Invalid window metadata format: {metadata}")

    row = rows[0]
    return Window(
        name=row["window"],
        center_angstrom=float(row["center_A"]),
        amber_force=float(row["force_kcal_mol_A2"]),
        directory=directory,
    )


def discover_windows(root: Path) -> list[Window]:
    windows = []
    for directory in sorted(root.glob("[0-9][0-9][0-9]")):
        if directory.is_dir():
            windows.append(read_window(directory))

    if not windows:
        raise ValueError(f"umbrella window not found: {root}")

    centers = [window.center_angstrom for window in windows]
    if centers != sorted(centers) or len(centers) != len(set(centers)):
        raise ValueError("Window centers must be unique and increasing.")

    return windows


def read_dumpave(path: Path) -> list[tuple[float, float]]:
    required_columns = max(TIME_COLUMN, DISTANCE_COLUMN)
    values = []

    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith(("#", "@")):
                continue

            fields = line.replace("D", "E").split()
            if len(fields) < required_columns:
                continue

            try:
                time_ps = float(fields[TIME_COLUMN - 1])
                distance_angstrom = float(fields[DISTANCE_COLUMN - 1])
            except ValueError:
                continue

            values.append((time_ps, distance_angstrom))

    if not values:
        raise ValueError(f"DUMPAVE numeric record could not be read: {path}")

    return values



def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record_generation(directory: Path) -> None:
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != ".generation.json":
            files[str(path.relative_to(directory))] = file_digest(path)
    if not files:
        raise ValueError(f"No analysis outputs were created: {directory}")
    record = {"generation": uuid.uuid4().hex, "files": files}
    (directory / ".generation.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )


def verify_generation(directory: Path) -> str:
    pending = directory.with_name(f".{directory.name}.pending")
    if pending.exists():
        raise ValueError(f"Analysis publication is incomplete: {pending}")
    marker = directory / ".generation.json"
    try:
        record = json.loads(marker.read_text(encoding="utf-8"))
        generation = record["generation"]
        files = record["files"]
        if not isinstance(generation, str) or not generation:
            raise ValueError("invalid generation identifier")
        if not isinstance(files, dict) or not files:
            raise ValueError("missing output hashes")
        actual = {
            str(path.relative_to(directory))
            for path in directory.rglob("*")
            if path.is_file() and path.name != ".generation.json"
        }
        if set(files) != actual:
            raise ValueError("output set differs from the completed generation")
        for name, expected in files.items():
            if file_digest(directory / name) != expected:
                raise ValueError(f"output hash differs: {directory / name}")
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Incomplete or mixed analysis generation: {marker}; "
            f"run ./run.sh again. {error}"
        ) from error
    if pending.exists() or marker.read_text(encoding="utf-8") != json.dumps(record, indent=2) + "\n":
        raise ValueError(f"Analysis generation changed while reading: {directory}")
    return generation


@contextmanager
def result_generation(output_dir: Path):
    pending = output_dir.with_name(f".{output_dir.name}.pending")
    if pending.exists():
        raise ValueError(f"Analysis publication is incomplete; inspect {pending}")
    if output_dir.is_symlink():
        raise ValueError(f"Analysis output must be a directory, not a symlink: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.generation-", dir=output_dir.parent))
    stage = temporary / "new"
    previous = temporary / "previous"
    stage.mkdir()
    owns_pending = False
    retain_backup = False
    try:
        yield stage
        record_generation(stage)
        verify_generation(stage)
        with pending.open("x", encoding="utf-8") as handle:
            owns_pending = True
            handle.write(f"Previous results: {previous}\nNew results: {stage}\n")
        if output_dir.exists():
            output_dir.rename(previous)
        stage.rename(output_dir)
        pending.unlink()
        owns_pending = False
    except BaseException:
        if owns_pending:
            try:
                if not stage.exists() and output_dir.exists():
                    output_dir.rename(stage)
                if previous.exists():
                    previous.rename(output_dir)
                pending.unlink()
            except OSError:
                retain_backup = True
                print(f"Error: publication rollback failed; preserve and inspect {temporary} and {pending}", file=sys.stderr)
        raise
    finally:
        if not retain_backup:
            shutil.rmtree(temporary)


def copy_prepared_inputs(output_dir: Path, stage: Path) -> None:
    generation = verify_generation(output_dir)
    shutil.copy2(output_dir / "summary.tsv", stage / "summary.tsv")
    shutil.copytree(output_dir / "series", stage / "series")
    if verify_generation(output_dir) != generation:
        raise ValueError(f"Prepared inputs changed while copying: {output_dir}")
    record_generation(stage)
    verify_generation(stage)


def prepare_windows(windows_dir: Path, output_dir: Path) -> int:
    with result_generation(output_dir) as generation_dir:
        windows = discover_windows(windows_dir)
        series_dir = generation_dir / "series"
        series_dir.mkdir(parents=True, exist_ok=True)

        summary_rows = [
            [
                "window",
                "center_A",
                "amber_rk_kcal_mol_A2",
                "frames",
                "first_time_ps",
                "last_time_ps",
            ]
        ]

        for window in windows:
            source = window.directory / "distance.dat"
            if not source.is_file():
                raise ValueError(f"DUMPAVE output not found: {source}")

            values = read_dumpave(source)
            first_production_time = values[0][0] + DISCARD_PS
            kept = []
            for time_ps, distance_angstrom in values:
                if time_ps >= first_production_time:
                    kept.append((time_ps, distance_angstrom))

            if not kept:
                raise ValueError(f"No frames remain after discarding data: {source}")

            series_file = series_dir / f"window_{window.name}.dat"
            with series_file.open("w", encoding="utf-8") as handle:
                handle.write("time_ps\tdistance_A\n")
                for time_ps, distance_angstrom in kept:
                    handle.write(f"{time_ps:.6f}\t{distance_angstrom:.8f}\n")

            summary_rows.append(
                [
                    window.name,
                    f"{window.center_angstrom:.6f}",
                    f"{window.amber_force:.6f}",
                    str(len(kept)),
                    f"{kept[0][0]:.6f}",
                    f"{kept[-1][0]:.6f}",
                ]
            )

        with (generation_dir / "summary.tsv").open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t").writerows(summary_rows)

        window_count = len(windows)
    return window_count


def main() -> None:
    from writer_guard import protect_python_entry
    protect_python_entry("output", writes=(OUTPUT_DIR,))
    print(f"Preparing WHAM inputs: {WINDOWS_DIR} -> {OUTPUT_DIR}")
    try:
        window_count = prepare_windows(WINDOWS_DIR, OUTPUT_DIR)
    except (OSError, KeyError, ValueError) as error:
        raise SystemExit(f"WHAM input preparation failed: {error}") from error

    print(f"Organized {window_count} windows: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
