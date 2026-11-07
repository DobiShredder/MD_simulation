#!/usr/bin/env python3
"""Validate RBFE selections and generate environment/lambda window inputs."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from apply_config import apply_config, synchronize_resolved_section  # noqa: E402
from config_utils import finite_float, load_config, positive_float, positive_int, section, string_value  # noqa: E402


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


def heating_seed_base(run: dict[str, object]) -> int | None:
    """Return the integer heating-seed base, or None for AMBER's random ig=-1."""
    seed = run.get("random_seed")
    if seed == "random":
        return None
    if isinstance(seed, bool) or not isinstance(seed, int) or seed <= 0:
        raise ValueError("random_seed must be 'random' or a positive integer")
    return seed


# Soft-core values used when [alchemical] omits a key. They match the values the
# templates wrote before these options were exposed. gti_* = 0 are pmemd.cuda
# defaults (Amber26 manual 27.1.7.1, p. 559-560) and are not written to mdin.
SOFTCORE_DEFAULTS: dict[str, float | int] = {
    "scalpha": 0.5,
    "scbeta": 12.0,
    "gti_lam_sch": 0,
    "gti_ele_sc": 0,
    "gti_vdw_sc": 0,
}
GTI_SOFTCORE_KEYS = ("gti_lam_sch", "gti_ele_sc", "gti_vdw_sc")


def softcore_settings(alchemical: dict[str, object]) -> dict[str, float | int]:
    """Read and check the soft-core and lambda-scheduling options."""
    settings: dict[str, float | int] = {}
    for key in ("scalpha", "scbeta"):
        value = finite_float(alchemical, key, default=SOFTCORE_DEFAULTS[key])
        if value <= 0:
            raise ValueError(f"{key} must be greater than zero")
        settings[key] = value
    for key in GTI_SOFTCORE_KEYS:
        value = alchemical.get(key, SOFTCORE_DEFAULTS[key])
        if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
            raise ValueError(f"{key} must be integer 0 or 1")
        settings[key] = value
    return settings


def gti_softcore_lines(settings: dict[str, float | int]) -> str:
    """Return the gti_* mdin lines, or nothing when all three keep the default 0.

    With gti_lam_sch=1 pmemd changes the default of gti_ele_sc and gti_vdw_sc
    to 1, so all three are written as soon as one of them is enabled.
    """
    if not any(settings[key] for key in GTI_SOFTCORE_KEYS):
        return ""
    return "".join(f"\n  {key}={settings[key]}," for key in GTI_SOFTCORE_KEYS)


def selected_indices(topology: object, mask: str) -> list[int]:
    from parmed.amber.mask import AmberMask

    return [index + 1 for index, value in enumerate(AmberMask(topology, mask).Selection()) if value]


# Tutorial builds place mapped atoms within about 0.01 A. A larger gap means the
# two ligand MOL2 files are not overlaid in one coordinate frame.
CORE_TOLERANCE_ANGSTROM = 0.1


def read_mapping(config: dict[str, object]) -> list[tuple[str, str]]:
    build = section(config, "build")
    mapping_path = Path(string_value(build, "atom_mapping_file"))
    if not mapping_path.is_file():
        raise ValueError(f"atom mapping file not found: {mapping_path}")
    rows: list[tuple[str, str]] = []
    with mapping_path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 2:
                raise ValueError(f"{mapping_path}:{line_number}: expected two atom-name columns")
            rows.append((fields[0], fields[1]))
    if not rows:
        raise ValueError(f"atom mapping file contains no mappings: {mapping_path}")
    if len({row[0] for row in rows}) != len(rows) or len({row[1] for row in rows}) != len(rows):
        raise ValueError("atom mapping must be one-to-one")
    return rows


def ligand_atoms(topology: object, mask: str) -> tuple[str, dict[str, object]]:
    """Return the residue name and atoms selected by one ligand mask."""
    atoms = [topology.atoms[index - 1] for index in selected_indices(topology, mask)]
    if not atoms:
        raise ValueError(f"ligand mask selects no atoms: {mask}")
    residues = {atom.residue for atom in atoms}
    if len(residues) != 1:
        raise ValueError(f"ligand mask must select one residue: {mask}")
    residue = next(iter(residues))
    if len(atoms) != len(residue.atoms):
        raise ValueError(f"ligand mask must select the whole residue: {mask}")
    if sum(1 for item in topology.residues if item.name == residue.name) != 1:
        raise ValueError(f"ligand residue name must be unique in the topology: {residue.name}")
    names = [atom.name for atom in atoms]
    if len(set(names)) != len(names):
        raise ValueError(f"ligand atom names must be unique: {residue.name}")
    return residue.name, {atom.name: atom for atom in atoms}


def common_core(
    topology: object,
    mask_a: str,
    mask_b: str,
    mapping: list[tuple[str, str]],
) -> tuple[str, str, list[tuple[object, object]]]:
    """Return scmask1, scmask2 and the mapped atom pairs for one environment."""
    residue_a, atoms_a = ligand_atoms(topology, mask_a)
    residue_b, atoms_b = ligand_atoms(topology, mask_b)
    for name_a, name_b in mapping:
        if name_a not in atoms_a or name_b not in atoms_b:
            raise ValueError(f"mapped atom is absent from its ligand: {name_a} {name_b}")
    pairs = sorted(((atoms_a[a], atoms_b[b]) for a, b in mapping), key=lambda pair: pair[0].idx)

    # pmemd pairs the timask atoms outside scmask by their order, so mapped
    # atoms must appear in the same order in both ligands.
    order_b = [atom_b.idx for _, atom_b in pairs]
    if order_b != sorted(order_b):
        raise ValueError("mapped ligand B atoms are not in the same order as their ligand A partners")

    mapped_a = {atom_a.name for atom_a, _ in pairs}
    mapped_b = {atom_b.name for _, atom_b in pairs}
    unique_a = [name for name in atoms_a if name not in mapped_a]
    unique_b = [name for name in atoms_b if name not in mapped_b]
    scmask_a = f":{residue_a}@{','.join(unique_a)}" if unique_a else ""
    scmask_b = f":{residue_b}@{','.join(unique_b)}" if unique_b else ""
    return scmask_a, scmask_b, pairs


