#!/usr/bin/env python3
"""Validate config and generate AMBER inputs for soluble-protein MD."""

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
        description="Generate config-driven AMBER preparation inputs for GaREUS."
    )
    parser.add_argument("config", type=Path, help="TOML configuration file")
    parser.add_argument("output", type=Path, help="Directory for generated input files")
    parser.add_argument(
        "--salt-pairs",
        type=int,
        help="Number of configured-salt formula units for the final tleap build",
    )
    return parser.parse_args()


def render_cntrl(title: str, values: list[str]) -> str:
    body = "\n".join(f"  {value}," for value in values)
    return f"{title}\n&cntrl\n{body}\n/\n"


def resolve(config_path: Path) -> dict[str, object]:
    config = load_config(config_path)
    build = section(config, "build")
    run = section(config, "run")

    force_field = string_value(build, "protein_force_field")
    water_model = string_value(build, "water_model").upper()
    if force_field != "ff19SB":
        raise ValueError("protein_force_field currently supports only ff19SB")
    if water_model not in {"OPC", "TIP3P"}:
        raise ValueError("water_model must be OPC or TIP3P")
    if string_value(run, "ensemble").upper() != "NPT":
        raise ValueError("ensemble currently supports only NPT")
    if string_value(run, "constraint_mode").lower() != "h-bonds":
        raise ValueError("constraint_mode currently supports only h-bonds")

    timestep = positive_float(run, "timestep")
    heating_steps = positive_int(run, "heating_steps")
    equilibration_steps = positive_int(run, "equilibration_steps")
    total_production_steps = positive_int(run, "production_steps")
    segments = positive_int(run, "production_segments")
    if total_production_steps % segments != 0:
        raise ValueError("production steps must be divisible by production_segments")

    seed = run.get("random_seed")
    if seed != "random" and (
        isinstance(seed, bool) or not isinstance(seed, int) or seed <= 0
    ):
        raise ValueError("random_seed must be 'random' or a positive integer")

    return {
        "force_field": force_field,
        "water_model": water_model,
        "box_distance": positive_float(build, "solute_box_distance"),
        "salt_concentration": nonnegative_float(build, "salt_concentration_molar"),
        "engine": string_value(run, "engine"),
        "temperature": positive_float(run, "temperature"),
        "pressure": positive_float(run, "pressure"),
        "ensemble": "NPT",
        "timestep": timestep,
        "constraint_mode": "h-bonds",
        "heating_steps": heating_steps,
        "equilibration_steps": equilibration_steps,
        "production_steps": total_production_steps,
        "production_steps_per_segment": total_production_steps // segments,
        "segments": segments,
        "trajectory_interval": positive_int(run, "trajectory_interval_steps"),
        "seed": seed,
    }


