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
from tempered_selection import definition_selection, read_selection, topology_layout  # noqa: E402

def generated_topology(directory: Path, lambda_pp: float, kappa: float) -> Path:
    suffix = f"-{lambda_pp:.3f}-{kappa:.3f}.top"
    candidates = [path for path in directory.rglob("*.top") if path.name.endswith(suffix)]
    if len(candidates) != 1:
        raise SystemExit(
            f"Could not identify one REST3 topology with suffix {suffix}: "
            f"found {len(candidates)}"
        )
    return candidates[0]


def select_hot_molecules(topology: Path, tempered_atoms: Path) -> list[tuple[int, str]]:
    """Return (definition index, name) of the molecules in the tempered selection.

    The parser tempers whole [ moleculetype ] definitions (hot_molecules), so
    the selection must cover every atom of each selected molecule.
    """
    try:
        definitions, _ = topology_layout(topology)
        positions = definition_selection(topology, read_selection(tempered_atoms))
    except (OSError, ValueError) as error:
        raise SystemExit(f"Error: {error}") from None

    selected: list[tuple[int, str]] = []
    for index in sorted(positions):
        name, atoms = definitions[index]
        if len(positions[index]) != len(atoms):
            raise SystemExit(
                f"The tempered selection covers {len(positions[index])} of {len(atoms)} atoms "
                f"of molecule {index} ({name}). REST3 (repex-topology-parser hot_molecules) "
                "tempers whole molecules only: select every atom of the molecule, or use "
                "REST2 for a partial region."
            )
        selected.append((index, name))
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
    parser.add_argument("tempered_atoms", type=Path, help="tempered_atoms.tsv from tempered_selection.py")
    parser.add_argument("states", type=Path, help="Resolved REST3 states.tsv file")
    parser.add_argument("output", type=Path, help="Replica output directory")
    args = parser.parse_args()

    with args.states.open(encoding="utf-8", newline="") as handle:
        states = list(csv.DictReader(handle, delimiter="\t"))
    if len(states) < 2 or len(states) % 2:
        raise SystemExit(f"REST3 requires at least two and an even number of states: {args.states} ({len(states)} states)")

    selected_molecules = select_hot_molecules(args.processed_topology, args.tempered_atoms)
    hot_indices = [index for index, _ in selected_molecules]
    write_hot_molecules(args.output / "hot_molecules.tsv", selected_molecules)

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
        # indices do not name the same molecules as the tempered selection.
        parser_molecules = getattr(converter, "molecules", {})
        for index, name in selected_molecules:
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

    names = ", ".join(name for _, name in selected_molecules)
    print(f"Created {len(states)} REST3 topologies: {args.output} (hot molecules: {names})")


if __name__ == "__main__":
    main()
