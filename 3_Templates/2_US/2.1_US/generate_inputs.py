#!/usr/bin/env python3
"""Generate shared build, ratchet-MD, and umbrella-sampling inputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, "../../common")
from apply_config import apply_config  # noqa: E402
from config_utils import (  # noqa: E402
    amber_ensemble_lines,
    choice_value,
    load_config,
    nonnegative_float,
    positive_float,
    positive_int,
    run_settings,
    salt_settings,
    section,
    string_value,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one stage of the config-driven rMD/US workflow."
    )
    parser.add_argument("mode", choices=("build", "rmd", "us"), help="input set to generate")
    parser.add_argument("config", type=Path, help="TOML configuration file")
    parser.add_argument("output", type=Path, help="work directory for generated inputs")
    parser.add_argument("--salt-pairs", type=int, help="bulk-salt formula-unit count")
    parser.add_argument("--topology", type=Path, help="AMBER topology for atom-mask resolution")
    return parser.parse_args()


def render_cntrl(title: str, values: list[str]) -> str:
    body = "\n".join(f"  {value}," for value in values)
    return f"{title}\n&cntrl\n{body}\n/\n"


def resolve(config_path: Path) -> dict[str, object]:
    config = load_config(config_path)
    build = section(config, "build")
    run = section(config, "run")
    umbrella = section(config, "umbrella")
    ratchet = section(config, "ratchet_md")
    runtime = run_settings(run)

    force_field = string_value(build, "protein_force_field")
    water_model = string_value(build, "water_model").upper()
    if force_field != "ff19SB":
        raise ValueError("protein_force_field currently supports only ff19SB")
    if water_model not in {"OPC", "TIP3P"}:
        raise ValueError("water_model must be OPC or TIP3P")
    box_shape = choice_value(build, "box_shape", {"rectangular", "octahedral"})
    if string_value(run, "constraint_mode").lower() != "h-bonds":
        raise ValueError("constraint_mode currently supports only h-bonds")
    if positive_int(run, "production_segments") != 1:
        raise ValueError("umbrella sampling currently supports production_segments=1")

    density_minimum = nonnegative_float(ratchet, "minimum_density")
    density_maximum = positive_float(ratchet, "maximum_density")
    if density_maximum <= density_minimum:
        raise ValueError("maximum_density must be greater than minimum_density")

    seed = run.get("random_seed")
    if seed != "random" and (
        isinstance(seed, bool) or not isinstance(seed, int) or seed <= 0
    ):
        raise ValueError("random_seed must be 'random' or a positive integer")

    return {
        "config": config,
        "force_field": force_field,
        "water_model": water_model,
        "box_shape": box_shape,
        "box_distance": positive_float(build, "solute_box_distance"),
        "salt": salt_settings(build),
        "runtime": runtime,
        "temperature": positive_float(run, "temperature"),
        "pressure": positive_float(run, "pressure"),
        "timestep_ps": positive_float(run, "timestep") / 1000.0,
        "heating_steps": positive_int(run, "heating_steps"),
        "equilibration_steps": positive_int(run, "equilibration_steps"),
        "production_steps": positive_int(run, "production_steps"),
        "trajectory_interval": positive_int(run, "trajectory_interval_steps"),
        "energy_interval": positive_int(run, "energy_interval_steps"),
        "restart_interval": positive_int(run, "restart_interval_steps"),
        "seed": seed,
        "mask_1": string_value(umbrella, "atom_mask_1"),
        "mask_2": string_value(umbrella, "atom_mask_2"),
        "distance_interval": positive_int(umbrella, "distance_output_interval_steps"),
        "whole_molecule_mask": string_value(ratchet, "whole_molecule_mask"),
        "target_distance_angstrom": positive_float(ratchet, "target_distance"),
        "kappa": positive_float(ratchet, "kappa"),
        "path_steps": positive_int(ratchet, "path_generation_steps"),
        "ratchet_output_interval": positive_int(ratchet, "output_interval_steps"),
        "density_minimum": density_minimum,
        "density_maximum": density_maximum,
    }


def write_build_inputs(
    output: Path,
    values: dict[str, object],
    salt_pairs: int | None,
) -> None:
    water_model = str(values["water_model"])
    water_source = "leaprc.water.opc" if water_model == "OPC" else "leaprc.water.tip3p"
    water_box = "OPCBOX" if water_model == "OPC" else "TIP3PBOX"
    solvate = "solvateoct" if values["box_shape"] == "octahedral" else "solvatebox"
    lines = [
        "source leaprc.protein.ff19SB",
        f"source {water_source}",
        "system = loadpdb input.pdb",
        "check system",
        f"{solvate} system {water_box} {float(values['box_distance']):.3f}",
    ]
    if salt_pairs is None:
        lines.extend(["savepdb system solvated.pdb", "quit"])
        filename = "tleap.solvate.in"
    else:
        salt = values["salt"]
        cation = str(salt["cation"])
        anion = str(salt["anion"])
        cation_count = salt_pairs * int(salt["cation_count"])
        anion_count = salt_pairs * int(salt["anion_count"])
        lines.extend(
            [
                f"addionsrand system {cation} 0",
                f"addionsrand system {anion} 0",
                f"addionsrand system {cation} {cation_count}",
                f"addionsrand system {anion} {anion_count}",
                "check system",
                "saveamberparm system system.parm7 system.rst7",
                "savepdb system system.pdb",
                "quit",
            ]
        )
        filename = "tleap.final.in"
    input_dir = output / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


def seed_value(values: dict[str, object]) -> int:
    return -1 if values["seed"] == "random" else int(values["seed"])


def common_dynamics(values: dict[str, object], ensemble: str) -> list[str]:
    return [
        "imin=0",
        "irest=1",
        "ntx=5",
        "ig=-1",
        f"dt={float(values['timestep_ps']):.6f}",
        f"temp0={float(values['temperature']):.3f}",
        "ntt=3",
        "gamma_ln=1.0",
        *amber_ensemble_lines(ensemble, float(values["pressure"])),
        "ntc=2",
        "ntf=2",
        "cut=10.0",
        f"ntwx={int(values['trajectory_interval'])}",
        f"ntwr={int(values['restart_interval'])}",
        f"ntpr={int(values['energy_interval'])}",
        "ioutfm=1",
    ]


def heating_text(values: dict[str, object], title: str) -> str:
    runtime = values["runtime"]
    initial = float(runtime["heating_initial_temperature"])
    steps = int(values["heating_steps"])
    salt = values["salt"]
    mask = f"!:WAT,{salt['cation']},{salt['anion']} & !@H="
    text = render_cntrl(
        title,
        [
            "imin=0",
            "irest=0",
            "ntx=1",
            f"ig={seed_value(values)}",
            f"nstlim={steps}",
            f"dt={float(values['timestep_ps']):.6f}",
            f"tempi={initial:.3f}",
            f"temp0={float(values['temperature']):.3f}",
            "ntt=3",
            "gamma_ln=1.0",
            "ntb=1",
            "ntp=0",
            "ntc=2",
            "ntf=2",
            "cut=10.0",
            "ntr=1",
            "restraint_wt=2.0",
            f"restraintmask='{mask}'",
            f"ntwx={int(values['trajectory_interval'])}",
            f"ntwr={int(values['restart_interval'])}",
            f"ntpr={int(values['energy_interval'])}",
            "ioutfm=1",
            "nmropt=1",
        ],
    )
    return text + (
        "&wt\n"
        "  type='TEMP0',\n"
        "  istep1=0,\n"
        f"  istep2={steps},\n"
        f"  value1={initial:.3f},\n"
        f"  value2={float(values['temperature']):.3f},\n"
        "/\n"
        "&wt type='END' /\n"
    )


def write_rmd_inputs(output: Path, values: dict[str, object]) -> None:
    input_dir = output / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    runtime = values["runtime"]
    salt = values["salt"]
    solute_mask = f"!:WAT,{salt['cation']},{salt['anion']} & !@H="
    minimization_steps = int(runtime["minimization_steps"])
    steepest_steps = int(runtime["minimization_steepest_steps"])

    (input_dir / "min-solvent.in").write_text(
        render_cntrl(
            "Minimize solvent while restraining the solute",
            [
                "imin=1",
                f"maxcyc={minimization_steps}",
                f"ncyc={steepest_steps}",
                "ntc=1",
                "ntf=1",
                "ntb=1",
                "cut=10.0",
                "ntr=1",
                "restraint_wt=10.0",
                f"restraintmask='{solute_mask}'",
            ],
        ),
        encoding="utf-8",
    )
    (input_dir / "min-all.in").write_text(
        render_cntrl(
            "Minimize the complete system",
            [
                "imin=1",
                f"maxcyc={minimization_steps}",
                f"ncyc={steepest_steps}",
                "ntc=1",
                "ntf=1",
                "ntb=1",
                "cut=10.0",
                "ntr=0",
            ],
        ),
        encoding="utf-8",
    )
    (input_dir / "heat.in").write_text(
        heating_text(values, "Heat before ratchet MD"), encoding="utf-8"
    )
    (input_dir / "equil.in").write_text(
        render_cntrl(
            "Equilibrate before ratchet MD",
            [
                f"nstlim={int(values['equilibration_steps'])}",
                *common_dynamics(values, str(runtime["equilibration_ensemble"])),
                "ntr=1",
                "restraint_wt=1.0",
                f"restraintmask='{solute_mask}'",
            ],
        ),
        encoding="utf-8",
    )
    (input_dir / "ratchet.in").write_text(
        render_cntrl(
            "Generate a target-directed ratchet-MD pathway",
            [
                f"nstlim={int(values['path_steps'])}",
                *common_dynamics(values, str(runtime["production_ensemble"])),
                "ntr=0",
                "plumed=1",
                "plumedfile='plumed.dat'",
            ],
        ),
        encoding="utf-8",
    )


def write_us_inputs(output: Path, values: dict[str, object], atom_1: int, atom_2: int) -> None:
    input_dir = output / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    runtime = values["runtime"]
    (input_dir / "min.in").write_text(
        render_cntrl(
            "Minimize an umbrella seed with the window restraint active",
            [
                "imin=1",
                f"maxcyc={int(runtime['minimization_steps'])}",
                f"ncyc={int(runtime['minimization_steepest_steps'])}",
                "ntc=1",
                "ntf=1",
                "ntb=1",
                "cut=10.0",
                "ntr=0",
                "nmropt=1",
            ],
        )
        + "&wt type='END' /\nDISANG=restraint.RST\n",
        encoding="utf-8",
    )
    (input_dir / "heat.in").write_text(
        heating_text(values, "Heat an umbrella window")
        + "DISANG=restraint.RST\n",
        encoding="utf-8",
    )
    (input_dir / "equil.in").write_text(
        render_cntrl(
            "Equilibrate an umbrella window",
            [
                f"nstlim={int(values['equilibration_steps'])}",
                *common_dynamics(values, str(runtime["equilibration_ensemble"])),
                "ntr=0",
                "nmropt=1",
            ],
        )
        + "&wt type='END' /\nDISANG=restraint.RST\n",
        encoding="utf-8",
    )
    production = render_cntrl(
        "Umbrella production",
        [
            f"nstlim={int(values['production_steps'])}",
            *common_dynamics(values, str(runtime["production_ensemble"])),
            "ntr=0",
            "nmropt=1",
        ],
    )
    restraint_block = (
        "&wt\n"
        "  type='DUMPFREQ',\n"
        f"  istep1={int(values['distance_interval'])},\n"
        "/\n"
        "&wt type='END' /\n"
        "DISANG=restraint.RST\n"
    )
    (input_dir / "production.in").write_text(
        production + restraint_block + "DUMPAVE=distance.dat\n",
        encoding="utf-8",
    )
    (input_dir / "continue.in").write_text(
        production + restraint_block + "DUMPAVE=distance-cont.dat\n",
        encoding="utf-8",
    )
    (output / "restraint.RST.template").write_text(
        "&rst\n"
        f" iat={atom_1},{atom_2},\n"
        " r1=0.0,\n"
        " r2=CENTER,\n"
        " r3=CENTER,\n"
        " r4=99.0,\n"
        " rk2=FORCE,\n"
        " rk3=FORCE,\n"
        "/\n",
        encoding="utf-8",
    )


def selected_atoms(topology: Path, mask: str) -> list[int]:
    try:
        import parmed
        from parmed.amber.mask import AmberMask
    except ImportError as error:
        raise ValueError("ParmEd is required to resolve rMD/US atom masks") from error
    structure = parmed.load_file(str(topology))
    return [
        index + 1
        for index, selected in enumerate(AmberMask(structure, mask).Selection())
        if selected
    ]


def one_atom(topology: Path, mask: str) -> int:
    atoms = selected_atoms(topology, mask)
    if len(atoms) != 1:
        raise ValueError(f"mask must select exactly one atom: {mask} selected {len(atoms)}")
    return atoms[0]


def compress_atom_ranges(atoms: list[int]) -> str:
    if not atoms:
        raise ValueError("whole_molecule_mask selected no atoms")
    ranges: list[str] = []
    start = previous = atoms[0]
    for atom in atoms[1:]:
        if atom == previous + 1:
            previous = atom
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = atom
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(ranges)


def write_plumed(output: Path, values: dict[str, object], topology: Path) -> None:
    atom_1 = one_atom(topology, str(values["mask_1"]))
    atom_2 = one_atom(topology, str(values["mask_2"]))
    if atom_1 == atom_2:
        raise ValueError("atom_mask_1 and atom_mask_2 select the same atom")
    molecule = compress_atom_ranges(
        selected_atoms(topology, str(values["whole_molecule_mask"]))
    )
    target_nm = float(values["target_distance_angstrom"]) / 10.0
    (output / "plumed.dat").write_text(
        f"WHOLEMOLECULES ENTITY0={molecule}\n"
        f"reaction_coordinate: DISTANCE ATOMS={atom_1},{atom_2} NOPBC\n"
        "ratchet: ABMD ARG=reaction_coordinate "
        f"TO={target_nm:.6f} KAPPA={float(values['kappa']):.6f}\n"
        "PRINT ARG=reaction_coordinate,ratchet.bias,ratchet.reaction_coordinate_min "
        f"STRIDE={int(values['ratchet_output_interval'])} FILE=ratchet.dat\n",
        encoding="utf-8",
    )


def write_resolved(config_path: Path, output: Path, salt_pairs: int | None) -> None:
    text = config_path.read_text(encoding="utf-8").rstrip() + "\n"
    pair_value = -1 if salt_pairs is None else salt_pairs
    (output / "resolved_config.toml").write_text(
        text + f"\n[generated]\nsalt_pairs = {pair_value}\n", encoding="utf-8"
    )


def main() -> None:
    args = parse_arguments()
    if args.salt_pairs is not None and args.salt_pairs < 0:
        raise SystemExit("--salt-pairs must be zero or greater")
    try:
        values = resolve(args.config)
        args.output.mkdir(parents=True, exist_ok=True)
        if args.mode == "build":
            write_build_inputs(args.output, values, args.salt_pairs)
            write_resolved(args.config, args.output, args.salt_pairs)
            apply_config(args.config, args.output)
        elif args.mode == "rmd":
            if args.topology is None or not args.topology.is_file():
                raise ValueError("rmd mode requires --topology PARM7")
            write_rmd_inputs(args.output, values)
            write_plumed(args.output, values, args.topology)
        else:
            if args.topology is None or not args.topology.is_file():
                raise ValueError("us mode requires --topology PARM7")
            atom_1 = one_atom(args.topology, str(values["mask_1"]))
            atom_2 = one_atom(args.topology, str(values["mask_2"]))
            if atom_1 == atom_2:
                raise ValueError("atom_mask_1 and atom_mask_2 select the same atom")
            write_us_inputs(args.output, values, atom_1, atom_2)
    except (OSError, ValueError) as error:
        raise SystemExit(f"Config error: {error}") from None


if __name__ == "__main__":
    main()
