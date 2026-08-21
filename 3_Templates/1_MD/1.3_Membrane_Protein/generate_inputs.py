#!/usr/bin/env python3
"""Validate membrane config and generate AMBER input files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, "../../common")
from apply_config import apply_config  # noqa: E402
from config_utils import (  # noqa: E402
    load_config,
    nonnegative_float,
    positive_float,
    positive_int,
    section,
    string_value,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate config-driven AMBER inputs for membrane-protein MD."
    )
    parser.add_argument("config", type=Path, help="TOML configuration file")
    parser.add_argument("output", type=Path, help="Directory for generated input files")
    parser.add_argument(
        "--coordinate",
        type=Path,
        help="Built membrane PDB used to generate the final tleap input",
    )
    return parser.parse_args()


def resolve(config_path: Path) -> dict[str, object]:
    config = load_config(config_path)
    build = section(config, "build")
    run = section(config, "run")
    if string_value(build, "protein_force_field") != "ff19SB":
        raise ValueError("protein_force_field currently supports only ff19SB")
    if string_value(build, "lipid_force_field").lower() != "lipid21":
        raise ValueError("lipid_force_field currently supports only Lipid21")
    if string_value(build, "water_model").upper() != "OPC":
        raise ValueError("membrane template currently supports only OPC")
    if string_value(run, "ensemble").upper() != "NPT":
        raise ValueError("ensemble currently supports only NPT")
    if string_value(run, "pressure_coupling").lower() != "anisotropic":
        raise ValueError("membrane pressure_coupling must be anisotropic")
    if string_value(run, "constraint_mode").lower() != "h-bonds":
        raise ValueError("constraint_mode currently supports only h-bonds")
    production_steps = positive_int(run, "production_steps")
    segments = positive_int(run, "production_segments")
    if production_steps % segments != 0:
        raise ValueError("production_steps must be divisible by production_segments")
    seed = run.get("random_seed")
    if seed != "random" and (
        isinstance(seed, bool) or not isinstance(seed, int) or seed <= 0
    ):
        raise ValueError("random_seed must be 'random' or a positive integer")
    return {
        "protein_force_field": "ff19SB",
        "lipid_force_field": "Lipid21",
        "water_model": "OPC",
        "composition": string_value(build, "bilayer_composition"),
        "popc": Path(string_value(build, "popc_bilayer_gro")),
        "pope": Path(string_value(build, "pope_bilayer_gro")),
        "cholesterol": Path(string_value(build, "cholesterol_bilayer_gro")),
        "xy_padding": positive_float(build, "xy_padding_angstrom"),
        "water_padding": positive_float(build, "water_padding_angstrom"),
        "protein_lipid_distance": positive_float(build, "protein_lipid_distance_angstrom"),
        "salt_concentration": nonnegative_float(build, "salt_concentration_molar"),
        "restraint_mask": string_value(build, "protein_restraint_mask"),
        "engine": string_value(run, "engine"),
        "temperature": positive_float(run, "temperature_kelvin"),
        "pressure": positive_float(run, "pressure_bar"),
        "timestep_fs": positive_float(run, "timestep_fs"),
        "heating_steps": positive_int(run, "heating_steps"),
        "equilibration_steps": positive_int(run, "equilibration_steps"),
        "production_steps": production_steps,
        "production_steps_per_segment": production_steps // segments,
        "segments": segments,
        "interval": positive_int(run, "trajectory_interval_steps"),
        "seed": seed,
    }


def render_cntrl(title: str, values: list[str]) -> str:
    body = "\n".join(f"  {value}," for value in values)
    return f"{title}\n&cntrl\n{body}\n/\n"


def write_md_inputs(output: Path, values: dict[str, object]) -> None:
    dt_ps = float(values["timestep_fs"]) / 1000.0
    temperature = values["temperature"]
    pressure = values["pressure"]
    interval = values["interval"]
    seed = -1 if values["seed"] == "random" else values["seed"]
    mask = values["restraint_mask"]
    (output / "min-solvent.in").write_text(
        render_cntrl(
            "Minimize membrane environment while restraining the protein",
            [
                "imin=1", "maxcyc=10000", "ncyc=5000", "ntmin=2",
                "dx0=0.0001", "ntb=1", "ntc=1", "ntf=1", "cut=10.0", "ntr=1",
                "restraint_wt=10.0", f"restraintmask='{mask}'",
            ],
        ), encoding="utf-8"
    )
    (output / "min-all.in").write_text(
        render_cntrl(
            "Minimize the complete membrane system",
            ["imin=1", "maxcyc=10000", "ncyc=5000", "ntmin=2", "dx0=0.0001", "ntb=1", "ntc=1", "ntf=1", "cut=10.0", "ntr=0"],
        ), encoding="utf-8"
    )
    (output / "heat.in").write_text(
        render_cntrl(
            "Heat the membrane system",
            [
                "imin=0", "irest=0", "ntx=1", f"nstlim={values['heating_steps']}",
                f"dt={dt_ps:.6f}", "tempi=20.0", f"temp0={temperature:.3f}",
                "ntt=3", "gamma_ln=1.0", f"ig={seed}", "ntb=1", "ntp=0", "ntc=2",
                "ntf=2", "cut=10.0", "ntr=1", "restraint_wt=5.0",
                f"restraintmask='{mask}'", f"ntpr={interval}", f"ntwx={interval}",
                f"ntwr={interval}", "ioutfm=1", "nmropt=1",
            ],
        )
        + f"&wt\n type='TEMP0', istep1=0, istep2={values['heating_steps']}, value1=20.0, value2={temperature:.3f},\n/\n&wt type='END' /\n",
        encoding="utf-8",
    )
    dynamics = [
        "imin=0", "irest=1", "ntx=5", f"dt={dt_ps:.6f}",
        f"temp0={temperature:.3f}", "ntt=3", "gamma_ln=1.0", "ig=-1",
        "ntb=2", "ntp=2", "barostat=2", f"pres0={pressure:.3f}",
        "taup=2.0", "ntc=2", "ntf=2", "cut=10.0",
        f"ntpr={interval}", f"ntwx={interval}", f"ntwr={interval}", "ioutfm=1",
    ]
    (output / "equilibrate.in").write_text(
        render_cntrl(
            "Anisotropic NPT membrane equilibration",
            [f"nstlim={values['equilibration_steps']}", *dynamics, "ntr=1", "restraint_wt=1.0", f"restraintmask='{mask}'"],
        ), encoding="utf-8"
    )
    (output / "production.in").write_text(
        render_cntrl(
            "Membrane production segment",
            [f"nstlim={values['production_steps_per_segment']}", *dynamics, "ntr=0"],
        ), encoding="utf-8"
    )


def read_box_and_waters(path: Path) -> tuple[tuple[float, float, float], int]:
    box = None
    waters: set[tuple[str, str, str]] = set()
    for line in path.read_text(encoding="ascii").splitlines():
        if line.startswith("CRYST1"):
            box = (float(line[6:15]), float(line[15:24]), float(line[24:33]))
        if line.startswith(("ATOM  ", "HETATM")) and line[17:20].strip() == "WAT":
            waters.add((line[21:22], line[22:26], line[26:27]))
    if box is None or not waters:
        raise ValueError("packed membrane PDB must contain CRYST1 and WAT residues")
    return box, len(waters)


def write_build_parameters(output: Path, values: dict[str, object]) -> None:
    lines = [
        f"composition\t{values['composition']}", f"popc\t{values['popc']}",
        f"pope\t{values['pope']}", f"cholesterol\t{values['cholesterol']}",
        f"xy_padding\t{values['xy_padding']}", f"water_padding\t{values['water_padding']}",
        f"protein_lipid_distance\t{values['protein_lipid_distance']}",
    ]
    (output.parent / "build_parameters.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tleap_and_resolved(output: Path, values: dict[str, object], coordinate: Path) -> None:
    box, water_count = read_box_and_waters(coordinate)
    salt_pairs = round(water_count * float(values["salt_concentration"]) / 55.5)
    tleap = f"""source leaprc.protein.ff19SB
