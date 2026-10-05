#!/usr/bin/env python3
"""Prepare checkpoint continuation inputs and publish GROMACS part outputs."""

import argparse
import math
from pathlib import Path
import re
import subprocess

PART_OUTPUTS = ("gro", "log", "edr", "xtc", "trr")


def mdp_timing(path):
    values = {}
    for line in path.read_text().splitlines():
        content = line.split(";", 1)[0]
        if "=" not in content:
            continue
        name, value = content.split("=", 1)
        name = name.strip().lower().replace("_", "-")
        if name in ("nsteps", "dt", "init-step", "tinit"):
            if name in values:
                raise ValueError(f"Repeated {name} in {path}")
            values[name] = value.strip()
    try:
        steps = int(values["nsteps"])
        timestep = float(values["dt"])
        initial_step = int(values.get("init-step", "0"))
        initial_time = float(values.get("tinit", "0"))
    except (KeyError, ValueError) as error:
        raise ValueError(f"Invalid production timing input: {path}: {error}") from None
    if steps < 1 or initial_step < 0 or not math.isfinite(timestep) or timestep <= 0:
        raise ValueError(f"Invalid production step count or timestep: {path}")
    if not math.isfinite(initial_time):
        raise ValueError(f"Nonfinite tinit: {path}")
    return steps, timestep, initial_step, initial_time


def checkpoint_timing(gromacs, checkpoint):
    result = subprocess.run([gromacs, "dump", "-cp", str(checkpoint)],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"Checkpoint inspection failed: {checkpoint}\n{result.stderr[-1500:]}")
    text = result.stdout + result.stderr
    values = {}
    for name in ("step", "t", "simulation part #"):
        match = re.search(r"^\s*" + re.escape(name) + r"\s*=\s*(\S+)\s*$", text, re.MULTILINE)
        if match is None:
            raise ValueError(f"Checkpoint has no {name} field: {checkpoint}")
        values[name] = match[1]
    time_ps = float(values["t"])
    if not math.isfinite(time_ps):
        raise ValueError(f"Nonfinite checkpoint time: {checkpoint}")
    return int(values["step"]), time_ps, int(values["simulation part #"])


def prepare_segment(directory, segment, gromacs):
    stage = f"production.{segment:03d}"
    source = directory / "production.mdp"
    target = directory / f"{stage}.mdp"
    steps, timestep, initial_step, initial_time = mdp_timing(source)
    next_step = initial_step + (segment - 1) * steps
    next_time = initial_time + next_step * timestep
    checkpoint = directory / f"production.{segment - 1:03d}.cpt"
    previous_step, previous_time, previous_part = checkpoint_timing(gromacs, checkpoint)
    if (previous_step != next_step or previous_part != segment - 1
            or not math.isclose(previous_time, next_time, rel_tol=1e-6, abs_tol=1e-6)):
        raise ValueError(
            f"{stage}: predecessor checkpoint does not continue this schedule: {checkpoint}; "
            f"expected step={next_step}, time={next_time:g} ps, part={segment - 1}; "
            f"found step={previous_step}, time={previous_time:g} ps, part={previous_part}. "
            "Existing files were preserved. Use a new work directory for a changed schedule."
        )
    lines = []
    for line in source.read_text().splitlines(keepends=True):
        key = line.split(";", 1)[0].split("=", 1)[0].strip().lower().replace("_", "-")
        if key != "init-step":
            lines.append(line)
    content = "".join(lines).rstrip("\n") + f"\ninit-step = {next_step}\n"
    if target.exists():
        if target.read_text() != content:
            raise ValueError(f"{stage}: generated input changed: {target}. Existing input was preserved.")
        return
    identity = directory.parent / f".{stage}.complete.identity.json"
    marker = directory.parent / f".{stage}.complete"
    existing = [path for path in directory.glob(f"{stage}.*") if path.suffix != ".mdp"]
    if identity.exists() or marker.exists() or existing:
        raise ValueError(f"{stage}: generated input is missing while stage state exists: {target}. Files were preserved.")
    with target.open("x") as handle:
        handle.write(content)


def publish_segment(directory, segment, gromacs):
    stage = f"production.{segment:03d}"
    part = f"part{segment:04d}"
    coordinates = directory / (f"{stage}.{part}.gro" if segment > 1 else f"{stage}.gro")
    checkpoint = directory / f"{stage}.cpt"
    for path in (coordinates, checkpoint):
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"{stage}: required continuation output is missing or empty: {path}")
    steps, timestep, initial_step, initial_time = mdp_timing(directory / "production.mdp")
    expected_step = initial_step + segment * steps
    expected_time = initial_time + expected_step * timestep
    step, time_ps, simulation_part = checkpoint_timing(gromacs, checkpoint)
    if (step != expected_step or simulation_part != segment
            or not math.isclose(time_ps, expected_time, rel_tol=1e-6, abs_tol=1e-6)):
        raise ValueError(
            f"{stage}: incomplete production checkpoint: {checkpoint}; "
            f"expected step={expected_step}, time={expected_time:g} ps, part={segment}; "
            f"found step={step}, time={time_ps:g} ps, part={simulation_part}. Outputs were preserved."
        )
    if segment == 1:
        return
    outputs = []
    for suffix in PART_OUTPUTS:
        source = directory / f"{stage}.{part}.{suffix}"
        target = directory / f"{stage}.{suffix}"
        if source.exists():
            if target.exists():
                raise ValueError(f"{stage}: refusing to replace existing output: {target}")
            outputs.append((source, target))
    for source, target in outputs:
        source.rename(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "publish"),
                        help="Prepare continuation input or publish completed segment outputs")
    parser.add_argument("directory", type=Path, help="Replica directory")
    parser.add_argument("segment", type=int, help="Production segment index, starting at 1")
    parser.add_argument("--gromacs", required=True, help="GROMACS executable for checkpoint inspection")
    args = parser.parse_args()
    if args.segment < 1 or (args.operation == "prepare" and args.segment < 2):
        parser.error("publish requires segment >= 1; prepare requires segment >= 2")
    try:
        if args.operation == "prepare":
            prepare_segment(args.directory, args.segment, args.gromacs)
        else:
            publish_segment(args.directory, args.segment, args.gromacs)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Error: production.{args.segment:03d} {args.operation} failed: {error}\n")


if __name__ == "__main__":
    main()
