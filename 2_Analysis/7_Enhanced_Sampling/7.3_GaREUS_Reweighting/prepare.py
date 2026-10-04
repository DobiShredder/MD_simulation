#!/usr/bin/env python3
"""Align per-window GaREUS distances and GaMD boosts by frame."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path


TUTORIAL_DIR = Path.cwd()
SIMULATION_WORK = TUTORIAL_DIR / "../../../1_Simulation/3_REMD/3.5_GaREUS/work"
OUTPUT_DIR = TUTORIAL_DIR / "output"

GAMD_COMPONENTS = 2
RESTRAINT_FORCE_KCAL_MOL_A2 = 10.0


def read_last_column(path: Path) -> list[float]:
    values = []

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "@")):
            continue

        try:
            values.append(float(line.replace("D", "E").split()[-1]))
        except ValueError:
            continue

    if not values:
        raise ValueError(f"numeric record could not be read: {path}")

    return values


def read_boost(path: Path) -> list[float]:
    values = []

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        fields = line.replace("D", "E").split()
        if len(fields) < 6 + GAMD_COMPONENTS:
            continue

        try:
            boost = 0.0
            for component in range(GAMD_COMPONENTS):
                boost += float(fields[6 + component])
        except ValueError:
            continue

        values.append(boost)

    if not values:
        raise ValueError(f"GaMD boost record could not be read: {path}")

    return values


def read_states(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        states = list(csv.DictReader(handle, delimiter="\t"))

    if len(states) != 20:
        raise ValueError(f"Expected 20 GaREUS states, found {len(states)}")

    return states


def prepare_window(replica: str, replica_dir: Path, output_file: Path) -> int:
    rows = []
    frame = 1
    segment = 1

    distance_file = replica_dir / "restraint.production.dat"
    boost_file = replica_dir / "gamd.production.log"

    if not distance_file.is_file():
        raise ValueError(f"restraint output not found: {distance_file}")
    if not boost_file.is_file():
        raise ValueError(f"GaMD log not found: {boost_file}")

    distances = read_last_column(distance_file)
    boosts = read_boost(boost_file)
    if len(distances) != len(boosts):
        raise ValueError(
            f"replica {replica}, segment {segment:03d}: distance and boost record "
            f"counts differ ({len(distances)} != {len(boosts)})."
        )

    for distance, boost in zip(distances, boosts):
        rows.append([frame, segment, f"{distance:.8f}", f"{boost:.8f}"])
        frame += 1

    with output_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["frame", "segment", "distance_A", "boost_kcal_mol"])
        writer.writerows(rows)

    return len(rows)



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


def prepare_inputs(simulation_work: Path, output_dir: Path) -> int:
    with result_generation(output_dir) as generation_dir:
        states = read_states(simulation_work / "states.tsv")
        series_dir = generation_dir / "series"
        series_dir.mkdir(parents=True, exist_ok=True)

        summary = [["window", "center_A", "amber_rk_kcal_mol_A2", "frames"]]

        for state in states:
            replica = state["replica"]
            replica_dir = simulation_work / replica
            frames = prepare_window(
                replica,
                replica_dir,
                series_dir / f"window_{replica}.tsv",
            )
            summary.append(
                [
                    replica,
                    state["window_center_A"],
                    f"{RESTRAINT_FORCE_KCAL_MOL_A2:.6f}",
                    frames,
                ]
            )

        with (generation_dir / "summary.tsv").open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t").writerows(summary)

        window_count = len(states)
    return window_count


def main() -> None:
    print(f"Preparing GaREUS inputs: {SIMULATION_WORK} -> {OUTPUT_DIR}")
    try:
        state_count = prepare_inputs(SIMULATION_WORK, OUTPUT_DIR)
    except (OSError, KeyError, ValueError) as error:
        raise SystemExit(f"GaREUS input preparation failed: {error}") from error

    print(f"Organized distances and boosts for {state_count} GaREUS states: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
