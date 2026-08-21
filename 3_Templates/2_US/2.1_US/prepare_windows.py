#!/usr/bin/env python3
"""Select ordered umbrella seeds from a ratchet MD trajectory."""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "../../common")
from apply_config import apply_config  # noqa: E402
from config_utils import load_config, positive_float, positive_int, section, string_value  # noqa: E402


def parse_arguments() -> argparse.Namespace:
    """Read the directed trajectory and optional path overrides."""
    parser = argparse.ArgumentParser(
        description="Select ordered US seeds and create restrained window directories."
    )
    parser.add_argument("trajectory", type=Path, help="target-directed AMBER trajectory")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="TOML configuration file (default: config.toml)",
    )
    parser.add_argument(
        "--topology",
        type=Path,
        default=Path("work/system.parm7"),
        help="AMBER topology used to evaluate the reaction coordinate",
    )
    parser.add_argument(
        "--windows",
        type=Path,
        default=None,
        help="Window-center file; defaults to the path in the config",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("work/windows"),
        help="Directory for selected window seeds and restraints",
    )
    parser.add_argument(
        "--cpptraj",
        default="cpptraj",
        help="cpptraj executable or command name (default: cpptraj)",
    )
    parser.add_argument(
        "--max-error",
        dest="max_error_angstrom",
        type=float,
        default=None,
        help="Tolerance for the difference between the target center and frame distance (Å)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print planned frame selections without writing windows",
    )
    return parser.parse_args()


def read_centers(path: Path) -> list[float]:
    """Read window centers and validate positivity, uniqueness, and order."""
    centers: list[float] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 1:
                raise ValueError(f"{path}:{line_number}: expected one CENTER_A column.")
            center = float(fields[0])
            if center <= 0:
                raise ValueError(f"{path}:{line_number}: center must be positive.")
            centers.append(center)
    if not centers:
        raise ValueError(f"window center is missing: {path}")
    if centers != sorted(centers) or len(centers) != len(set(centers)):
        raise ValueError("Window centers must be unique and increasing.")
    return centers


def run_cpptraj(executable: str, topology: Path, commands: str) -> None:
    """Pass a command block to cpptraj stdin and preserve failure output."""
    result = subprocess.run(
        [executable, "-p", str(topology)],
        input=commands,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"cpptraj failed: {detail}")


def calculate_distances(
    executable: str,
    topology: Path,
    trajectory: Path,
    output: Path,
    mask_1: str,
    mask_2: str,
) -> list[tuple[int, float]]:
    """Calculate the terminal C-alpha distance for each trajectory frame."""
    commands = (
        f"trajin {trajectory}\n"
        f"distance reaction_coordinate {mask_1} {mask_2} out {output} noimage\n"
        "run\n"
    )
    run_cpptraj(executable, topology, commands)

    values: list[tuple[int, float]] = []
    with output.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            values.append((int(float(fields[0])), float(fields[1])))
    if not values:
        raise RuntimeError("cpptraj end-to-end distance output is empty.")
    return values


def select_crossings(
    values: list[tuple[int, float]],
    centers_angstrom: list[float],
    max_error_angstrom: float,
) -> list[tuple[int, float, float]]:
    """Select frames near first crossings while preserving center order."""
    selected: list[tuple[int, float, float]] = []
    start = 0

    for center_angstrom in centers_angstrom:
        crossing = None
        for index in range(start, len(values)):
            if values[index][1] >= center_angstrom:
                crossing = index
                break

        if crossing is None:
            candidates = range(start, len(values))
        else:
            candidates = [crossing]
            if crossing > start:
                candidates.append(crossing - 1)

        try:
            best = min(
                candidates,
                key=lambda index: abs(values[index][1] - center_angstrom),
            )
        except ValueError as exc:
            raise RuntimeError(
                f"Trajectory has no frame for the {center_angstrom:.3f} Å window."
            ) from exc

        frame, observed = values[best]
        error = abs(observed - center_angstrom)

        if error > max_error_angstrom:
            raise RuntimeError(
                f"No frame is within the {max_error_angstrom:.3f} Å tolerance of "
                f"center {center_angstrom:.3f} Å. The nearest ordered frame is "
                f"{frame} at {observed:.3f} Å."
            )
        selected.append((frame, observed, error))
        start = best + 1

    return selected