def write_tleap(output: Path, values: dict[str, object], salt_pairs: int | None) -> None:
    if values["water_model"] == "OPC":
        water_source = "leaprc.water.opc"
        water_box = "OPCBOX"
    else:
        water_source = "leaprc.water.tip3p"
        water_box = "TIP3PBOX"

    lines = [
        "source leaprc.protein.ff19SB",
        f"source {water_source}",
        "system = loadpdb input.pdb",
        "check system",
        f"solvatebox system {water_box} {values['box_distance']:.3f}",
    ]
    if salt_pairs is None:
        lines.extend(["savepdb system solvated.pdb", "quit"])
        path = output / "tleap.solvate.in"
    else:
        lines.extend(
            [
                "addionsrand system Na+ 0",
                "addionsrand system Cl- 0",
                f"addionsrand system Na+ {salt_pairs}",
                f"addionsrand system Cl- {salt_pairs}",
                "check system",
                "saveamberparm system system.parm7 system.rst7",
                "savepdb system system.pdb",
                "quit",
            ]
        )
        path = output / "tleap.final.in"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_md_inputs(output: Path, values: dict[str, object]) -> None:
    dt_ps = float(values["timestep"]) / 1000.0
    temperature = values["temperature"]
    pressure = values["pressure"]
    interval = values["trajectory_interval"]
    seed = -1 if values["seed"] == "random" else values["seed"]

    (output / "min-solvent.in").write_text(
        render_cntrl(
            "Minimize solvent while restraining the solute",
            [
                "imin=1", "maxcyc=5000", "ncyc=2500", "ntb=1", "cut=10.0",
                "ntr=1", "restraint_wt=10.0", "restraintmask='!:WAT,Na+,Cl-'",
            ],
        ),
        encoding="utf-8",
    )
    (output / "min-all.in").write_text(
        render_cntrl(
            "Minimize the complete system",
            ["imin=1", "maxcyc=10000", "ncyc=5000", "ntb=1", "cut=10.0", "ntr=0"],
        ),
        encoding="utf-8",
    )
    (output / "heat.in").write_text(
        render_cntrl(
            "Heat the system to the target temperature",
            [
                "imin=0", "irest=0", "ntx=1", f"nstlim={values['heating_steps']}",
                f"dt={dt_ps:.6f}", "tempi=20.0", f"temp0={temperature:.3f}",
                "ntt=3", "gamma_ln=1.0", f"ig={seed}", "ntb=1", "ntc=2",
                "ntf=2", "cut=10.0", "ntr=1", "restraint_wt=2.0",
                "restraintmask='!:WAT,Na+,Cl-'", f"ntpr={interval}",
                f"ntwx={interval}", f"ntwr={interval}", "ioutfm=1",
            ],
        ),
        encoding="utf-8",
    )
    dynamics = [
        "imin=0", "irest=1", "ntx=5", f"dt={dt_ps:.6f}",
        f"temp0={temperature:.3f}", "ntt=3", "gamma_ln=1.0", "ig=-1",
        "ntb=2", "ntp=1", "barostat=2", f"pres0={pressure:.3f}",
        "taup=2.0", "ntc=2", "ntf=2", "cut=10.0", "ntr=0",
        f"ntpr={interval}", f"ntwx={interval}", f"ntwr={interval}", "ioutfm=1",
    ]
    (output / "equilibrate.in").write_text(
        render_cntrl(
            "NPT equilibration",
            [f"nstlim={values['equilibration_steps']}", *dynamics],
        ),
        encoding="utf-8",
    )
    (output / "production.in").write_text(
        render_cntrl(
            "Production MD segment",
            [f"nstlim={values['production_steps_per_segment']}", *dynamics],
        ),
        encoding="utf-8",
    )


def write_resolved(output: Path, values: dict[str, object], salt_pairs: int | None) -> None:
    seed = f'"{values["seed"]}"' if isinstance(values["seed"], str) else values["seed"]
    salt_text = -1 if salt_pairs is None else salt_pairs
    text = f"""[build]
protein_force_field = \"{values['force_field']}\"
water_model = \"{values['water_model']}\"
solute_box_distance = {values['box_distance']:.3f}
salt_concentration_molar = {values['salt_concentration']:.6f}
salt_pairs = {salt_text}

[run]
engine = \"{values['engine']}\"
temperature = {values['temperature']:.3f}
pressure = {values['pressure']:.3f}
ensemble = "{values['ensemble']}"
timestep = {values['timestep']:.3f}
constraint_mode = "{values['constraint_mode']}"
heating_steps = {values['heating_steps']}
equilibration_steps = {values['equilibration_steps']}
production_steps_per_segment = {values['production_steps_per_segment']}
production_steps = {values['production_steps']}
production_segments = {values['segments']}
trajectory_interval_steps = {values['trajectory_interval']}
random_seed = {seed}
"""
    (output / "resolved_config.toml").write_text(text, encoding="utf-8")


def main() -> None:
    args = parse_arguments()
    if args.salt_pairs is not None and args.salt_pairs < 0:
        raise SystemExit("--salt-pairs must be zero or greater")
    try:
        values = resolve(args.config)
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None
    args.output.mkdir(parents=True, exist_ok=True)
    write_tleap(args.output, values, args.salt_pairs)
    write_md_inputs(args.output, values)
    write_resolved(args.output.parent, values, args.salt_pairs)
    apply_config(args.config, args.output.parent)


if __name__ == "__main__":
    main()
