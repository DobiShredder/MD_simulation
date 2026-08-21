#!/usr/bin/env python3
"""Generate ABFE restraints and inputs for 65 alchemical windows."""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import parmed
from parmed.geometry import dihedral as parmed_dihedral

sys.path.insert(0, ".")
from apply_config import apply_config  # noqa: E402
from config_utils import load_config, positive_float, positive_int, section, string_value  # noqa: E402


RestraintRecord = tuple[str, list[object], float, float]


def window_directory(
    work_dir: Path,
    stage: str,
    environment: str,
    window: str,
) -> Path:
    if stage == "restraint":
        interaction = "restraint"
    elif stage.endswith("_charge"):
        interaction = "charge"
    elif stage.endswith("_vdw"):
        interaction = "vdw"
    else:
        raise SystemExit(f"Unsupported ABFE stage: {stage}")
    return work_dir / interaction / environment / window


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate config-driven Amber ABFE windows.")
    parser.add_argument("config", type=Path, help="TOML configuration file")
    parser.add_argument("work_dir", type=Path, help="Directory containing built ABFE systems")
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


def vector(a: list[float], b: list[float]) -> list[float]:
    return [b[index] - a[index] for index in range(3)]


def dot(a: list[float], b: list[float]) -> float:
    return sum(left * right for left, right in zip(a, b))


def norm(a: list[float]) -> float:
    return math.sqrt(dot(a, a))


def distance(a: list[float], b: list[float]) -> float:
    return norm(vector(a, b))


def angle(a: list[float], b: list[float], c: list[float]) -> float:
    left, right = vector(b, a), vector(b, c)
    cosine = max(-1.0, min(1.0, dot(left, right) / (norm(left) * norm(right))))
    return math.degrees(math.acos(cosine))


def dihedral(a: list[float], b: list[float], c: list[float], d: list[float]) -> float:
    return float(parmed_dihedral(a, b, c, d))


def atom_from_mask(topology: object, mask: str) -> object:
    from parmed.amber.mask import AmberMask

    selected = [
        topology.atoms[index]
        for index, value in enumerate(AmberMask(topology, mask).Selection())
        if value
    ]
    if len(selected) != 1:
        raise ValueError(f"Anchor mask must select exactly one atom: {mask} selected {len(selected)}")
    return selected[0]


def restraint_records(
    topology: object,
    restraints: dict[str, object],
) -> list[RestraintRecord]:
    p1, p2, p3 = [
        atom_from_mask(topology, string_value(restraints, f"protein_anchor_{index}"))
        for index in range(1, 4)
    ]
    l1, l2, l3 = [
        atom_from_mask(topology, string_value(restraints, f"ligand_anchor_{index}"))
        for index in range(1, 4)
    ]
    anchors = [p1, p2, p3, l1, l2, l3]
    if len({atom.idx for atom in anchors}) != 6:
        raise ValueError("The six ABFE anchor masks must select six distinct atoms")
    distance_force = positive_float(restraints, "distance_force")
    angular_force = positive_float(restraints, "angle_force")
    torsion_force = positive_float(restraints, "torsion_force")
    xyz = lambda atom: list(topology.coordinates[atom.idx])
    return [
        ("distance", [p1, l1], distance(xyz(p1), xyz(l1)), distance_force),
        ("angle_a", [p2, p1, l1], angle(xyz(p2), xyz(p1), xyz(l1)), angular_force),
        ("angle_b", [p1, l1, l2], angle(xyz(p1), xyz(l1), xyz(l2)), angular_force),
        ("dihedral_a", [p3, p2, p1, l1], dihedral(xyz(p3), xyz(p2), xyz(p1), xyz(l1)), torsion_force),
        ("dihedral_b", [p2, p1, l1, l2], dihedral(xyz(p2), xyz(p1), xyz(l1), xyz(l2)), torsion_force),
        ("dihedral_c", [p1, l1, l2, l3], dihedral(xyz(p1), xyz(l1), xyz(l2), xyz(l3)), torsion_force),
    ]


