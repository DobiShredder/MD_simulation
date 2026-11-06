"""Compatibility fixes for repex-topology-parser 0.2.2 used by REST3."""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import io
import math
import os
from pathlib import Path
from types import ModuleType


def use_full_precision_nonbonded_output(module: ModuleType) -> ModuleType:
    """Replace the parser's four-decimal solvent override writer."""

    def generate_nonbonded(first: list[str], second: list[str]) -> str:
        epsilon = math.sqrt(float(first[-1]) * float(second[-1]))
        sigma = 0.5 * (float(first[-2]) + float(second[-2]))
        return (
            f"{first[0]:>5} {second[0]:>4} {1:^5} "
            f"{sigma:.16e} {epsilon:.16e}\n"
        )

    module.generate_nonbonded = generate_nonbonded
    return module


def use_molecule_definition_indices(module: ModuleType) -> ModuleType:
    """Match parser selections to definitions, preserving molecule row order."""
    def ordered_molecules(converter: object) -> None:
        molecules = {}
        # One definition may occur in several nonadjacent [ molecules ] rows.
        for index, definition in converter._sections["moleculetype"].items():
            for line in definition["header"]:
                fields = line.split(";", 1)[0].split()
                if fields and not fields[0].startswith("["):
                    molecules[index] = fields[0]
                    break
            else:
                raise ValueError(f"Molecule definition {index} has no name")
        converter.molecules = molecules
        converter.nmol = max(molecules)

    module.topo2rest._ordered_molecules = ordered_molecules
    return module


def use_hot_molecule_atom_types(module: ModuleType) -> ModuleType:
    """Look up each hot molecule's dihedral types with its own atom types.

    Parser 0.2.2 maps dihedral atom indices through molecule 0 for every hot
    molecule, which is wrong when more than one molecule is tempered.
    """
    def scale_dihedrals(converter: object, lambda_on: bool = True) -> None:
        sections = converter._sections
        dihedral_types = [
            line for line in sections["dihedraltypes"]
            if len(line[:line.find(";")].split()) > 4
        ]
        for hot in converter.hot_molecules:
            source = sections["moleculetype"][hot]["dihedrals"]
            if not lambda_on:
                converter._scaled_dihedrals[hot] = {value: source for value in converter.lambdai}
                continue
            dihedrals = module.dihedral_array(
                module.dihedraltype_array(dihedral_types),
                source,
                converter.molecule_atoms[hot],
            )
            unscaled_k = module.deepcopy(dihedrals["K"])
            converter._scaled_dihedrals[hot] = {}
            for value in converter.lambdai:
                dihedrals["K"] = unscaled_k * module.float32(value)
                converter._scaled_dihedrals[hot][value] = module.dihedrals_strings_list(dihedrals)

    module.topo2rest._get_scale_dehedrals = scale_dihedrals
    return module


def patch_parser(module: ModuleType) -> ModuleType:
    """Apply every compatibility fix used by this template."""
    module = use_full_precision_nonbonded_output(module)
    module = use_molecule_definition_indices(module)
    return use_hot_molecule_atom_types(module)


def run_parser(converter: object, **options: object) -> None:
    """Run the parser while suppressing its unconditional empty-list output."""
    captured = io.StringIO()

    try:
        with contextlib.redirect_stdout(captured):
            converter.run(**options)
    finally:
        for line in captured.getvalue().splitlines():
            if line.strip() and line.strip() != "[]":
                print(line)


def load_parser_module() -> ModuleType:
    """Load the installed parser or the source downloaded by download.sh."""
    for name in ("repex_topology_parser", "src.repex_topology_parser"):
        try:
            module = importlib.import_module(name)
            return patch_parser(module)
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
        return patch_parser(module)

    raise SystemExit(
        "repex-topology-parser 0.2.2 module not found. "
        "Run ./download.sh before ./build.sh."
    )
