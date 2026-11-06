#!/usr/bin/env python3
"""Generate REST3 topologies from a resolved state table."""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from rest3_parser_adapter import load_parser_module, run_parser  # noqa: E402
from scale_cmap import install_scaled_cmap  # noqa: E402

# tempered_region = "solute": every molecule definition except water and ions
# is hot. These residue names match mark_hot.py and generate_states.py.
SOLVENT_AND_ION_NAMES = {
    "CA", "CA2", "CA2+", "CL", "CL-", "CLA", "HOH", "K", "K+", "MG", "MG2", "MG2+", "NA", "NA+", "OPC", "POT", "SOD", "SOL", "TIP3", "TIP3P", "WAT", "ZN", "ZN2", "ZN2+",
}


def generated_topology(directory: Path, lambda_pp: float, kappa: float) -> Path:
    suffix = f"-{lambda_pp:.3f}-{kappa:.3f}.top"
    candidates = [path for path in directory.rglob("*.top") if path.name.endswith(suffix)]
    if len(candidates) != 1:
        raise SystemExit(
            f"Could not identify one REST3 topology with suffix {suffix}: "
            f"found {len(candidates)}"
        )
    return candidates[0]


def solute_molecules(topology: Path) -> list[tuple[int, str]]:
    """Return (definition index, name) of every non-water, non-ion molecule."""
    definitions: list[tuple[str, set[str]]] = []
    section = ""
    for line in topology.read_text(encoding="utf-8").splitlines():
        data = line.split(";", 1)[0].strip()
        if not data or data.startswith("#"):
            continue
        if data.startswith("[") and data.endswith("]"):
            section = data.strip("[] ").lower()
            if section == "moleculetype":
                definitions.append(("", set()))
            continue
        fields = data.split()
        if section == "moleculetype" and not definitions[-1][0]:
            definitions[-1] = (fields[0], definitions[-1][1])
        elif section == "atoms" and len(fields) >= 5 and definitions:
            definitions[-1][1].add(fields[3].upper())

    selected: list[tuple[int, str]] = []
    for index, (name, residues) in enumerate(definitions):
        cold = residues & SOLVENT_AND_ION_NAMES
        if cold and cold != residues:
            raise SystemExit(
                f"Molecule {index} ({name}) mixes solute residues with water or ions; "
                "the solute hot region cannot be separated."
            )
        if not cold:
            selected.append((index, name))
    if not selected:
        raise SystemExit(f"No solute molecule found for the REST3 hot region: {topology}")
    return selected


def write_hot_molecules(path: Path, molecules: list[tuple[int, str]]) -> None:
    lines = ["molecule_index\tmolecule_name"]
    lines.extend(f"{index}\t{name}" for index, name in molecules)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    if len(states) < 2 or len(states) % 2:
        raise SystemExit(f"REST3 requires at least two and an even number of states: {args.states} ({len(states)} states)")

    hot_molecules = solute_molecules(args.processed_topology)
    hot_indices = [index for index, _ in hot_molecules]
    write_hot_molecules(args.output / "hot_molecules.tsv", hot_molecules)

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
        # The parser indexes [ moleculetype ] blocks itself; stop if its
        # indices do not name the same molecules as the solute selection.
        parser_molecules = getattr(converter, "molecules", {})
        for index, name in hot_molecules:
            if parser_molecules.get(index) != name:
                raise SystemExit(
                    f"Parser molecule {index} is {parser_molecules.get(index)!r}, "
                    f"expected {name!r}; hot-region selection is unsafe."
                )
        run_parser(
            converter,
            method="ssrest3",
            hot_molecules=hot_indices,
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

    names = ", ".join(name for _, name in hot_molecules)
    print(f"Created {len(states)} REST3 topologies: {args.output} (hot molecules: {names})")


if __name__ == "__main__":
    main()