source leaprc.lipid21
source leaprc.water.opc
system = loadpdb system-coordinates.pdb
set system box {{ {box[0]:.3f} {box[1]:.3f} {box[2]:.3f} }}
addionsrand system K+ 0
addionsrand system Cl- 0
addionsrand system K+ {salt_pairs} Cl- {salt_pairs}
check system
saveamberparm system system.parm7 system.rst7
savepdb system system.pdb
quit
"""
    (output / "tleap.in").write_text(tleap, encoding="utf-8")
    seed = f'"{values["seed"]}"' if isinstance(values["seed"], str) else values["seed"]
    resolved = f"""[build]
protein_force_field = "ff19SB"
lipid_force_field = "Lipid21"
water_model = "OPC"
bilayer_composition = "{values['composition']}"
xy_padding_angstrom = {values['xy_padding']:.3f}
water_padding_angstrom = {values['water_padding']:.3f}
protein_lipid_distance_angstrom = {values['protein_lipid_distance']:.3f}
salt_concentration_molar = {values['salt_concentration']:.6f}
water_molecules = {water_count}
salt_pairs = {salt_pairs}

[run]
engine = "{values['engine']}"
temperature_kelvin = {values['temperature']:.3f}
pressure_bar = {values['pressure']:.3f}
ensemble = "NPT"
pressure_coupling = "anisotropic"
timestep_fs = {values['timestep_fs']:.3f}
constraint_mode = "h-bonds"
heating_steps = {values['heating_steps']}
equilibration_steps = {values['equilibration_steps']}
production_steps = {values['production_steps']}
production_steps_per_segment = {values['production_steps_per_segment']}
production_segments = {values['segments']}
trajectory_interval_steps = {values['interval']}
random_seed = {seed}
"""
    (output.parent / "resolved_config.toml").write_text(resolved, encoding="utf-8")


def main() -> None:
    args = parse_arguments()
    try:
        values = resolve(args.config)
        for path in (values["popc"], values["pope"], values["cholesterol"]):
            if not path.is_file():
                raise ValueError(f"bilayer coordinate file not found: {path}")
        args.output.mkdir(parents=True, exist_ok=True)
        write_md_inputs(args.output, values)
        write_build_parameters(args.output, values)
        if args.coordinate is not None:
            write_tleap_and_resolved(args.output, values, args.coordinate)
        apply_config(args.config, args.output.parent)
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None


if __name__ == "__main__":
    main()
