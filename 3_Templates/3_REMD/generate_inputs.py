#!/usr/bin/env python3
"""Validate replica-exchange config and generate AMBER or GROMACS inputs."""

from __future__ import annotations

import argparse
import csv
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
        description="Generate config-driven AMBER T-REMD or GROMACS REST inputs."
    )
    parser.add_argument(
        "method",
        choices=("remd", "rest2", "rest3"),
        help="Replica-exchange method to generate",
    )
    parser.add_argument("config", type=Path, help="TOML configuration file")
    parser.add_argument("output", type=Path, help="Directory for generated input files")
    parser.add_argument(
        "--salt-pairs",
        type=int,
        help="Number of configured-salt formula units for the final tleap build",
    )
    parser.add_argument(
        "--states",
        type=Path,
        help="Resolved state table used to generate per-replica engine inputs",
    )
    return parser.parse_args()


def resolve(config_path: Path, method: str) -> dict[str, object]:
    config = load_config(config_path)
    build = section(config, "build")
    run = section(config, "run")
    exchange = section(config, "replica_exchange")

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

    production_steps = positive_int(run, "production_steps")
    segments = positive_int(run, "production_segments")
    if production_steps % segments != 0:
        raise ValueError("production_steps must be divisible by production_segments")
    random_seed = exchange.get("random_seed")
    if random_seed != "random" and (
        isinstance(random_seed, bool)
        or not isinstance(random_seed, int)
        or random_seed <= 0
    ):
        raise ValueError("random_seed must be 'random' or a positive integer")

    values = {
        "force_field": force_field,
        "water_model": water_model,
        "box_distance": positive_float(build, "solute_box_distance_angstrom"),
        "salt_concentration": nonnegative_float(build, "salt_concentration_molar"),
        "base_temperature": positive_float(run, "temperature_kelvin"),
        "pressure": positive_float(run, "pressure_bar"),
        "ensemble": "NPT",
        "timestep_fs": positive_float(run, "timestep_fs"),
        "constraint_mode": "h-bonds",
        "heating_steps": positive_int(run, "heating_steps"),
        "equilibration_steps": positive_int(run, "equilibration_steps"),
        "production_steps": production_steps,
        "production_steps_per_segment": production_steps // segments,
        "segments": segments,
        "trajectory_interval": positive_int(run, "trajectory_interval_steps"),
        "exchange_interval": positive_int(exchange, "exchange_interval_steps"),
        "random_seed": random_seed,
    }
    if method == "remd":
        values["engine"] = string_value(run, "engine")
        values["mpi_engine"] = string_value(run, "mpi_engine")
    else:
        values["equilibration_engine"] = string_value(run, "equilibration_engine")
        values["production_engine"] = string_value(run, "production_engine")
        values["threads_per_replica"] = positive_int(
            exchange, "cpu_threads_per_replica"
        )
        values["gpu_count"] = positive_int(exchange, "gpu_count")
    return values


