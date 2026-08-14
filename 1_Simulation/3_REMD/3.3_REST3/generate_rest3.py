#!/usr/bin/env python3
"""Generate ssREST3 topologies from a fixed temperature/kappa table."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

from rest3_parser_adapter import load_parser_module, run_parser
from scale_cmap import install_scaled_cmap


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
