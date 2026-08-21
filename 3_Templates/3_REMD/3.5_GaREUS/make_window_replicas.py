#!/usr/bin/env python3
"""Generate config-driven REUS or GaREUS window directories."""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from apply_config import apply_config  # noqa: E402
from config_utils import load_config, positive_float, positive_int, section, string_value  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create REUS/GaREUS states, restraints, and AMBER inputs.")
    parser.add_argument(
        "method",
        choices=("reus", "gareus"),
        help="Window-replica method to generate",
    )
    parser.add_argument("config", type=Path, help="TOML configuration file")
    parser.add_argument("topology", type=Path, help="Shared AMBER parm7 topology")
    parser.add_argument("coordinates", type=Path, help="Shared AMBER restart coordinates")
    parser.add_argument("output", type=Path, help="Directory for generated replicas")
    return parser.parse_args()


def resolve_atom(topology: Path, mask: str) -> int:
    try:
        import parmed
        from parmed.amber.mask import AmberMask
    except ImportError as error:
        raise SystemExit("ParmEd is required to validate replica-window masks") from error
    structure = parmed.load_file(str(topology))
    selected = [index + 1 for index, value in enumerate(AmberMask(structure, mask).Selection()) if value]
    if len(selected) != 1:
        raise SystemExit(f"Mask must select exactly one atom: {mask} selected {len(selected)}")
    return selected[0]


def read_centers(path: Path) -> list[float]:
    result: list[float] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 1:
            raise SystemExit(f"{path}:{line_number}: expected one center per line")
        result.append(float(fields[0]))
    if not result or result != sorted(set(result)):
        raise SystemExit("Window centers must be non-empty, unique, and increasing")
    return result


def render(
    title: str,
    values: list[str],
    dump_frequency: int | None = None,
    heating_steps: int | None = None,
    temperature: float | None = None,
) -> str:
    body = "\n".join(f" {value}," for value in values)
    tail = "\n&wt type='END' /\nDISANG=distance.RST\n"
    if heating_steps is not None and temperature is not None:
        tail = (
            "\n&wt\n"
            " type='TEMP0',\n"
            " istep1=0,\n"
            f" istep2={heating_steps},\n"
            " value1=20.0,\n"
            f" value2={temperature:.3f},\n"
            "/\n"
            "&wt type='END' /\n"
            "DISANG=distance.RST\n"
        )
    elif dump_frequency is not None:
        tail = f"\n&wt type='DUMPFREQ', istep1={dump_frequency}, /\n&wt type='END' /\nDISANG=@DISANG@\nDUMPAVE=@DUMPAVE@\n"
    return f"{title}\n&cntrl\n{body}\n/\n{tail}"