def write_tleap(output: Path, values: dict[str, object], salt_pairs: int | None) -> None:
    if values["water_model"] == "OPC":
        water_source, water_box = "leaprc.water.opc", "OPCBOX"
    else:
        water_source, water_box = "leaprc.water.tip3p", "TIP3PBOX"
    lines = [
        "source leaprc.protein.ff19SB",
        f"source {water_source}",
        "system = loadpdb input.pdb",
        "check system",
        f"solvatebox system {water_box} {values['box_distance']:.3f}",
    ]
    if salt_pairs is None:
        lines.extend(["savepdb system solvated.pdb", "quit"])
        name = "tleap.solvate.in"
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
        name = "tleap.final.in"
    (output / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_states(path: Path, method: str) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    temperature_column = "temperature_K" if method == "remd" else "effective_temperature_K"
    if len(rows) < 2 or any(temperature_column not in row or "seed" not in row for row in rows):
        raise ValueError(f"invalid state table: {path}")
    return rows


def render_mdp(values: dict[str, object], *, stage: str, temperature: float, seed: int) -> str:
    dt_ps = float(values["timestep_fs"]) / 1000.0
    interval = int(values["trajectory_interval"])
    common = f"""integrator              = md
dt                      = {dt_ps:.6f}
constraints             = h-bonds
constraint-algorithm    = lincs
cutoff-scheme           = Verlet
nstlist                 = 20
rlist                   = 1.0
coulombtype             = PME
rcoulomb                = 1.0
vdwtype                 = Cut-off
rvdw                    = 1.0
tcoupl                  = v-rescale
tc-grps                 = System
tau-t                   = 1.0
ref-t                   = {temperature:.8f}
nstxout-compressed      = {interval}
nstenergy               = {interval}
nstlog                  = {interval}
pbc                     = xyz
"""
    continuation = "no" if stage == "equilibrate" else "yes"
    gen_vel = "yes" if stage == "equilibrate" else "no"
    nsteps = values["equilibration_steps"] if stage == "equilibrate" else values["production_steps_per_segment"]
    velocity_options = ""
    if stage == "equilibrate":
        velocity_options = (
            f"gen-temp                = {temperature:.8f}\n"
            f"gen-seed                = {seed}\n"
        )
    return f"""{common}nsteps                  = {nsteps}
continuation            = {continuation}
gen-vel                 = {gen_vel}
{velocity_options}pcoupl                  = C-rescale
pcoupltype               = isotropic
tau-p                   = 5.0
ref-p                   = {values['pressure']:.6f}
compressibility         = 4.5e-5
"""


def render_amber_input(title: str, values: list[str], extra: str = "") -> str:
    body = "\n".join(f" {value}," for value in values)
    return f"{title}\n&cntrl\n{body}\n/\n{extra}"


def write_amber_replica_inputs(
    output: Path, states_path: Path, values: dict[str, object]
) -> None:
    dt_ps = float(values["timestep_fs"]) / 1000.0
    interval = int(values["trajectory_interval"])
    exchange = int(values["exchange_interval"])
    production_steps = int(values["production_steps_per_segment"])
    if production_steps % exchange != 0:
        raise ValueError(
            "production steps per segment must be divisible by exchange_interval_steps"
        )

    for row in read_states(states_path, "remd"):
        replica = row["replica"]
        temperature = float(row["temperature_K"])
        seed = int(row["seed"])
        directory = output / replica
        directory.mkdir(parents=True, exist_ok=True)

        (directory / "minimize.in").write_text(
            render_amber_input(
                "Energy minimization",
                [
                    "imin=1",
                    "maxcyc=5000",
                    "ncyc=2500",
                    "ntb=1",
                    "cut=10.0",
                    "ntpr=100",
                ],
            ),
            encoding="utf-8",
        )

        heat_extra = (
            "&wt\n"
            " type='TEMP0',\n"
            " istep1=0,\n"
            f" istep2={values['heating_steps']},\n"
            " value1=20.0,\n"
            f" value2={temperature:.8f},\n"
            "/\n"
            "&wt type='END' /\n"
        )
        (directory / "heat.in").write_text(
            render_amber_input(
                f"Heat to {temperature:.8f} K",
                [
                    "imin=0",
                    "irest=0",
                    "ntx=1",
                    f"ig={seed}",
                    f"nstlim={values['heating_steps']}",
                    f"dt={dt_ps:.6f}",
                    "tempi=20.0",
                    f"temp0={temperature:.8f}",
                    "ntt=3",
                    "gamma_ln=1.0",
                    "ntb=1",
                    "ntc=2",
                    "ntf=2",
                    "cut=10.0",
                    "ntr=1",
                    "restraint_wt=5.0",
                    "restraintmask='!:WAT,Na+,Cl- & !@H='",
                    f"ntwx={interval}",
                    f"ntwr={interval}",
                    f"ntpr={interval}",
                    "ioutfm=1",
                    "nmropt=1",
                ],
                heat_extra,
            ),
            encoding="utf-8",
        )

        dynamics = [
            "imin=0",
            "irest=1",
            "ntx=5",
            "ig=-1",
            f"dt={dt_ps:.6f}",
            f"temp0={temperature:.8f}",
            "ntt=3",
            "gamma_ln=1.0",
            "ntb=2",
            "ntp=1",
            "barostat=2",
            f"pres0={values['pressure']:.6f}",
            "taup=2.0",
            "ntc=2",
            "ntf=2",
            "cut=10.0",
            "ntr=0",
            f"ntwx={interval}",
            f"ntwr={interval}",
            f"ntpr={interval}",
            "ioutfm=1",
        ]
        (directory / "equilibrate.in").write_text(
            render_amber_input(
                f"NPT equilibration at {temperature:.8f} K",
                [f"nstlim={values['equilibration_steps']}", *dynamics],
            ),
            encoding="utf-8",
        )
        (directory / "production.in").write_text(
            render_amber_input(
                f"T-REMD production segment at {temperature:.8f} K",
                [
                    f"nstlim={exchange}",
                    f"numexchg={production_steps // exchange}",
                    "iwrap=1",
                    *dynamics,
                ],
            ),
            encoding="utf-8",
        )


def write_gromacs_replica_inputs(
    output: Path, method: str, states_path: Path, values: dict[str, object]
) -> None:
    minimize = """integrator              = steep
nsteps                  = 5000
emtol                   = 1000.0
emstep                  = 0.01
cutoff-scheme           = Verlet
nstlist                 = 20
rlist                   = 1.0
coulombtype             = PME
rcoulomb                = 1.0
rvdw                    = 1.0
pbc                     = xyz
"""
    for row in read_states(states_path, method):
        replica = row["replica"]
        effective = float(row["temperature_K"] if method == "remd" else values["base_temperature"])
        seed = int(row["seed"])
        directory = output / replica
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "minimize.mdp").write_text(minimize, encoding="utf-8")
        for stage in ("equilibrate", "production"):
            (directory / f"{stage}.mdp").write_text(
                render_mdp(values, stage=stage, temperature=effective, seed=seed),
                encoding="utf-8",
            )


