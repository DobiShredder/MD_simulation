#!/usr/bin/env python3
"""Generate config-driven REUS or GaREUS window directories."""

from __future__ import annotations

import argparse
import csv
import secrets
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from apply_config import apply_amber_ensemble, apply_config  # noqa: E402
from config_utils import load_config, positive_float, positive_int, section, string_value  # noqa: E402

# Langevin dynamics (ntt=3) should use a different ig on each restart
# (Amber26 manual, ig). An integer random_seed gives each restarted stage its
# own offset; window seeds are 7919 apart, so offsets do not collide below 126 windows.
STAGE_SEED_OFFSET = 1_000_000
EQUILIBRATION_SEED_STAGE = 1
GAMD_PREPARATION_SEED_STAGE = 2
FIRST_PRODUCTION_SEED_STAGE = 3


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create REUS/GaREUS states, restraints, and AMBER inputs.")
    parser.add_argument(
        "method",
        choices=("reus", "gareus"),
        help="Window-replica method to generate",
    )
    parser.add_argument("config", type=Path, help="TOML configuration file")
    parser.add_argument("topology", type=Path, help="Shared AMBER parm7 topology")
    parser.add_argument("output", type=Path, help="Directory for generated replicas")
    return parser.parse_args()


def resolve_group(topology: Path, mask: str) -> list[int]:
    """Return the 1-based atom numbers selected by one reaction-coordinate mask."""
    try:
        import parmed
        from parmed.amber.mask import AmberMask
    except ImportError as error:
        raise SystemExit("ParmEd is required to validate replica-window masks") from error
    structure = parmed.load_file(str(topology))
    selected = [index + 1 for index, value in enumerate(AmberMask(structure, mask).Selection()) if value]
    if not selected:
        raise SystemExit(f"Mask must select at least one atom: {mask}")
    return selected


def restraint_atom_fields(group_1: list[int], group_2: list[int]) -> str:
    """Return the &rst atom fields of the distance restraint.

    A single atom goes directly into iat. For a group, iat(n) = -1 and igr<n>
    lists its atoms; with the default ir6 = 0 AMBER restrains the group's center
    of mass (Amber26 manual, section 31.1.1: iat, igr1/igr2, ir6). sander allows
    at most 200 atoms per group; pmemd allows up to the system atom count.
    """
    if set(group_1) & set(group_2):
        raise SystemExit("The two reaction-coordinate masks must not select the same atom")
    iat = []
    group_lines = []
    for group_number, group in enumerate((group_1, group_2), 1):
        if len(group) == 1:
            iat.append(str(group[0]))
            continue
        iat.append("-1")
        # Ten atoms per line keeps large groups readable in distance.RST.
        chunks = [",".join(str(atom) for atom in group[start:start + 10]) for start in range(0, len(group), 10)]
        group_lines.append(f" igr{group_number}=" + ",\n  ".join(chunks) + ",")
    return "\n".join([f" iat={iat[0]},{iat[1]},", *group_lines])


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
        raise SystemExit(f"{path}: window centers must be non-empty, unique, and increasing")
    if len(result) < 2 or len(result) % 2:
        raise SystemExit(f"Replica exchange requires at least two and an even number of windows: {path} ({len(result)} windows)")
    return result


def check_reference_replica(gamd: dict[str, object], window_count: int) -> int:
    value = gamd.get("reference_replica")
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < window_count:
        raise SystemExit(
            f"Config error: gamd.reference_replica must be a window index from 0 to {window_count - 1}"
        )
    return value


def window_seeds(value: object, count: int) -> list[int]:
    if value == "random":
        seeds: set[int] = set()
        while len(seeds) < count:
            seeds.add(secrets.randbelow(900_000_000) + 1)
        return list(seeds)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SystemExit("Config error: random_seed must be 'random' or a positive integer")
    return [value + 7919 * index for index in range(count)]


def shared_seed(value: object, window_count: int) -> int:
    """Seed for the shared heating stage that runs once before the windows."""
    if value == "random":
        return secrets.randbelow(900_000_000) + 1
    # The next value in the window seed sequence, so it never repeats a window seed.
    return value + 7919 * window_count