def extract_restarts(
    executable: str,
    topology: Path,
    trajectory: Path,
    output_dir: Path,
    selected: list[tuple[int, float, float]],
) -> None:
    """Extract selected frames as per-window AMBER restart files."""
    commands = [f"trajin {trajectory}"]
    for window, (frame, _, _) in enumerate(selected, start=1):
        seed = output_dir / f"seed_{window:03d}.rst7"
        commands.append(f"trajout {seed} restart onlyframes {frame}")
    commands.append("run")
    run_cpptraj(executable, topology, "\n".join(commands) + "\n")

    missing = [
        output_dir / f"seed_{window:03d}.rst7"
        for window in range(1, len(selected) + 1)
        if not (output_dir / f"seed_{window:03d}.rst7").is_file()
    ]
    if missing:
        raise RuntimeError(f"cpptraj seed restart was not created: {missing[0]}")


def write_metadata(
    path: Path,
    centers_angstrom: list[float],
    selected: list[tuple[int, float, float]],
) -> None:
    """Write window targets, selected frames, distances, and errors as TSV."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["window", "target_A", "frame", "observed_A", "error_A"])
        for window, (center, selection) in enumerate(
            zip(centers_angstrom, selected),
            start=1,
        ):
            frame, observed, error = selection
            writer.writerow(
                [window, f"{center:.3f}", frame, f"{observed:.6f}", f"{error:.6f}"]
            )


def resolve_single_atom(topology: Path, mask: str) -> int:
    """Resolve an AMBER mask and require exactly one selected atom."""
    try:
        import parmed
        from parmed.amber.mask import AmberMask
    except ImportError as error:
        raise RuntimeError("ParmEd is required to validate umbrella atom masks") from error
    structure = parmed.load_file(str(topology))
    selected = [
        index + 1
        for index, value in enumerate(AmberMask(structure, mask).Selection())
        if value
    ]
    if len(selected) != 1:
        raise ValueError(f"mask must select exactly one atom: {mask} selected {len(selected)}")
    return selected[0]


def create_window_files(
    output: Path,
    topology: Path,
    windows: Path,
    atom_1: int,
    atom_2: int,
    force: float,
) -> None:
    """Place the shared topology, seed, restraint, and metadata in each window."""
    rows = [
        line.split()
        for line in windows.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    for window_number, fields in enumerate(rows, start=1):
        center = fields[0]
        window = output / f"{window_number:03d}"
        window.mkdir()
        shutil.copy2(topology, window / "system.parm7")
        shutil.move(output / f"seed_{window_number:03d}.rst7", window / "seed.rst7")
        (window / "restraint.RST").write_text(
            "&rst\n"
            f" iat={atom_1},{atom_2},\n"
            f" r1=0.0, r2={center}, r3={center}, r4=999.0,\n"
            f" rk2={force:.6f}, rk3={force:.6f},\n"
            "/\n",
            encoding="utf-8",
        )
        (window / "window.tsv").write_text(
            f"window\tcenter_A\tforce_kcal_mol_A2\n{window_number:03d}\t{center}\t{force:.6f}\n",
            encoding="utf-8",
        )


def create_md_inputs(output: Path, config: dict[str, object]) -> None:
    """Generate the four restrained AMBER stages used by every window."""
    run = section(config, "run")
    umbrella = section(config, "umbrella")
    temperature = positive_float(run, "temperature_kelvin")
    pressure = positive_float(run, "pressure_bar")
    timestep = positive_float(run, "timestep_fs") / 1000.0
    interval = positive_int(run, "trajectory_interval_steps")
    if positive_int(run, "production_segments") != 1:
        raise ValueError("umbrella sampling currently supports production_segments=1")
    stages = {
        "min.in": ["imin=1", "maxcyc=5000", "ncyc=2500", "ntb=1", "cut=10.0", "nmropt=1"],
        "heat.in": ["imin=0", "irest=0", "ntx=1", f"nstlim={positive_int(run, 'heating_steps')}", f"dt={timestep:.6f}", "tempi=20.0", f"temp0={temperature:.3f}", "ntt=3", "gamma_ln=1.0", "ig=-1", "ntb=1", "ntp=0", "ntc=2", "ntf=2", "cut=10.0", "ntr=1", "restraint_wt=2.0", "restraintmask='!:WAT,Na+,Cl- & !@H='", f"ntpr={interval}", f"ntwx={interval}", f"ntwr={interval}", "ioutfm=1", "nmropt=1"],
        "equil.in": ["imin=0", "irest=1", "ntx=5", f"nstlim={positive_int(run, 'equilibration_steps')}", f"dt={timestep:.6f}", f"temp0={temperature:.3f}", "ntt=3", "gamma_ln=1.0", "ig=-1", "ntb=2", "ntp=1", "barostat=2", f"pres0={pressure:.3f}", "taup=2.0", "ntc=2", "ntf=2", "cut=10.0", f"ntpr={interval}", f"ntwx={interval}", f"ntwr={interval}", "ioutfm=1", "nmropt=1"],
        "production.in": ["imin=0", "irest=1", "ntx=5", f"nstlim={positive_int(run, 'production_steps')}", f"dt={timestep:.6f}", f"temp0={temperature:.3f}", "ntt=3", "gamma_ln=1.0", "ig=-1", "ntb=2", "ntp=1", "barostat=2", f"pres0={pressure:.3f}", "taup=2.0", "ntc=2", "ntf=2", "cut=10.0", f"ntpr={interval}", f"ntwx={interval}", f"ntwr={interval}", "ioutfm=1", "nmropt=1"],
    }
    input_dir = output / "inputs"
    input_dir.mkdir()
    for name, values in stages.items():
        body = "\n".join(f" {value}," for value in values)
        suffix = "\n&wt type='END' /\nDISANG=restraint.RST\n"
        if name == "heat.in":
            heating_steps = positive_int(run, "heating_steps")
            suffix = (
                "\n&wt\n"
                " type='TEMP0',\n"
                " istep1=0,\n"
                f" istep2={heating_steps},\n"
                " value1=20.0,\n"
                f" value2={temperature:.3f},\n"
                "/\n"
                "&wt type='END' /\n"
                "DISANG=restraint.RST\n"
            )
        elif name == "production.in":
            frequency = positive_int(umbrella, "distance_output_interval_steps")
            suffix = f"\n&wt type='DUMPFREQ', istep1={frequency}, /\n&wt type='END' /\nDISANG=restraint.RST\nDUMPAVE=distance.dat\n"
        (input_dir / name).write_text(f"Umbrella {name}\n&cntrl\n{body}\n/\n{suffix}", encoding="utf-8")


def main() -> int:
    args = parse_arguments()

    config = load_config(args.config)
    umbrella = section(config, "umbrella")
    mask_1 = string_value(umbrella, "atom_mask_1")
    mask_2 = string_value(umbrella, "atom_mask_2")
    force = positive_float(umbrella, "force_constant_kcal_mol_angstrom2")
    if args.windows is None:
        args.windows = Path(string_value(umbrella, "windows_file"))
    if args.max_error_angstrom is None:
        args.max_error_angstrom = positive_float(umbrella, "seed_max_error_angstrom")

    if not args.windows.is_file():
        raise SystemExit(f"window settings not found: {args.windows}")

    if args.max_error_angstrom <= 0:
        raise SystemExit("--max-error must be greater than zero.")

    try:
        centers_angstrom = read_centers(args.windows)
    except (OSError, ValueError) as error:
        raise SystemExit(f"window settings Error: {error}") from None

    if args.dry_run:
        print(f"topology: {args.topology}")
        print(f"trajectory: {args.trajectory}")
        print(f"seed output: {args.output} ({len(centers_angstrom)} windows)")
        return 0

    if shutil.which(args.cpptraj) is None:
        raise SystemExit(f"cpptraj not found: {args.cpptraj}")
    for path in (args.topology, args.trajectory, args.windows):
        if not path.is_file():
            raise SystemExit(f"Required input not found: {path}")
    if args.output.exists():
        raise SystemExit(f"Output directory already exists: {args.output}")

    args.output.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory(prefix="us_seed_") as temp_dir:
            distances = Path(temp_dir) / "distance.dat"
            values = calculate_distances(
                args.cpptraj,
                args.topology.resolve(),
                args.trajectory.resolve(),
                distances,
                mask_1,
                mask_2,
            )
        selected = select_crossings(
            values,
            centers_angstrom,
            args.max_error_angstrom,
        )
        extract_restarts(
            args.cpptraj,
            args.topology.resolve(),
            args.trajectory.resolve(),
            args.output.resolve(),
            selected,
        )
        write_metadata(args.output / "seeds.tsv", centers_angstrom, selected)
        atom_1 = resolve_single_atom(args.topology, mask_1)
        atom_2 = resolve_single_atom(args.topology, mask_2)
        if atom_1 == atom_2:
            raise ValueError("atom_mask_1 and atom_mask_2 select the same atom")
        create_window_files(args.output, args.topology, args.windows, atom_1, atom_2, force)
        create_md_inputs(args.output, config)
        apply_config(args.config, args.output.parent)
    except (OSError, RuntimeError, ValueError) as error:
        if args.output.exists() and not any(args.output.iterdir()):
            args.output.rmdir()
        raise SystemExit(f"Error: {error}") from None

    print(f"Created {len(centers_angstrom)} umbrella windows: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
