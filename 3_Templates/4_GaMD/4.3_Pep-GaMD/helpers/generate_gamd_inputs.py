#!/usr/bin/env python3
"""Generate method-specific Amber 26 GaMD input files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from apply_config import apply_config  # noqa: E402
from config_utils import load_config, positive_float, positive_int, section, string_value  # noqa: E402


METHOD_SETTINGS = {
    "gamd": {"igamd": 3, "selection": None, "thresholds": "iE=1"},
    "ligamd3": {"igamd": 28, "selection": "ligand", "thresholds": "iE=1, iEP=2, iED=1, iEB=1"},
    "pepgamd": {"igamd": 15, "selection": "peptide", "thresholds": "iE=1, iEP=1, iED=1"},
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate GaMD preparation and production inputs from config.toml."
    )
    parser.add_argument(
        "method",
        choices=METHOD_SETTINGS,
        help="GaMD variant that determines the boost terms and atom selection",
    )
    parser.add_argument("config", type=Path, help="TOML configuration file")
    parser.add_argument("topology", type=Path, help="AMBER topology used to validate masks")
    parser.add_argument("output", type=Path, help="Directory for generated GaMD inputs")
    return parser.parse_args()


def amber_mask_indices(topology: Path, mask: str) -> list[int]:
    try:
        import parmed
        from parmed.amber.mask import AmberMask
    except ImportError as error:
        raise SystemExit("ParmEd is required to validate GaMD atom masks") from error

    structure = parmed.load_file(str(topology))
    selection = AmberMask(structure, mask).Selection()
    return [index + 1 for index, selected in enumerate(selection) if selected]


def render(title: str, values: list[str]) -> str:
    body = "\n".join(f"  {value}," for value in values)
    return f"{title}\n&cntrl\n{body}\n/\n"


def main() -> None:
    args = parse_arguments()
    config = load_config(args.config)
    run = section(config, "run")
    gamd = section(config, "gamd")
    settings = METHOD_SETTINGS[args.method]

    timestep = positive_float(run, "timestep")
    temperature = positive_float(run, "temperature")
    interval = positive_int(run, "trajectory_interval_steps")
    production_steps = positive_int(run, "production_steps")
    segments = positive_int(run, "production_segments")
    if production_steps % segments != 0:
        raise SystemExit("production_steps must be divisible by production_segments")

    conventional_preparation = positive_int(gamd, "conventional_preparation_steps")
    conventional_statistics = positive_int(gamd, "conventional_statistics_steps")
    boost_preparation = positive_int(gamd, "boost_preparation_steps")
    boost_statistics = positive_int(gamd, "boost_statistics_steps")
    averaging = positive_int(gamd, "averaging_interval_steps")
    for name, value in (
        ("conventional_preparation_steps", conventional_preparation),
        ("conventional_statistics_steps", conventional_statistics),
        ("boost_preparation_steps", boost_preparation),
        ("boost_statistics_steps", boost_statistics),
    ):
        if value % averaging != 0:
            raise SystemExit(f"{name} must be a multiple of averaging_interval_steps")

    sigma = positive_float(gamd, "sigma0")
    method_lines: list[str] = []
    resolved_lines: list[str] = []
    selection = settings["selection"]
    if selection is not None:
        mask_key = f"{selection}_mask"
        mask = string_value(gamd, mask_key)
        selected = amber_mask_indices(args.topology, mask)
        if not selected:
            raise SystemExit(f"{mask_key} does not select any atoms: {mask}")
        method_lines.extend(
            [
                "icfe=1",
                "ifsc=1",
                "gti_cpu_output=0",
                "gti_add_sc=1",
                f"timask1='{mask}'",
                f"scmask1='{mask}'",
                "timask2=''",
                "scmask2=''",
            ]
        )
        resolved_lines.append(f'{mask_key} = "{mask}"')

        if args.method == "ligamd3":
            receptor_mask = string_value(gamd, "receptor_mask")
            receptor = amber_mask_indices(args.topology, receptor_mask)
            if not receptor:
                raise SystemExit(f"receptor_mask does not select any atoms: {receptor_mask}")
            if receptor != list(range(receptor[0], receptor[-1] + 1)):
                raise SystemExit("LiGaMD3 receptor_mask must select one contiguous atom range")
            if set(receptor).intersection(selected):
                raise SystemExit("ligand_mask and receptor_mask overlap")
            method_lines.extend([f"bgpro2atm={receptor[0]}", f"edpro2atm={receptor[-1]}"])
            resolved_lines.extend(
                [f'receptor_mask = "{receptor_mask}"', f"receptor_first_atom = {receptor[0]}", f"receptor_last_atom = {receptor[-1]}"]
            )

    force_evaluation = 1 if selection is not None else 2
    common = [
        "imin=0", "irest=1", "ntx=5", f"dt={timestep / 1000.0:.6f}",
        f"temp0={temperature:.3f}", "ntt=3", "gamma_ln=1.0", "ig=-1",
        "ntb=1", "ntp=0", "ntc=2", f"ntf={force_evaluation}", "cut=10.0", "iwrap=0",
        f"ntpr={interval}", f"ntwx={interval}", f"ntwr={interval}", "ioutfm=1",
        f"igamd={settings['igamd']}", settings["thresholds"], *method_lines,
    ]
    preparation_steps = conventional_statistics + boost_statistics
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "gamd_prepare.in").write_text(
        render(
            "GaMD parameter preparation",
            [
                f"nstlim={preparation_steps}", *common, "irest_gamd=0",
                f"ntcmdprep={conventional_preparation}", f"ntcmd={conventional_statistics}",
                f"ntebprep={boost_preparation}", f"nteb={boost_statistics}",
                f"ntave={averaging}", f"sigma0P={sigma:.3f}", f"sigma0D={sigma:.3f}",
                *( [f"sigma0B={sigma:.3f}"] if args.method == "ligamd3" else [] ),
            ],
        ),
        encoding="utf-8",
    )
    (args.output / "production.in").write_text(
        render(
            "GaMD production segment",
            [
                f"nstlim={production_steps // segments}", *common, "irest_gamd=1",
                "ntcmdprep=0", "ntcmd=0", "ntebprep=0", "nteb=0",
                f"ntave={averaging}", f"sigma0P={sigma:.3f}", f"sigma0D={sigma:.3f}",
                *( [f"sigma0B={sigma:.3f}"] if args.method == "ligamd3" else [] ),
            ],
        ),
        encoding="utf-8",
    )

    resolved = args.output.parent / "resolved_config.toml"
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n[gamd]\n"
            f'method = "{args.method}"\n'
            f"igamd = {settings['igamd']}\n"
            f"conventional_preparation_steps = {conventional_preparation}\n"
            f"conventional_statistics_steps = {conventional_statistics}\n"
            f"boost_preparation_steps = {boost_preparation}\n"
            f"boost_statistics_steps = {boost_statistics}\n"
            f"averaging_interval_steps = {averaging}\n"
            f"sigma0 = {sigma:.3f}\n"
            + "\n".join(resolved_lines)
            + ("\n" if resolved_lines else "")
        )
    apply_config(args.config, args.output.parent)


if __name__ == "__main__":
    main()