def write_shared_inputs(
    directory: Path,
    run: dict[str, object],
    dynamics: list[str],
    npt: list[str],
    seed: int,
    random_seed: object,
) -> None:
    """Heat and NPT-equilibrate the unbiased system once (Amber26 manual, REMD).

    NVT replica exchange needs every replica at the same volume, so all GaREUS
    windows start from the box written by this shared NPT stage.
    """
    directory.mkdir()
    temperature = positive_float(run, "temperature")
    heating_steps = positive_int(run, "heating_steps")
    unbiased = [value for value in dynamics if value != "nmropt=1"]
    (directory / "minimize.in").write_text(
        "Shared system minimization\n&cntrl\n imin=1,\n maxcyc=5000,\n ncyc=2500,\n"
        " ntb=1,\n cut=10.0,\n ntpr=100,\n/\n",
        encoding="utf-8",
    )
    heat_values = [
        "imin=0", "irest=0", "ntx=1", f"ig={seed}", f"nstlim={heating_steps}",
        "tempi=20.0", "ntb=1", "ntp=0", *unbiased, "nmropt=1",
    ]
    (directory / "heat.in").write_text(
        "Shared heating\n&cntrl\n"
        + "\n".join(f" {value}," for value in heat_values)
        + "\n/\n&wt\n type='TEMP0',\n istep1=0,\n"
        + f" istep2={heating_steps},\n value1=20.0,\n value2={temperature:.3f},\n/\n"
        + "&wt type='END' /\n",
        encoding="utf-8",
    )
    equilibrate_values = [
        "imin=0", "irest=1", "ntx=5",
        f"ig={stage_seed(random_seed, seed, EQUILIBRATION_SEED_STAGE)}",
        f"nstlim={positive_int(run, 'equilibration_steps')}", *npt, *unbiased,
    ]
    (directory / "equilibrate.in").write_text(
        "Shared NPT equilibration\n&cntrl\n"
        + "\n".join(f" {value}," for value in equilibrate_values)
        + "\n/\n",
        encoding="utf-8",
    )


def stage_seed(random_seed: object, window_seed: int, seed_stage: int) -> int:
    """Return ig for a restarted stage: wall-clock seed or an offset integer seed."""
    if random_seed == "random":
        return -1
    return window_seed + STAGE_SEED_OFFSET * seed_stage