def synchronize_core(rst7: Path, output: Path, pairs: list[tuple[object, object]]) -> float:
    """Copy ligand B core coordinates onto the mapped ligand A atoms."""
    import parmed

    restart = parmed.amber.Rst7.open(str(rst7))
    coordinates = restart.coordinates.reshape(-1, 3)
    largest = 0.0
    for atom_a, atom_b in pairs:
        gap = float(((coordinates[atom_a.idx] - coordinates[atom_b.idx]) ** 2).sum() ** 0.5)
        largest = max(largest, gap)
        coordinates[atom_a.idx] = coordinates[atom_b.idx]
    if largest > CORE_TOLERANCE_ANGSTROM:
        raise ValueError(f"mapped core atoms differ by {largest:.3f} A (limit {CORE_TOLERANCE_ANGSTROM} A): {rst7}")
    restart.coordinates = coordinates.reshape(1, -1, 3)
    restart.write(str(output))
    return largest


def relative_link(target: Path, link: Path) -> None:
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(os.path.relpath(target, link.parent))


def render(template: Path, output: Path, replacements: dict[str, str]) -> None:
    text = template.read_text(encoding="utf-8")
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    # Soft-core masks contain "@", so look only for unreplaced @NAME@ markers.
    if re.search(r"@[A-Z_]+@", text):
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
        seed_base = heating_seed_base(run)
        softcore = softcore_settings(alchemical)
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None

    try:
        mapping = read_mapping(config)
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None

    # Each environment has its own atom indices and restart, so the common core
    # is resolved and synchronized separately for complex and solvent.
    soft_core_masks: dict[str, tuple[str, str]] = {}
    for environment in ("complex", "solvent"):
        topology_file = args.work_dir / "build" / f"{environment}.parm7"
        topology = parmed.load_file(str(topology_file))
        selected_a = selected_indices(topology, mask_a)
        selected_b = selected_indices(topology, mask_b)
        if not selected_a or not selected_b:
            raise SystemExit(f"Both RBFE ligand masks must select at least one atom: {topology_file}")
        if set(selected_a).intersection(selected_b):
            raise SystemExit(f"RBFE ligand masks overlap: {topology_file}")
        try:
            scmask_a, scmask_b, pairs = common_core(topology, mask_a, mask_b, mapping)
            largest = synchronize_core(
                args.work_dir / "build" / f"{environment}.rst7",
                args.work_dir / "build" / f"{environment}_core.rst7",
                pairs,
            )
        except ValueError as error:
            raise SystemExit(f"Common-core error ({environment}): {error}") from None
        soft_core_masks[environment] = (scmask_a, scmask_b)
        print(
            f"{environment}: {len(pairs)} common-core atoms (largest pre-sync gap {largest:.4f} A); "
            f"scmask1='{scmask_a}', scmask2='{scmask_b}'"
        )
    if soft_core_masks["complex"] != soft_core_masks["solvent"]:
        raise SystemExit("Complex and solvent soft-core masks differ; check the ligand atom names")
    scmask_a, scmask_b = soft_core_masks["complex"]

    common = {
        "@MASK_A@": mask_a,
        "@MASK_B@": mask_b,
        "@SCMASK_A@": scmask_a,
        "@SCMASK_B@": scmask_b,
        "@SCALPHA@": repr(softcore["scalpha"]),
        "@SCBETA@": repr(softcore["scbeta"]),
        "@GTI_SOFTCORE_OPTIONS@": gti_softcore_lines(softcore),
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
            # Only heating starts new velocities; later stages restart with ig=-1.
            heating_seed = -1 if seed_base is None else seed_base + state_index
            window = f"{window_index:03d}"
            directory = args.work_dir / environment / window
            directory.mkdir(parents=True, exist_ok=True)
            relative_link(args.work_dir / "build" / f"{environment}.parm7", directory / "system.parm7")
            relative_link(args.work_dir / "build" / f"{environment}_core.rst7", directory / "system.rst7")
            replacements = {
                **common,
                "@LAMBDA@": f"{lambda_value:.6f}",
                "@RANDOM_SEED@": str(heating_seed),
            }
            for stage in ("minimize", "heat", "equilibrate", "production"):
                render(args.input_dir / f"{stage}.in.template", directory / f"{stage}.in", replacements)
            states.append(f"{environment}\t{window}\t{lambda_value:.6f}\t{heating_seed}\t{directory}")

    (args.work_dir / "states.tsv").write_text("\n".join(states) + "\n", encoding="utf-8")
    (args.work_dir / "atom_mapping.resolved.tsv").write_text(
        "ligand_a_atom\tligand_b_atom\n" + "".join(f"{left}\t{right}\n" for left, right in mapping),
        encoding="utf-8",
    )
    # The resolved config records the soft-core values actually written to mdin.
    resolved_text = synchronize_resolved_section(
        args.config.read_text(encoding="utf-8"),
        "alchemical",
        softcore,
    )
    (args.work_dir / "resolved_config.toml").write_text(resolved_text, encoding="utf-8")
    apply_config(args.config, args.work_dir)


if __name__ == "__main__":
    main()
