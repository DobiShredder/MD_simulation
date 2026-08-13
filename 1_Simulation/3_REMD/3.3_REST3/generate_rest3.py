#!/usr/bin/env python3
"""Generate ssREST3 topologies from a fixed temperature/kappa table."""

from __future__ import annotations

import argparse
import csv
import contextlib
import importlib
import importlib.util
import io
import math
import os
import shutil
from pathlib import Path
from types import ModuleType

from scale_cmap import install_scaled_cmap


def use_full_precision_nonbonded_output(module: ModuleType) -> ModuleType:
    """Replace the four-decimal solvent override writer in parser 0.2.2."""

    def generate_nonbonded(first: list[str], second: list[str]) -> str:
        epsilon = math.sqrt(float(first[-1]) * float(second[-1]))
        sigma = 0.5 * (float(first[-2]) + float(second[-2]))
        return (
            f"{first[0]:>5} {second[0]:>4} {1:^5} "
            f"{sigma:.16e} {epsilon:.16e}\n"
        )

    module.generate_nonbonded = generate_nonbonded
    return module


def run_parser(converter: object, **options: object) -> None:
    """Run parser 0.2.2 without its unconditional empty-list diagnostic."""
    captured = io.StringIO()

    try:
        with contextlib.redirect_stdout(captured):
            converter.run(**options)
    finally:
        for line in captured.getvalue().splitlines():
            if line.strip() and line.strip() != "[]":
                print(line)


def load_parser_module() -> ModuleType:
    candidates = (
        "repex_topology_parser",
        "src.repex_topology_parser",
    )

    for name in candidates:
        try:
            return use_full_precision_nonbonded_output(
                importlib.import_module(name)
            )
        except ModuleNotFoundError:
            continue

    source_candidates = []
    source_value = os.environ.get("REPEX_TOPOLOGY_PARSER_SOURCE", "")
    if source_value:
        source_candidates.append(Path(source_value).expanduser())

    source_candidates.append(
        Path("dependencies/repex_topology_parser-0.2.2/src/repex_topology_parser.py")
    )

    for source in source_candidates:
        if source.is_dir():
            source = source / "src" / "repex_topology_parser.py"

        if not source.is_file():
            continue

        spec = importlib.util.spec_from_file_location(
            "repex_topology_parser_external", source
        )
        if spec is None or spec.loader is None:
            raise SystemExit(f"Could not load parser module: {source}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return use_full_precision_nonbonded_output(module)

    raise SystemExit(
        "repex-topology-parser 0.2.2 module not found. "
        "Run ./download.sh before ./build.sh."
    )


def generated_hot_topology(
    output_dir: Path, lambda_pp: float, kappa: float
) -> Path:
    expected_suffix = f"-{lambda_pp:.3f}-{kappa:.3f}.top"
    candidates = [
        path
        for path in output_dir.rglob("*.top")
        if path.name.endswith(expected_suffix)
    ]

    if len(candidates) != 1:
        raise SystemExit(
            "Could not identify exactly one target lambda/kappa topology: "
            f"suffix={expected_suffix}, found={len(candidates)}"
        )

    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("processed_topology", type=Path)
    parser.add_argument("states", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()

    module = load_parser_module()
    args.output_directory.mkdir(parents=True, exist_ok=True)

    with args.states.open(encoding="utf-8", newline="") as handle:
        states = list(csv.DictReader(handle, delimiter="\t"))

    if len(states) < 2:
        raise SystemExit(f"REST3 requires at least two states: {len(states)}")

    base_target = args.output_directory / "000" / "topol.top"
    base_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.processed_topology, base_target)

    for state in states[1:]:
        replica = state["replica"]
        temperature = float(state["effective_temperature_K"])
        lambda_pp = float(state["lambda_pp"])
        kappa = float(state["kappa"])
        temporary = args.output_directory / f".rest3_{replica}"
        temporary.mkdir(parents=True, exist_ok=True)

        converter = module.topo2rest(
            str(args.processed_topology),
            temps=[300.0, temperature],
            nreps=2,
        )

        molecules = getattr(converter, "molecules", {})
        protein_name = str(molecules.get(0, "")).lower()
        if "protein" not in protein_name:
            raise SystemExit(
                "Hot molecule at index 0 is not a protein: "
                f"{molecules.get(0, '<unknown>')}"
            )

        run_parser(
            converter,
            method="ssrest3",
            hot_molecules=[0],
            nreps=2,
            temps=[300.0, temperature],
            kappa_low_temp=300.0,
            kappa_max=kappa,
            kappa_atom_names=["OW"],
            outfile=f"rest3_{replica}",
            filepath=f"{temporary}/",
            verbose=False,
        )

        source = generated_hot_topology(temporary, lambda_pp, kappa)
        target = args.output_directory / replica / "topol.top"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        install_scaled_cmap(
            args.processed_topology,
            target,
            lambda_pp,
        )
        shutil.rmtree(temporary)

    print(f"Created {len(states)} REST3 topologies: {args.output_directory}")


if __name__ == "__main__":
    main()
