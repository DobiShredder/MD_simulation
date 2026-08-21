#!/usr/bin/env python3
"""Prepare tleap files for config-driven RBFE and ABFE systems."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, "../../common")
from apply_config import apply_config  # noqa: E402
from config_utils import load_config, nonnegative_float, positive_float, section, string_value  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy reviewed FEP inputs and generate first- or second-pass tleap files."
    )
    parser.add_argument(
        "method",
        choices=("rbfe", "abfe"),
        help="Free-energy method that determines the required systems",
    )
    parser.add_argument("config", type=Path, help="TOML configuration file")
    parser.add_argument("structure", type=Path, help="Reviewed input PDB structure")
    parser.add_argument("output", type=Path, help="Directory for copied inputs and tleap files")
    parser.add_argument(
        "--complex-salt-pairs",
        type=int,
        help="Number of configured-salt formula units for the complex system",
    )
    parser.add_argument(
        "--solvent-salt-pairs",
        type=int,
        help="Number of configured-salt formula units for the solvent system",
    )
    return parser.parse_args()


def copy_input(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError(f"Required input not found: {source}")
    shutil.copy2(source, destination)


def integer_value(values: dict[str, object], key: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def validate_mol2(path: Path, residue_name: str, expected_charge: int) -> None:
    try:
        import parmed
    except ImportError as error:
        raise ValueError("ParmEd is required to validate ligand MOL2 files") from error
    ligand = parmed.load_file(str(path))
    atoms = list(ligand.atoms)
    if not atoms:
        raise ValueError(f"Ligand MOL2 contains no atoms: {path}")
    names = {atom.residue.name for atom in atoms}
    if names != {residue_name}:
        raise ValueError(f"{path} residue names {sorted(names)} do not match {residue_name}")
    charge = sum(float(atom.charge) for atom in atoms)
    if abs(charge - expected_charge) > 0.01:
        raise ValueError(f"{path} charge {charge:.6f} does not match expected {expected_charge}")


def water_settings(name: str) -> tuple[str, str]:
    normalized = name.upper()
    if normalized == "OPC":
        return "leaprc.water.opc", "OPCBOX"
    if normalized == "TIP3P":
        return "leaprc.water.tip3p", "TIP3PBOX"
    raise ValueError("water_model must be OPC or TIP3P")


def leap_text(
    method: str,
    environment: str,
    build: dict[str, object],
    water_source: str,
    water_box: str,
    salt_pairs: int | None,
) -> str:
    if environment == "complex":
        distance = positive_float(build, "complex_box_distance")
    else:
        distance = positive_float(build, "solvent_box_distance")

    lines = ["source leaprc.gaff2", f"source {water_source}"]
    if environment == "complex":
        lines.insert(0, "source leaprc.protein.ff19SB")

    if method == "rbfe":
        name_a = string_value(build, "ligand_a_residue_name")
        name_b = string_value(build, "ligand_b_residue_name")
        lines.extend(
            [
                "loadamberparams ligand_a.frcmod",
                "loadamberparams ligand_b.frcmod",
                f"{name_a} = loadmol2 ligand_a.mol2",
                f"{name_b} = loadmol2 ligand_b.mol2",
            ]
        )
        if environment == "complex":
            lines.extend(["protein = loadpdb input.pdb", f"system = combine {{ protein {name_a} {name_b} }}"])
        else:
            lines.append(f"system = combine {{ {name_a} {name_b} }}")
    else:
        name = string_value(build, "ligand_residue_name")
        lines.extend(["loadamberparams ligand.frcmod", f"{name} = loadmol2 ligand.mol2"])
        if environment == "complex":
            lines.append("system = loadpdb input.pdb")
        else:
            lines.append(f"system = combine {{ {name} }}")

    lines.append(f"solvatebox system {water_box} {distance:.3f}")
    if salt_pairs is None:
        lines.extend([f"savepdb system {environment}.solvated.pdb", "quit"])
    else:
        lines.extend(
            [
                "addionsrand system Na+ 0",
                "addionsrand system Cl- 0",
                f"addionsrand system Na+ {salt_pairs}",
                f"addionsrand system Cl- {salt_pairs}",
                f"saveamberparm system {environment}.parm7 {environment}.rst7",
                f"savepdb system {environment}.pdb",
                "quit",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = arguments()
    if (args.complex_salt_pairs is None) != (args.solvent_salt_pairs is None):
        raise SystemExit("Specify both salt-pair counts or neither")
    for count in (args.complex_salt_pairs, args.solvent_salt_pairs):
        if count is not None and count < 0:
            raise SystemExit("Salt-pair counts must be zero or greater")

    try:
        config = load_config(args.config)
        build = section(config, "build")
        if string_value(build, "protein_force_field") != "ff19SB":
            raise ValueError("protein_force_field currently supports only ff19SB")
        if string_value(build, "ligand_force_field").upper() != "GAFF2":
            raise ValueError("ligand_force_field currently supports only GAFF2")
        if string_value(build, "charge_method").upper() != "RESP":
            raise ValueError("charge_method currently supports precharged RESP MOL2 input")
        nonnegative_float(build, "salt_concentration_molar")
        water_source, water_box = water_settings(string_value(build, "water_model"))
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None

    args.output.mkdir(parents=True, exist_ok=True)
    copy_input(args.structure, args.output / "input.pdb")
    if args.method == "rbfe":
        copy_input(Path(string_value(build, "ligand_a_mol2")), args.output / "ligand_a.mol2")
        copy_input(Path(string_value(build, "ligand_a_frcmod")), args.output / "ligand_a.frcmod")
        copy_input(Path(string_value(build, "ligand_b_mol2")), args.output / "ligand_b.mol2")
        copy_input(Path(string_value(build, "ligand_b_frcmod")), args.output / "ligand_b.frcmod")
        validate_mol2(
            args.output / "ligand_a.mol2",
            string_value(build, "ligand_a_residue_name"),
            integer_value(build, "ligand_a_net_charge"),
        )
        validate_mol2(
            args.output / "ligand_b.mol2",
            string_value(build, "ligand_b_residue_name"),
            integer_value(build, "ligand_b_net_charge"),
        )
    else:
        copy_input(Path(string_value(build, "ligand_mol2")), args.output / "ligand.mol2")
        copy_input(Path(string_value(build, "ligand_frcmod")), args.output / "ligand.frcmod")
        validate_mol2(
            args.output / "ligand.mol2",
            string_value(build, "ligand_residue_name"),
            integer_value(build, "ligand_net_charge"),
        )

    for environment, salt_pairs in (
        ("complex", args.complex_salt_pairs),
        ("solvent", args.solvent_salt_pairs),
    ):
        phase = "solvate" if salt_pairs is None else "final"
        path = args.output / f"tleap.{environment}.{phase}.in"
        path.write_text(
            leap_text(args.method, environment, build, water_source, water_box, salt_pairs),
            encoding="utf-8",
        )
    apply_config(args.config, args.output.parent)


if __name__ == "__main__":
    main()