def render(
    title: str,
    values: list[str],
    dump_frequency: int | None = None,
    dump_file: str = "",
    disang_file: str = "distance.RST",
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
        tail = (
            f"\n&wt type='DUMPFREQ', istep1={dump_frequency}, /\n"
            "&wt type='END' /\n"
            f"DISANG={disang_file}\n"
            f"DUMPAVE={dump_file}\n"
        )
    return f"{title}\n&cntrl\n{body}\n/\n{tail}"


def main() -> None:
    args = arguments()
    config = load_config(args.config)
    run = section(config, "run")
    umbrella = section(config, "umbrella")
    state_centers = read_centers(Path(string_value(umbrella, "windows_file")))
    # Each mask selects one atom or an atom group (restrained at its center of mass).
    atom_fields = restraint_atom_fields(
        resolve_group(args.topology, string_value(umbrella, "atom_mask_1")),
        resolve_group(args.topology, string_value(umbrella, "atom_mask_2")),
    )

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

    if args.method == "gareus":
        check_reference_replica(section(config, "gamd"), len(state_centers))
        if str(run.get("equilibration_ensemble", "")).upper() != "NPT":
            raise SystemExit(
                "Config error: GaREUS requires equilibration_ensemble = \"NPT\" for the shared "
                "stage that fixes the window volume"
            )
        window_equilibration_steps = positive_int(run, "window_equilibration_steps")
    random_seed = run.get("random_seed")
    seeds = window_seeds(random_seed, len(state_centers))
    dump_frequency = positive_int(umbrella, "distance_output_interval_steps")

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "states.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("replica", "window_center_A", "seed"))
        for index, center in enumerate(state_centers):
            writer.writerow((f"{index:03d}", f"{center:.6f}", seeds[index]))

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
    if args.method == "gareus":
        write_shared_inputs(
            args.output / "shared",
            run,
            dynamics,
            npt,
            shared_seed(random_seed, len(state_centers)),
            random_seed,
        )
    for index, center in enumerate(state_centers):
        replica = f"{index:03d}"
        seed = seeds[index]
        directory = args.output / replica
        directory.mkdir()
        (directory / "distance.RST").write_text(f"&rst\n{atom_fields}\n r1=0.0, r2={center:.6f}, r3={center:.6f}, r4=999.0,\n rk2={force:.6f}, rk3={force:.6f},\n/\n", encoding="utf-8")
        if args.method == "gareus":
            # Each window starts from the shared NPT box and keeps that volume.
            (directory / "equilibrate.in").write_text(
                render(
                    "Window NVT equilibration in the shared box",
                    [
                        "imin=0",
                        "irest=1",
                        "ntx=5",
                        f"ig={stage_seed(random_seed, seed, EQUILIBRATION_SEED_STAGE)}",
                        f"nstlim={window_equilibration_steps}",
                        "ntb=1",
                        "ntp=0",
                        *dynamics,
                    ],
                    dump_frequency,
                    "restraint.equilibrate.dat",
                ),
                encoding="utf-8",
            )
        else:
            (directory / "minimize.in").write_text(render("Window minimization", ["imin=1", "maxcyc=5000", "ncyc=2500", "ntb=1", "cut=10.0", "nmropt=1"]), encoding="utf-8")
            heating_steps = positive_int(run, "heating_steps")
            (directory / "heat.in").write_text(
                render(
                    "Window heating",
                    [
                        "imin=0",
                        "irest=0",
                        "ntx=1",
                        f"ig={seed}",
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
                        f"ig={stage_seed(random_seed, seed, EQUILIBRATION_SEED_STAGE)}",
                        f"nstlim={positive_int(run, 'equilibration_steps')}",
                        *npt,
                        *dynamics,
                    ],
                    dump_frequency,
                    "restraint.equilibrate.dat",
                ),
                encoding="utf-8",
            )
        production_ensemble = ["ntb=1", "ntp=0"] if args.method == "gareus" else npt
        values = ["imin=0", "irest=1", "ntx=5", f"nstlim={exchange}", f"numexchg={production_per_segment // exchange}", *production_ensemble, *dynamics]
        if args.method == "gareus":
            gamd = section(config, "gamd")
            values.extend(["igamd=3", "iE=1", "irest_gamd=1", "ntcmdprep=0", "ntcmd=0", "ntebprep=0", "nteb=0", f"ntave={positive_int(gamd, 'averaging_interval_steps')}", f"sigma0P={positive_float(gamd, 'sigma0'):.3f}", f"sigma0D={positive_float(gamd, 'sigma0'):.3f}"])
            conventional = positive_int(gamd, "conventional_statistics_steps")
            boost = positive_int(gamd, "boost_statistics_steps")
            gamd_prepare = ["imin=0", "irest=1", "ntx=5", f"ig={stage_seed(random_seed, seed, GAMD_PREPARATION_SEED_STAGE)}", f"nstlim={conventional + boost}", *production_ensemble, *dynamics, "igamd=3", "iE=1", "irest_gamd=0", f"ntcmdprep={positive_int(gamd, 'conventional_preparation_steps')}", f"ntcmd={conventional}", f"ntebprep={positive_int(gamd, 'boost_preparation_steps')}", f"nteb={boost}", f"ntave={positive_int(gamd, 'averaging_interval_steps')}", f"sigma0P={positive_float(gamd, 'sigma0'):.3f}", f"sigma0D={positive_float(gamd, 'sigma0'):.3f}"]
            (directory / "gamd_prepare.in").write_text(render("Shared GaMD parameter preparation", gamd_prepare, dump_frequency, "restraint.gamd_prepare.dat"), encoding="utf-8")
        # Exchange production runs from the tutorial directory through the group file,
        # so run.sh replaces @DISANG@ and @DUMPAVE@ with work-directory paths.
        for segment in range(1, segments + 1):
            segment_seed = stage_seed(random_seed, seed, FIRST_PRODUCTION_SEED_STAGE + segment - 1)
            segment_values = [*values[:3], f"ig={segment_seed}", *values[3:]]
            (directory / f"production.{segment:03d}.template.in").write_text(
                render("Replica-exchange production", segment_values, dump_frequency, "@DUMPAVE@", "@DISANG@"),
                encoding="utf-8",
            )

    resolved = args.output / "resolved_config.toml"
    shutil.copy2(args.config, resolved)
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[replica_exchange]\nreplicas = {len(state_centers)}\nexchange_interval_steps = {exchange}\n")
    apply_config(args.config, args.output)
    if args.method == "gareus":
        # apply_config gives every equilibrate.in the equilibration_ensemble (the shared
        # NPT stage). Window equilibration must stay NVT in the shared box.
        for index in range(len(state_centers)):
            path = args.output / f"{index:03d}" / "equilibrate.in"
            path.write_text(apply_amber_ensemble(path.read_text(encoding="utf-8"), "NVT", pressure, "isotropic"), encoding="utf-8")
    print(f"Created {len(state_centers)} {args.method.upper()} windows: {args.output}")


if __name__ == "__main__":
    main()
