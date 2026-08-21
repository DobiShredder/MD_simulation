#!/usr/bin/env python3
"""Validate RBFE selections and generate environment/lambda window inputs."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, "../../common")
from apply_config import apply_config  # noqa: E402
from config_utils import load_config, positive_float, positive_int, section, string_value  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate config-driven Amber RBFE windows.")
    parser.add_argument("config", type=Path, help="TOML configuration file")
    parser.add_argument("work_dir", type=Path, help="Directory containing built RBFE systems")
    parser.add_argument("input_dir", type=Path, help="Directory for shared generated inputs")
    return parser.parse_args()


def float_list(values: dict[str, object], key: str) -> list[float]:
    raw = values.get(key)
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{key} must be a non-empty array")
    result: list[float] = []
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{key} must contain only numbers")
        result.append(float(item))
    if result != sorted(set(result)) or result[0] != 0.0 or result[-1] != 1.0:
        raise ValueError(f"{key} must be unique, increasing, and span 0.0 to 1.0")
    return result


def selected_indices(topology: object, mask: str) -> list[int]:
    from parmed.amber.mask import AmberMask

    return [index + 1 for index, value in enumerate(AmberMask(topology, mask).Selection()) if value]


def validate_mapping(config: dict[str, object], topology: object, mask_a: str, mask_b: str) -> list[tuple[str, str]]:
    build = section(config, "build")
    mapping_path = Path(string_value(build, "atom_mapping_file"))
    if not mapping_path.is_file():
        raise ValueError(f"atom mapping file not found: {mapping_path}")

    atoms_a = {topology.atoms[index - 1].name for index in selected_indices(topology, mask_a)}
    atoms_b = {topology.atoms[index - 1].name for index in selected_indices(topology, mask_b)}
    rows: list[tuple[str, str]] = []
    with mapping_path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 2:
                raise ValueError(f"{mapping_path}:{line_number}: expected two atom-name columns")
            if fields[0] not in atoms_a or fields[1] not in atoms_b:
                raise ValueError(f"{mapping_path}:{line_number}: mapped atom name is absent from its ligand")
            rows.append((fields[0], fields[1]))
    if not rows:
        raise ValueError("atom mapping file contains no mappings")
    if len({row[0] for row in rows}) != len(rows) or len({row[1] for row in rows}) != len(rows):
        raise ValueError("atom mapping must be one-to-one")
    return rows


def relative_link(target: Path, link: Path) -> None:
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(os.path.relpath(target, link.parent))


def render(template: Path, output: Path, replacements: dict[str, str]) -> None:
    text = template.read_text(encoding="utf-8")
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    if "@" in text:
        raise ValueError(f"Unreplaced marker found: {output}")
    output.write_text(text, encoding="utf-8")


def main() -> None:
    args = arguments()
    try:
        import parmed
    except ImportError as error:
        raise SystemExit("ParmEd is required to generate RBFE windows") from error

    try:
        config = load_config(args.config)
        run = section(config, "run")
        alchemical = section(config, "alchemical")
        lambdas = float_list(alchemical, "lambda_values")
        mask_a = string_value(alchemical, "ligand_a_mask")
        mask_b = string_value(alchemical, "ligand_b_mask")
        timestep_ps = positive_float(run, "timestep") / 1000.0
        heating = positive_int(run, "heating_steps")
        equilibration = positive_int(run, "equilibration_steps")
        production = positive_int(run, "production_steps_per_window")
        segments = positive_int(run, "production_segments")
        if segments != 1:
            raise ValueError("RBFE currently supports production_segments=1")
        interval = positive_int(run, "trajectory_interval_steps")
        mbar_interval = positive_int(run, "mbar_interval_steps")
        temperature = positive_float(run, "temperature")
        pressure = positive_float(run, "pressure")
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None

    complex_topology = parmed.load_file(str(args.work_dir / "build/complex.parm7"))
    selected_a = selected_indices(complex_topology, mask_a)
    selected_b = selected_indices(complex_topology, mask_b)
    if not selected_a or not selected_b:
        raise SystemExit("Both RBFE ligand masks must select at least one atom")
    if set(selected_a).intersection(selected_b):
        raise SystemExit("RBFE ligand masks overlap")
    try:
        mapping = validate_mapping(config, complex_topology, mask_a, mask_b)
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None

    common = {
        "@MASK_A@": mask_a,
        "@MASK_B@": mask_b,
        "@TIMESTEP_PS@": f"{timestep_ps:.6f}",
        "@TEMPERATURE@": f"{temperature:.3f}",
        "@PRESSURE@": f"{pressure:.3f}",
        "@HEATING_STEPS@": str(heating),
        "@EQUILIBRATION_STEPS@": str(equilibration),
        "@PRODUCTION_STEPS@": str(production),
        "@TRAJECTORY_INTERVAL@": str(interval),
        "@MBAR_INTERVAL@": str(mbar_interval),
        "@MBAR_STATES@": str(len(lambdas)),
        "@MBAR_LAMBDAS@": ",".join(f"{value:.6f}" for value in lambdas),
    }
    states = ["environment\twindow\tlambda\tseed\tdirectory"]
    state_index = 0
    for environment in ("complex", "solvent"):
        for window_index, lambda_value in enumerate(lambdas):
            state_index += 1
            window = f"{window_index:03d}"
            directory = args.work_dir / environment / window
            directory.mkdir(parents=True, exist_ok=True)
            relative_link(args.work_dir / "build" / f"{environment}.parm7", directory / "system.parm7")
            relative_link(args.work_dir / "build" / f"{environment}.rst7", directory / "system.rst7")
            replacements = {
                **common,
                "@LAMBDA@": f"{lambda_value:.6f}",
                "@RANDOM_SEED@": str(51000 + state_index),
            }
            for stage in ("minimize", "heat", "equilibrate", "production"):
                render(args.input_dir / f"{stage}.in.template", directory / f"{stage}.in", replacements)
            states.append(f"{environment}\t{window}\t{lambda_value:.6f}\t{51000 + state_index}\t{directory}")

    (args.work_dir / "states.tsv").write_text("\n".join(states) + "\n", encoding="utf-8")
    (args.work_dir / "atom_mapping.resolved.tsv").write_text(
        "ligand_a_atom\tligand_b_atom\n" + "".join(f"{left}\t{right}\n" for left, right in mapping),
        encoding="utf-8",
    )
    (args.work_dir / "resolved_config.toml").write_text(args.config.read_text(encoding="utf-8"), encoding="utf-8")
    apply_config(args.config, args.work_dir)


if __name__ == "__main__":
    main()