def main() -> None:
    args = arguments()
    config = load_config(args.config)
    run = section(config, "run")
    umbrella = section(config, "umbrella")
    state_centers = read_centers(Path(string_value(umbrella, "windows_file")))
    atom_1 = resolve_atom(args.topology, string_value(umbrella, "atom_mask_1"))
    atom_2 = resolve_atom(args.topology, string_value(umbrella, "atom_mask_2"))
    if atom_1 == atom_2:
        raise SystemExit("The two reaction-coordinate masks select the same atom")

    force = positive_float(umbrella, "force_constant")
    exchange = positive_int(umbrella, "exchange_interval_steps")
    temperature = positive_float(run, "temperature")
    pressure = positive_float(run, "pressure")
    dt = positive_float(run, "timestep") / 1000.0
    interval = positive_int(run, "trajectory_interval_steps")
    segments = positive_int(run, "production_segments")
    production = positive_int(run, "production_steps")
    if production % segments != 0:
        raise SystemExit("production_steps must be divisible by production_segments")
    production_per_segment = production // segments
    if production_per_segment % exchange != 0:
        raise SystemExit("Production steps per segment must be divisible by exchange_interval_steps")

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "states.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("replica", "window_center_A", "seed"))
        for index, center in enumerate(state_centers):
            writer.writerow((f"{index:03d}", f"{center:.6f}", 510001 + 7919 * index))

    dynamics = [
        f"dt={dt:.6f}",
        f"temp0={temperature:.3f}",
        "ntt=3",
        "gamma_ln=1.0",
        "ntc=2",
        "ntf=2",
        "cut=10.0",
        f"ntpr={interval}",
        f"ntwx={interval}",
        f"ntwr={interval}",
        "ioutfm=1",
        "nmropt=1",
    ]
    npt = [
        "ntb=2",
        "ntp=1",
        "barostat=2",
        f"pres0={pressure:.3f}",
        "taup=2.0",
    ]
    for index, center in enumerate(state_centers):
        replica = f"{index:03d}"
        directory = args.output / replica
        directory.mkdir()
        shutil.copy2(args.topology, directory / "system.parm7")
        shutil.copy2(args.coordinates, directory / "system.rst7")
        (directory / "distance.RST").write_text(f"&rst\n iat={atom_1},{atom_2},\n r1=0.0, r2={center:.6f}, r3={center:.6f}, r4=999.0,\n rk2={force:.6f}, rk3={force:.6f},\n/\n", encoding="utf-8")
        (directory / "minimize.in").write_text(render("Window minimization", ["imin=1", "maxcyc=5000", "ncyc=2500", "ntb=1", "cut=10.0", "nmropt=1"]), encoding="utf-8")
        heating_steps = positive_int(run, "heating_steps")
        (directory / "heat.in").write_text(
            render(
                "Window heating",
                [
                    "imin=0",
                    "irest=0",
                    "ntx=1",
                    f"ig={510001 + 7919 * index}",
                    f"nstlim={heating_steps}",
                    "tempi=20.0",
                    "ntb=1",
                    "ntp=0",
                    *dynamics,
                ],
                heating_steps=heating_steps,
                temperature=temperature,
            ),
            encoding="utf-8",
        )
        (directory / "equilibrate.in").write_text(
            render(
                "Window equilibration",
                [
                    "imin=0",
                    "irest=1",
                    "ntx=5",
                    "ig=-1",
                    f"nstlim={positive_int(run, 'equilibration_steps')}",
                    *npt,
                    *dynamics,
                ],
                positive_int(umbrella, "distance_output_interval_steps"),
            ),
            encoding="utf-8",
        )
        production_ensemble = ["ntb=1", "ntp=0"] if args.method == "gareus" else npt
        values = ["imin=0", "irest=1", "ntx=5", "ig=-1", f"nstlim={exchange}", f"numexchg={production_per_segment // exchange}", *production_ensemble, *dynamics]
        if args.method == "gareus":
            gamd = section(config, "gamd")
            values.extend(["igamd=3", "iE=1", "irest_gamd=1", "ntcmdprep=0", "ntcmd=0", "ntebprep=0", "nteb=0", f"ntave={positive_int(gamd, 'averaging_interval_steps')}", f"sigma0P={positive_float(gamd, 'sigma0'):.3f}", f"sigma0D={positive_float(gamd, 'sigma0'):.3f}"])
            conventional = positive_int(gamd, "conventional_statistics_steps")
            boost = positive_int(gamd, "boost_statistics_steps")
            gamd_prepare = ["imin=0", "irest=1", "ntx=5", "ig=-1", f"nstlim={conventional + boost}", *npt, *dynamics, "igamd=3", "iE=1", "irest_gamd=0", f"ntcmdprep={positive_int(gamd, 'conventional_preparation_steps')}", f"ntcmd={conventional}", f"ntebprep={positive_int(gamd, 'boost_preparation_steps')}", f"nteb={boost}", f"ntave={positive_int(gamd, 'averaging_interval_steps')}", f"sigma0P={positive_float(gamd, 'sigma0'):.3f}", f"sigma0D={positive_float(gamd, 'sigma0'):.3f}"]
            (directory / "gamd_prepare.in").write_text(render("Shared GaMD parameter preparation", gamd_prepare, positive_int(umbrella, "distance_output_interval_steps")), encoding="utf-8")
        (directory / "production.template.in").write_text(render("Replica-exchange production", values, positive_int(umbrella, "distance_output_interval_steps")), encoding="utf-8")

    resolved = args.output / "resolved_config.toml"
    shutil.copy2(args.config, resolved)
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[replica_exchange]\nreplicas = {len(state_centers)}\nexchange_interval_steps = {exchange}\n")
    apply_config(args.config, args.output)
    print(f"Created {len(state_centers)} {args.method.upper()} windows: {args.output}")


if __name__ == "__main__":
    main()