def write_replica_inputs(
    output: Path, method: str, states_path: Path, values: dict[str, object]
) -> None:
    if method == "remd":
        write_amber_replica_inputs(output, states_path, values)
    else:
        write_gromacs_replica_inputs(output, method, states_path, values)


def write_resolved(output: Path, method: str, values: dict[str, object], replicas: int, salt_pairs: int) -> None:
    random_seed = values["random_seed"]
    seed_literal = f'"{random_seed}"' if isinstance(random_seed, str) else str(random_seed)
    if method == "remd":
        engine_text = (
            f'engine = "{values["engine"]}"\n'
            f'mpi_engine = "{values["mpi_engine"]}"'
        )
        resource_text = ""
    else:
        engine_text = (
            f'equilibration_engine = "{values["equilibration_engine"]}"\n'
            f'production_engine = "{values["production_engine"]}"'
        )
        resource_text = (
            f"cpu_threads_per_replica = {values['threads_per_replica']}\n"
            f"gpu_count = {values['gpu_count']}\n"
        )
    text = f"""[build]
method = \"{method}\"
protein_force_field = \"{values['force_field']}\"
water_model = \"{values['water_model']}\"
solute_box_distance_angstrom = {values['box_distance']:.3f}
salt_concentration_molar = {values['salt_concentration']:.6f}
salt_pairs = {salt_pairs}

[run]
{engine_text}
temperature_kelvin = {values['base_temperature']:.6f}
pressure_bar = {values['pressure']:.6f}
ensemble = "{values['ensemble']}"
timestep_fs = {values['timestep_fs']:.6f}
constraint_mode = "{values['constraint_mode']}"
heating_steps = {values['heating_steps']}
equilibration_steps = {values['equilibration_steps']}
production_steps = {values['production_steps']}
production_steps_per_segment = {values['production_steps_per_segment']}
production_segments = {values['segments']}
trajectory_interval_steps = {values['trajectory_interval']}

[replica_exchange]
replicas = {replicas}
exchange_interval_steps = {values['exchange_interval']}
{resource_text}random_seed = {seed_literal}
"""
    (output / "resolved_config.toml").write_text(text, encoding="utf-8")


def main() -> None:
    args = parse_arguments()
    try:
        values = resolve(args.config, args.method)
        if args.salt_pairs is not None and args.salt_pairs < 0:
            raise ValueError("salt formula-unit count must be zero or greater")
        if args.states is not None:
            rows = read_states(args.states, args.method)
        else:
            rows = []
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None

    args.output.mkdir(parents=True, exist_ok=True)
    write_tleap(args.output, values, args.salt_pairs)
    if args.states is not None and args.salt_pairs is not None:
        write_replica_inputs(args.output.parent, args.method, args.states, values)
        write_resolved(args.output.parent, args.method, values, len(rows), args.salt_pairs)
    apply_config(args.config, args.output.parent)


if __name__ == "__main__":
    main()
