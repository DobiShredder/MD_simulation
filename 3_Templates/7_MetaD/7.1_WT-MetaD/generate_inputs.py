#!/usr/bin/env python3
"""Generate config-driven AMBER inputs for MetaD and OPES templates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from apply_config import apply_config  # noqa: E402
from config_utils import (  # noqa: E402
    load_config,
    nonnegative_float,
    positive_float,
    positive_int,
    section,
    string_value,
)


METHODS = ("wt-metad", "funnel-metad", "opes-metad", "opes-expanded")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate tleap and AMBER stage inputs for a MetaD template."
    )
    parser.add_argument("method", choices=METHODS, help="MetaD or OPES method")
    parser.add_argument("config", type=Path, help="Template TOML configuration")
    parser.add_argument("output", type=Path, help="Directory for generated inputs")
    parser.add_argument(
        "--salt-pairs",
        type=int,
        help="Number of configured-salt formula units to add after neutralization",
    )
    return parser.parse_args()


def render_cntrl(title: str, values: list[str]) -> str:
    body = "\n".join(f"  {value}," for value in values)
    return f"{title}\n&cntrl\n{body}\n/\n"


def resolve(method: str, config_path: Path) -> dict[str, object]:
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
        raise ValueError("equilibration ensemble currently supports only NPT")
    if string_value(run, "constraint_mode").lower() != "h-bonds":
        raise ValueError("constraint_mode currently supports only h-bonds")
    if method == "funnel-metad":
        if string_value(build, "ligand_force_field").upper() != "GAFF2":
            raise ValueError("ligand_force_field currently supports only GAFF2")
        if string_value(build, "charge_method").upper() != "RESP":
            raise ValueError("charge_method currently supports only RESP")
        string_value(build, "ligand_residue_name")
        net_charge = build.get("ligand_net_charge")
        if isinstance(net_charge, bool) or not isinstance(net_charge, int):
            raise ValueError("ligand_net_charge must be an integer")

    production_steps = positive_int(run, "production_steps")
    segments = positive_int(run, "production_segments")
    if production_steps % segments != 0:
        raise ValueError("production_steps must be divisible by production_segments")

    seed = run.get("random_seed")
    if seed != "random" and (
        isinstance(seed, bool) or not isinstance(seed, int) or seed <= 0
    ):
        raise ValueError("random_seed must be 'random' or a positive integer")

    restraint_mask = "!:WAT,Na+,Cl- & !@H="
    if method == "funnel-metad":
        funnel_selection = section(config, "funnel_selection")
        restraint_mask = f"{string_value(funnel_selection, 'protein_mask')} & !@H="

    return {
        "method": method,
        "force_field": force_field,
        "water_model": water_model,
        "box_distance": positive_float(build, "solute_box_distance"),
        "salt_concentration": nonnegative_float(build, "salt_concentration_molar"),
        "engine": string_value(run, "engine"),
        "temperature": positive_float(run, "temperature"),
        "pressure": positive_float(run, "pressure"),
        "timestep": positive_float(run, "timestep"),
        "heating_steps": positive_int(run, "heating_steps"),
        "equilibration_steps": positive_int(run, "equilibration_steps"),
        "production_steps": production_steps,
        "production_steps_per_segment": production_steps // segments,
        "segments": segments,
        "trajectory_interval": positive_int(run, "trajectory_interval_steps"),
        "seed": seed,
        "restraint_mask": restraint_mask,
    }


def write_tleap(
    output: Path, values: dict[str, object], salt_pairs: int | None
) -> None:
    if values["water_model"] == "OPC":
        water_source = "leaprc.water.opc"
        water_box = "OPCBOX"
    else:
        water_source = "leaprc.water.tip3p"
        water_box = "TIP3PBOX"

    lines = ["source leaprc.protein.ff19SB"]
    if values["method"] == "funnel-metad":
        lines.extend([
            "source leaprc.gaff2",
            "loadamberparams ligand.frcmod",
            "LIG = loadmol2 ligand.mol2",
        ])
    lines.extend([
        f"source {water_source}",
        "system = loadpdb input.pdb",
        "check system",
        (
            f"solvatebox system {water_box} {values['box_distance']:.3f}"
            if values["method"] == "funnel-metad"
            else f"solvatebox system {water_box} {values['box_distance']:.3f} 0.75"
        ),
    ])
    if salt_pairs is None:
        lines.extend(["savepdb system solvated.pdb", "quit"])
        filename = "tleap.solvate.in"
    else:
        lines.extend([
            "addionsrand system Na+ 0",
            "addionsrand system Cl- 0",
            f"addionsrand system Na+ {salt_pairs}",
            f"addionsrand system Cl- {salt_pairs}",
            "check system",
            "saveamberparm system system.parm7 system.rst7",
            "savepdb system system.pdb",
            "quit",
        ])
        filename = "tleap.final.in"
    (output / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


def seed_value(seed: object, offset: int) -> int:
    if seed == "random":
        return -1
    return int(seed) + offset


def write_md_inputs(output: Path, values: dict[str, object]) -> None:
    timestep_ps = float(values["timestep"]) / 1000.0
    temperature = float(values["temperature"])
    pressure = float(values["pressure"])
    interval = int(values["trajectory_interval"])
    solute_mask = str(values["restraint_mask"])

    if values["method"] == "funnel-metad":
        (output / "min-solvent.in").write_text(
            render_cntrl(
                "Minimize solvent while restraining the solute",
                [
                    "imin=1", "maxcyc=5000", "ncyc=2500", "ntb=1", "cut=10.0",
                    "ntr=1", "restraint_wt=10.0", f"restraintmask='{solute_mask}'",
                    f"ntpr={interval}",
                ],
            ),
            encoding="utf-8",
        )
        minimization_name = "min-all.in"
    else:
        minimization_name = "minimize.in"
    (output / minimization_name).write_text(
        render_cntrl(
            "Minimize the complete system",
            ["imin=1", "maxcyc=5000", "ncyc=2500", "ntb=1", "cut=10.0",
             f"ntpr={interval}"],
        ),
        encoding="utf-8",
    )
    heating_input = render_cntrl(
            "Heat the system to the target temperature",
            [
                "imin=0", "irest=0", "ntx=1",
                f"nstlim={values['heating_steps']}", f"dt={timestep_ps:.6f}",
                "tempi=10.0", f"temp0={temperature:.3f}", "ntt=3",
                "gamma_ln=1.0", f"ig={seed_value(values['seed'], 1)}",
                "ntb=1", "ntp=0", "ntc=2", "ntf=2", "cut=10.0", "ntr=1",
                "restraint_wt=2.0", f"restraintmask='{solute_mask}'",
                f"ntpr={interval}", f"ntwx={interval}", f"ntwr={interval}",
                "ioutfm=1", "nmropt=1",
            ],
        )
    heating_input += (
        f"&wt TYPE='TEMP0', istep1=0, istep2={values['heating_steps']}, "
        f"value1=10.0, value2={temperature:.3f} /\n"
        "&wt TYPE='END' /\n"
    )
    (output / "heat.in").write_text(heating_input, encoding="utf-8")
    dynamics = [
        "imin=0", "irest=1", "ntx=5", f"dt={timestep_ps:.6f}",
        f"temp0={temperature:.3f}", "ntt=3", "gamma_ln=1.0",
        "ntc=2", "ntf=2", "cut=10.0", f"ntpr={interval}",
        f"ntwx={interval}", f"ntwr={interval}", "ioutfm=1",
    ]
    equilibration_input = render_cntrl(
            "NPT equilibration",
            [
                f"nstlim={values['equilibration_steps']}", *dynamics,
                "ig=-1",
                "ntb=2", "ntp=1", "barostat=1", f"pres0={pressure:.3f}",
                "taup=2.0",
                *(
                    ["ntr=1", "restraint_wt=0.5", f"restraintmask='{solute_mask}'"]
                    if values["method"] == "funnel-metad"
                    else []
                ),
            ],
        )
    if values["method"] != "funnel-metad":
        equilibration_input += "&ewald\n  skinnb=5.0,\n/\n"
    (output / "equilibrate.in").write_text(
        equilibration_input,
        encoding="utf-8",
    )
    if values["method"] == "opes-expanded":
        ensemble = ["ntb=1", "ntp=0"]
    else:
        ensemble = [
            "ntb=2", "ntp=1", "barostat=1", f"pres0={pressure:.3f}",
            "taup=2.0",
        ]
    (output / "production.in.template").write_text(
        render_cntrl(
            "Biased production segment",
            [
                f"nstlim={values['production_steps_per_segment']}", *dynamics,
                *ensemble, "ig=@RANDOM_SEED@", "plumed=1",
                "plumedfile='plumed.dat'",
            ],
        ),
        encoding="utf-8",
    )


def write_resolved(
    config: Path, output: Path, values: dict[str, object], salt_pairs: int | None
) -> None:
    text = config.read_text(encoding="utf-8").rstrip()
    text += "\n\n[resolved]\n"
    text += f"salt_pairs = {-1 if salt_pairs is None else salt_pairs}\n"
    text += (
        "production_steps_per_segment = "
        f"{values['production_steps_per_segment']}\n"
    )
    text += f"production_time_ns = {float(values['production_steps']) * float(values['timestep']) / 1_000_000:.6f}\n"
    (output / "resolved_config.toml").write_text(text, encoding="utf-8")


def main() -> None:
    args = parse_arguments()
    if args.salt_pairs is not None and args.salt_pairs < 0:
        raise SystemExit("--salt-pairs must be zero or greater")
    try:
        values = resolve(args.method, args.config)
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None
    args.output.mkdir(parents=True, exist_ok=True)
    write_tleap(args.output, values, args.salt_pairs)
    write_md_inputs(args.output, values)
    write_resolved(args.config, args.output.parent, values, args.salt_pairs)
    apply_config(args.config, args.output.parent)


if __name__ == "__main__":
    main()