def write_restraints(
    path: Path,
    records: list[RestraintRecord],
    scale: float,
) -> None:
    lines: list[str] = []
    for kind, atoms, reference, force in records:
        indices = ",".join(str(atom.idx + 1) for atom in atoms)
        width = 2.0 if kind == "distance" else 180.0
        lines.append(
            f"&rst iat={indices}, r1={reference-width:.6f}, r2={reference:.6f}, "
            f"r3={reference:.6f}, r4={reference+width:.6f}, "
            f"rk2={force*scale:.6f}, rk3={force*scale:.6f}, /"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render(template: Path, output: Path, replacements: dict[str, str]) -> None:
    text = template.read_text(encoding="utf-8")
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    if "@" in text:
        raise SystemExit(f"Unreplaced marker found: {output}")
    output.write_text(text, encoding="utf-8")


def relative_link(target: Path, link: Path) -> None:
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(os.path.relpath(target, link.parent))


def write_uncharged_topology(source: Path, destination: Path, ligand_mask: str) -> None:
    topology = parmed.load_file(str(source))
    from parmed.amber.mask import AmberMask

    selected = [index for index, value in enumerate(AmberMask(topology, ligand_mask).Selection()) if value]
    if not selected:
        raise ValueError(f"Ligand mask selects no atoms in {source}: {ligand_mask}")
    for index in selected:
        topology.atoms[index].charge = 0.0
    topology.save(str(destination), overwrite=True)


def alchemical_options(
    stage: str,
    lambda_value: float,
    schedule: list[float],
    collect_mbar: bool,
    ligand_mask: str,
    mbar_interval: int,
) -> str:
    common = f"icfe=1, clambda={lambda_value:.6f}, "
    if stage == "restraint":
        common += (
            f" timask1='{ligand_mask}', timask2='{ligand_mask}',"
            " ifsc=0, aces26=1, gti_nmropt=1,"
            " gti_sc_cc_energy_terms='', gti_sc_sc_energy_terms='',"
        )
    elif stage.endswith("vdw"):
        common += (
            f" timask1='{ligand_mask}', timask2='',"
            f" ifsc=1, scmask1='{ligand_mask}', scmask2='', scalpha=0.5, scbeta=12.0,"
            " aces26=1, gti_sc_cc_energy_terms='ele,vdw,ele14,vdw14',"
            " gti_sc_sc_energy_terms='', gti_nmropt=0,"
        )
    else:
        common += (
            f" timask1='{ligand_mask}', timask2='{ligand_mask}',"
            f" crgmask='{ligand_mask}', ifsc=0,"
        )
    if collect_mbar:
        mbar_lambda = ",".join(f"{value:.6f}" for value in schedule)
        common += (
            f" ifmbar=1, mbar_states={len(schedule)},"
            f" mbar_lambda={mbar_lambda}, bar_intervall={mbar_interval},"
        )
    return common


def prepare_alchemical_topologies(work_dir: Path, ligand_mask: str) -> None:
    """Create the neutral-ligand topologies used by the VDW stages."""
    for environment in ("complex", "solvent"):
        write_uncharged_topology(
            work_dir / "build" / f"{environment}.parm7",
            work_dir / "build" / f"{environment}_uncharged.parm7",
            ligand_mask,
        )


def write_restraint_metadata(work_dir: Path, records: list[RestraintRecord]) -> None:
    """Record the six Boresch restraints next to the generated windows."""
    lines = ["restraint\treference\tforce_constant\tatom_indices"]
    for kind, atoms, reference, force in records:
        atom_indices = ",".join(str(atom.idx + 1) for atom in atoms)
        lines.append(f"{kind}\t{reference:.8f}\t{force:.8f}\t{atom_indices}")
    (work_dir / "restraints.tsv").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_window(
    work_dir: Path,
    input_dir: Path,
    stage: str,
    environment: str,
    schedule: list[float],
    window_index: int,
    lambda_value: float,
    state_index: int,
    records: list[RestraintRecord],
    ligand_mask: str,
    common_replacements: dict[str, str],
    mbar_interval: int,
) -> str:
    """Generate links, restraints, and AMBER inputs for one ABFE window."""
    window = f"{window_index:03d}"
    directory = window_directory(work_dir, stage, environment, window)
    directory.mkdir(parents=True, exist_ok=True)

    topology_name = (
        f"{environment}_uncharged.parm7"
        if stage.endswith("vdw")
        else f"{environment}.parm7"
    )
    relative_link(work_dir / "build" / topology_name, directory / "system.parm7")
    relative_link(
        work_dir / "build" / f"{environment}.rst7",
        directory / "system.rst7",
    )

    restraint_scale = 1.0 if environment == "complex" else 0.0
    write_restraints(directory / "disang.rest", records, restraint_scale)

    replacements = {
        **common_replacements,
        "@STAGE@": stage,
        "@LAMBDA@": f"{lambda_value:.6f}",
        "@RANDOM_SEED@": str(61000 + state_index),
        "@RESTRAINT_OPTIONS@": "nmropt=1," if environment == "complex" else "",
        "@WT_END@": "&wt type='END', /" if environment == "complex" else "",
        "@DISANG@": "DISANG=disang.rest" if environment == "complex" else "",
    }
    for name in ("heat", "equilibrate", "production"):
        replacements["@ALCHEMICAL_OPTIONS@"] = alchemical_options(
            stage,
            lambda_value,
            schedule,
            collect_mbar=name == "production",
            ligand_mask=ligand_mask,
            mbar_interval=mbar_interval,
        )
        render(
            input_dir / f"{name}.in.template",
            directory / f"{name}.in",
            replacements,
        )
    render(input_dir / "minimize.in", directory / "minimize.in", replacements)

    return (
        f"{stage}\t{environment}\t{window}\t{lambda_value:.6f}\t"
        f"{61000 + state_index}\t{directory}"
    )


def main() -> None:
    args = parse_arguments()
    try:
        config = load_config(args.config)
        run = section(config, "run")
        alchemical = section(config, "alchemical")
        restraints = section(config, "restraints")
        restraint_schedule = float_list(alchemical, "restraint_lambdas")
        charge_schedule = float_list(alchemical, "charge_lambdas")
        vdw_schedule = float_list(alchemical, "vdw_lambdas")
        ligand_mask = string_value(alchemical, "ligand_mask")
        standard_state = positive_float(alchemical, "standard_state_concentration")
        segments = positive_int(run, "production_segments")
        if segments != 1:
            raise ValueError("ABFE currently supports production_segments=1")
        common_replacements = {
            "@TIMESTEP_PS@": f"{positive_float(run, 'timestep') / 1000.0:.6f}",
            "@TEMPERATURE@": f"{positive_float(run, 'temperature'):.3f}",
            "@PRESSURE@": f"{positive_float(run, 'pressure'):.3f}",
            "@HEATING_STEPS@": str(positive_int(run, "heating_steps")),
            "@EQUILIBRATION_STEPS@": str(positive_int(run, "equilibration_steps")),
            "@PRODUCTION_STEPS@": str(positive_int(run, "production_steps_per_window")),
            "@TRAJECTORY_INTERVAL@": str(positive_int(run, "trajectory_interval_steps")),
        }
        mbar_interval = positive_int(run, "mbar_interval_steps")
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None

    stages = [
        ("restraint", "complex", restraint_schedule),
        ("complex_charge", "complex", charge_schedule),
        ("complex_vdw", "complex", vdw_schedule),
        ("solvent_charge", "solvent", charge_schedule),
        ("solvent_vdw", "solvent", vdw_schedule),
    ]
    topology = parmed.load_file(
        str(args.work_dir / "build" / "complex.parm7"),
        xyz=str(args.work_dir / "build" / "complex.rst7"),
    )
    try:
        prepare_alchemical_topologies(args.work_dir, ligand_mask)
        records = restraint_records(topology, restraints)
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None
    write_restraint_metadata(args.work_dir, records)

    states = ["stage\tenvironment\twindow\tlambda\tseed\tdirectory"]
    state_index = 0
    for stage, environment, schedule in stages:
        for window_index, lambda_value in enumerate(schedule):
            state_index += 1
            states.append(
                write_window(
                    args.work_dir,
                    args.input_dir,
                    stage,
                    environment,
                    schedule,
                    window_index,
                    lambda_value,
                    state_index,
                    records,
                    ligand_mask,
                    common_replacements,
                    mbar_interval,
                )
            )
    (args.work_dir / "states.tsv").write_text("\n".join(states) + "\n", encoding="utf-8")
    (args.work_dir / "standard_state.tsv").write_text(
        f"temperature_K\tstandard_state_concentration_M\n{positive_float(run, 'temperature'):.6f}\t{standard_state:.6f}\n",
        encoding="utf-8",
    )
    (args.work_dir / "resolved_config.toml").write_text(
        args.config.read_text(encoding="utf-8"), encoding="utf-8"
    )
    apply_config(args.config, args.work_dir)


if __name__ == "__main__":
    main()
