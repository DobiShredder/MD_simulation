#!/usr/bin/env python3
"""Generate REST3 topologies from a resolved state table."""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, "../../../1_Simulation/3_REMD/3.3_REST3")
from rest3_parser_adapter import load_parser_module, run_parser  # noqa: E402
from scale_cmap import install_scaled_cmap  # noqa: E402


def generated_topology(directory: Path, lambda_pp: float, kappa: float) -> Path:
    suffix = f"-{lambda_pp:.3f}-{kappa:.3f}.top"
    candidates = [path for path in directory.rglob("*.top") if path.name.endswith(suffix)]
    if len(candidates) != 1:
        raise SystemExit(
            f"Could not identify one REST3 topology with suffix {suffix}: "
            f"found {len(candidates)}"
        )
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and validate REST3 topologies for a resolved state table."
    )
    parser.add_argument(
        "processed_topology",
        type=Path,
        help="Base GROMACS topology with residue-specific CMAP types",
    )
    parser.add_argument("states", type=Path, help="Resolved REST3 states.tsv file")
    parser.add_argument("output", type=Path, help="Replica output directory")
    args = parser.parse_args()

    with args.states.open(encoding="utf-8", newline="") as handle:
        states = list(csv.DictReader(handle, delimiter="\t"))
    if len(states) < 2:
        raise SystemExit("REST3 requires at least two states")

    base_temperature = float(states[0]["effective_temperature_K"])
    base_target = args.output / states[0]["replica"] / "topol.top"
    base_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.processed_topology, base_target)
    module = load_parser_module()

    for state in states[1:]:
        replica = state["replica"]
        temperature = float(state["effective_temperature_K"])
        lambda_pp = float(state["lambda_pp"])
        kappa = float(state["kappa"])
        temporary = args.output / f".rest3_{replica}"
        temporary.mkdir(parents=True, exist_ok=True)
        converter = module.topo2rest(
            str(args.processed_topology), temps=[base_temperature, temperature], nreps=2
        )
        molecules = getattr(converter, "molecules", {})
        if "protein" not in str(molecules.get(0, "")).lower():
            raise SystemExit(
                "The first molecule is not identified as protein; "
                "automatic hot-region selection is unsafe."
            )
        run_parser(
            converter,
            method="ssrest3",
            hot_molecules=[0],
            nreps=2,
            temps=[base_temperature, temperature],
            kappa_low_temp=base_temperature,
            kappa_max=kappa,
            kappa_atom_names=["OW"],
            outfile=f"rest3_{replica}",
            filepath=f"{temporary}/",
            verbose=False,
        )
        source = generated_topology(temporary, lambda_pp, kappa)
        target = args.output / replica / "topol.top"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        install_scaled_cmap(args.processed_topology, target, lambda_pp)
        shutil.rmtree(temporary)

    print(f"Created {len(states)} REST3 topologies: {args.output}")


if __name__ == "__main__":
    main()
