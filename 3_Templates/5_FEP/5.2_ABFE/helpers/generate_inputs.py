#!/usr/bin/env python3
"""Generate ABFE restraint, charge and vdW inputs for the configured lambda windows."""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
try:
    import parmed
    from parmed.geometry import dihedral as parmed_dihedral
except ImportError:
    raise SystemExit("Error: ParmEd is required for ABFE input generation: python3 -m pip install parmed") from None

sys.path.insert(0, ".")
from apply_config import apply_config, synchronize_resolved_section  # noqa: E402
from config_utils import finite_float, load_config, positive_float, positive_int, section, string_value  # noqa: E402


RestraintRecord = tuple[str, list[object], float, float]
RESTRAINT_DUMP_FILE = "production.restraint.dat"
# Both Boresch angles must stay away from 0 and 180 degrees: near-collinear
# anchors make the angle and dihedral restraints unstable, and the analytical
# standard-state correction divides by sin(theta_A) * sin(theta_B).
BORESCH_ANGLE_MIN_DEGREES = 30.0
BORESCH_ANGLE_MAX_DEGREES = 150.0
# Soft-core values used when [alchemical] omits a key. They match the values the
# template wrote before these options were exposed. gti_* = 0 are pmemd.cuda
# defaults (Amber26 manual 27.1.7.1, p. 559-560) and are not written to mdin.
SOFTCORE_DEFAULTS: dict[str, float | int] = {
    "scalpha": 0.5,
    "scbeta": 12.0,
    "gti_lam_sch": 0,
    "gti_ele_sc": 0,
    "gti_vdw_sc": 0,
}
GTI_SOFTCORE_KEYS = ("gti_lam_sch", "gti_ele_sc", "gti_vdw_sc")


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


def heating_seed_base(run: dict[str, object]) -> int | None:
    """Return the integer heating-seed base, or None for AMBER's random ig=-1."""
    seed = run.get("random_seed")
    if seed == "random":
        return None
    if isinstance(seed, bool) or not isinstance(seed, int) or seed <= 0:
        raise ValueError("random_seed must be 'random' or a positive integer")
    return seed


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


def softcore_settings(alchemical: dict[str, object]) -> dict[str, float | int]:
    """Read and check the soft-core and lambda-scheduling options of the vdW stage."""
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


def softcore_text(settings: dict[str, float | int]) -> str:
    """Return the vdW-stage soft-core keywords for the &cntrl namelist.

    gti_* keywords are omitted while all three keep the default 0. With
    gti_lam_sch=1 pmemd changes the default of gti_ele_sc and gti_vdw_sc to 1,
    so all three are written as soon as one of them is enabled.
    """
    text = f" scalpha={settings['scalpha']!r}, scbeta={settings['scbeta']!r},"
    if any(settings[key] for key in GTI_SOFTCORE_KEYS):
        text += "".join(f" {key}={settings[key]}," for key in GTI_SOFTCORE_KEYS)
    return text


def protein_anchor_masks(restraints: dict[str, object]) -> list[str]:
    """Return the three protein anchor masks, which have no usable default."""
    keys = [f"protein_anchor_{index}" for index in range(1, 4)]
    empty = [key for key in keys if not str(restraints.get(key, "")).strip()]
    if empty:
        raise ValueError(
            f"[restraints] {', '.join(empty)} must be set. Use AMBER masks that each "
            "select one rigid protein atom near the binding site (for example a "
            "backbone CA), with the three atoms not collinear. See 'Choosing Boresch "
            "anchors' in README.md."
        )
    return [string_value(restraints, key) for key in keys]


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
    ligand_mask: str,
) -> list[RestraintRecord]:
    p1, p2, p3 = [atom_from_mask(topology, mask) for mask in protein_anchor_masks(restraints)]
    l1, l2, l3 = [
        atom_from_mask(topology, string_value(restraints, f"ligand_anchor_{index}"))
        for index in range(1, 4)
    ]
    anchors = [p1, p2, p3, l1, l2, l3]
    if len({atom.idx for atom in anchors}) != 6:
        raise ValueError("The six ABFE anchor masks must select six distinct atoms")
    from parmed.amber.mask import AmberMask

    ligand_atoms = {
        index for index, selected in enumerate(AmberMask(topology, ligand_mask).Selection())
        if selected
    }
    if not ligand_atoms:
        raise ValueError(f"Ligand mask selects no atoms: {ligand_mask}")
    for role, role_atoms in (("protein", (p1, p2, p3)), ("ligand", (l1, l2, l3))):
        for index, atom in enumerate(role_atoms, 1):
            if (atom.idx in ligand_atoms) != (role == "ligand"):
                membership = "outside" if role == "protein" else "inside"
                raise ValueError(
                    f"{role}_anchor_{index} must be {membership} ligand_mask {ligand_mask}"
                )
    distance_force = positive_float(restraints, "distance_force")
    angular_force = positive_float(restraints, "angle_force")
    torsion_force = positive_float(restraints, "torsion_force")
    xyz = lambda atom: list(topology.coordinates[atom.idx])
    records: list[RestraintRecord] = [
        ("distance", [p1, l1], distance(xyz(p1), xyz(l1)), distance_force),
        ("angle_a", [p2, p1, l1], angle(xyz(p2), xyz(p1), xyz(l1)), angular_force),
        ("angle_b", [p1, l1, l2], angle(xyz(p1), xyz(l1), xyz(l2)), angular_force),
        ("dihedral_a", [p3, p2, p1, l1], dihedral(xyz(p3), xyz(p2), xyz(p1), xyz(l1)), torsion_force),
        ("dihedral_b", [p2, p1, l1, l2], dihedral(xyz(p2), xyz(p1), xyz(l1), xyz(l2)), torsion_force),
        ("dihedral_c", [p1, l1, l2, l3], dihedral(xyz(p1), xyz(l1), xyz(l2), xyz(l3)), torsion_force),
    ]
    for kind, atoms, reference, _ in records:
        if not kind.startswith("angle_"):
            continue
        if not BORESCH_ANGLE_MIN_DEGREES <= reference <= BORESCH_ANGLE_MAX_DEGREES:
            indices = ",".join(str(atom.idx + 1) for atom in atoms)
            raise ValueError(
                f"Boresch {kind} is {reference:.1f} deg (atoms {indices}), outside "
                f"{BORESCH_ANGLE_MIN_DEGREES:.0f}-{BORESCH_ANGLE_MAX_DEGREES:.0f} deg. "
                "Near-collinear anchors make the restraint unstable and the "
                "standard-state correction diverge; choose other protein or ligand anchors."
            )
    # Dihedrals A and C also need non-collinear anchor triplets on each side.
    frame_angles = (
        ("protein anchor angle P3-P2-P1", [p3, p2, p1]),
        ("ligand anchor angle L1-L2-L3", [l1, l2, l3]),
    )
    for name, atoms in frame_angles:
        value = angle(*(xyz(atom) for atom in atoms))
        if not BORESCH_ANGLE_MIN_DEGREES <= value <= BORESCH_ANGLE_MAX_DEGREES:
            indices = ",".join(str(atom.idx + 1) for atom in atoms)
            raise ValueError(
                f"{name} is {value:.1f} deg (atoms {indices}), outside "
                f"{BORESCH_ANGLE_MIN_DEGREES:.0f}-{BORESCH_ANGLE_MAX_DEGREES:.0f} deg. "
                "Near-collinear anchor triplets leave the Boresch dihedrals ill-defined; "
                "choose other anchors."
            )
    return records


def restraint_bounds(kind: str, reference: float) -> tuple[float, float]:
    """Return AMBER r1/r4; the potential is harmonic between them and linear outside."""
    width = 2.0 if kind == "distance" else 180.0
    return reference - width, reference + width


def write_restraints(
    path: Path,
    records: list[RestraintRecord],
    scale: float,
) -> None:
    lines: list[str] = []
    for kind, atoms, reference, force in records:
        indices = ",".join(str(atom.idx + 1) for atom in atoms)
        lower, upper = restraint_bounds(kind, reference)
        lines.append(
            f"&rst iat={indices}, r1={lower:.6f}, r2={reference:.6f}, "
            f"r3={reference:.6f}, r4={upper:.6f}, "
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


def residue_mask(residues: list[object]) -> str:
    return ":" + ",".join(str(residue.idx + 1) for residue in residues)


def check_charge_topology(
    work_dir: Path,
    environment: str,
    ligand_mask: str,
    records: list[RestraintRecord],
) -> tuple[str, str]:
    """Check the two-copy charge topology and return the two copy masks.

    LEaP appends the second ligand copy after the whole solute, so every solute
    atom, including the restraint anchors, keeps its index from the single-copy
    build. The copy is the block where the two residue sequences first differ.
    """
    from parmed.amber.mask import AmberMask

    build_dir = work_dir / "build"
    single = parmed.load_file(str(build_dir / f"{environment}.parm7"))
    double = parmed.load_file(
        str(build_dir / f"{environment}_charge.parm7"),
        xyz=str(build_dir / f"{environment}_charge.rst7"),
    )
    selection = AmberMask(single, ligand_mask).Selection()
    first_copy = sorted(
        {single.atoms[index].residue.idx for index, value in enumerate(selection) if value}
    )
    if not first_copy:
        raise ValueError(f"Ligand mask selects no atoms in {environment}.parm7: {ligand_mask}")

    copy_start = next(
        (
            index
            for index, (left, right) in enumerate(zip(single.residues, double.residues))
            if left.name != right.name or len(left.atoms) != len(right.atoms)
        ),
        len(single.residues),
    )
    if copy_start <= first_copy[-1]:
        raise ValueError(f"The solute before the ligand copy changed in {environment}_charge.parm7")
    first_residues = [double.residues[index] for index in first_copy]
    second_residues = list(double.residues[copy_start:copy_start + len(first_copy)])
    first_atoms = [atom for residue in first_residues for atom in residue.atoms]
    second_atoms = [atom for residue in second_residues for atom in residue.atoms]
    if len(first_atoms) != len(second_atoms):
        raise ValueError(f"The two ligand copies differ in size in {environment}_charge.parm7")
    for first, second in zip(first_atoms, second_atoms):
        same_coordinates = all(
            abs(double.coordinates[first.idx][axis] - double.coordinates[second.idx][axis]) < 1.0e-3
            for axis in range(3)
        )
        if (first.name, first.residue.name, first.charge) != (
            second.name, second.residue.name, second.charge
        ) or not same_coordinates:
            raise ValueError(
                f"The two ligand copies differ in {environment}_charge.parm7 at atom {first.name}"
            )

    if environment == "complex":
        for kind, atoms, _, _ in records:
            for atom in atoms:
                copied = double.atoms[atom.idx]
                if (copied.name, copied.residue.name, copied.residue.idx) != (
                    atom.name, atom.residue.name, atom.residue.idx
                ):
                    raise ValueError(f"Restraint {kind} atom {atom.idx + 1} differs in complex_charge.parm7")
    return residue_mask(first_residues), residue_mask(second_residues)


def alchemical_options(
    stage: str,
    lambda_value: float,
    schedule: list[float],
    collect_mbar: bool,
    ligand_mask: str,
    mbar_interval: int,
    softcore: dict[str, float | int],
    charge_masks: tuple[str, str] | None = None,
) -> str:
    if stage == "restraint":
        # Ordinary MD with lambda-scaled DISANG force constants; anal.py
        # rebuilds the MBAR energies from the DUMPAVE restraint values.
        return ""
    common = f"icfe=1, clambda={lambda_value:.6f}, "
    if stage.endswith("vdw"):
        common += (
            f" timask1='{ligand_mask}', timask2='',"
            f" ifsc=1, scmask1='{ligand_mask}', scmask2='',{softcore_text(softcore)}"
            " aces26=1, gti_sc_cc_energy_terms='ele,vdw,ele14,vdw14',"
            " gti_sc_sc_energy_terms='', gti_nmropt=0,"
        )
    else:
        # Linear TI between two identical ligand copies (Amber manual 27.1.8.1):
        # V0 keeps the charged first copy, V1 the second copy uncharged by crgmask.
        first_copy, second_copy = charge_masks
        common += (
            f" timask1='{first_copy}', timask2='{second_copy}',"
            f" crgmask='{second_copy}', ifsc=0,"
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
    """Record the six Boresch restraints in DISANG order for anal.py."""
    lines = ["restraint\treference\tforce_constant\tr1\tr4\tatom_indices"]
    for kind, atoms, reference, force in records:
        atom_indices = ",".join(str(atom.idx + 1) for atom in atoms)
        lower, upper = restraint_bounds(kind, reference)
        lines.append(
            f"{kind}\t{reference:.8f}\t{force:.8f}\t{lower:.8f}\t{upper:.8f}\t{atom_indices}"
        )
    (work_dir / "restraints.tsv").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def print_restraint_references(work_dir: Path, records: list[RestraintRecord]) -> None:
    """Print the Boresch references so the anchors can be checked before running."""
    print("Boresch restraint references from build/complex.rst7:")
    for kind, atoms, reference, _ in records:
        unit = "A" if kind == "distance" else "deg"
        indices = ",".join(str(atom.idx + 1) for atom in atoms)
        print(f"  {kind:<10} {reference:9.3f} {unit:<3}  atoms {indices}")
    print(f"Restraint table: {work_dir / 'restraints.tsv'}")


def write_window(
    work_dir: Path,
    input_dir: Path,
    stage: str,
    environment: str,
    schedule: list[float],
    window_index: int,
    lambda_value: float,
    heating_seed: int,
    records: list[RestraintRecord],
    ligand_mask: str,
    common_replacements: dict[str, str],
    mbar_interval: int,
    softcore: dict[str, float | int],
    charge_masks: dict[str, tuple[str, str]],
) -> str:
    """Generate links, restraints, and AMBER inputs for one ABFE window."""
    window = f"{window_index:03d}"
    directory = window_directory(work_dir, stage, environment, window)
    directory.mkdir(parents=True, exist_ok=True)

    topology_name = f"{environment}.parm7"
    coordinate_name = f"{environment}.rst7"
    if stage.endswith("vdw"):
        topology_name = f"{environment}_uncharged.parm7"
    elif stage.endswith("charge"):
        topology_name = f"{environment}_charge.parm7"
        coordinate_name = f"{environment}_charge.rst7"
    relative_link(work_dir / "build" / topology_name, directory / "system.parm7")
    relative_link(work_dir / "build" / coordinate_name, directory / "system.rst7")

    # The restraint stage is fully restrained at lambda 0 and unrestrained at
    # lambda 1. Charge and vdW complex windows keep the full restraint.
    if environment == "solvent":
        restraint_scale = 0.0
    elif stage == "restraint":
        restraint_scale = 1.0 - lambda_value
    else:
        restraint_scale = 1.0
    write_restraints(directory / "disang.rest", records, restraint_scale)

    replacements = {
        **common_replacements,
        "@STAGE@": stage,
        "@LAMBDA@": f"{lambda_value:.6f}",
        "@RANDOM_SEED@": str(heating_seed),
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
            softcore=softcore,
            charge_masks=charge_masks.get(environment),
        )
        if stage == "restraint" and name == "production":
            # Restraint values are written at the MBAR sampling interval.
            replacements["@WT_END@"] = (
                f"&wt type='DUMPFREQ', istep1={mbar_interval}, /\n"
                "&wt type='END', /"
            )
            replacements["@DISANG@"] = f"DISANG=disang.rest\nDUMPAVE={RESTRAINT_DUMP_FILE}"
        render(
            input_dir / f"{name}.in.template",
            directory / f"{name}.in",
            replacements,
        )
    # A charge window holds two ligand copies. pmemd keeps their coordinates
    # identical only in a TI run, so minimization uses the same linear TI masks;
    # otherwise heating stops with "does not have match in V1".
    minimize_options = ""
    if stage.endswith("charge"):
        minimize_options = alchemical_options(
            stage,
            lambda_value,
            schedule,
            collect_mbar=False,
            ligand_mask=ligand_mask,
            mbar_interval=mbar_interval,
            softcore=softcore,
            charge_masks=charge_masks.get(environment),
        )
    replacements["@MINIMIZE_ALCHEMICAL_OPTIONS@"] = minimize_options
    render(input_dir / "minimize.in", directory / "minimize.in", replacements)

    return (
        f"{stage}\t{environment}\t{window}\t{lambda_value:.6f}\t"
        f"{heating_seed}\t{directory}"
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
        seed_base = heating_seed_base(run)
        softcore = softcore_settings(alchemical)
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
        records = restraint_records(topology, restraints, ligand_mask)
        prepare_alchemical_topologies(args.work_dir, ligand_mask)
        charge_masks = {
            environment: check_charge_topology(args.work_dir, environment, ligand_mask, records)
            for environment in ("complex", "solvent")
        }
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None
    write_restraint_metadata(args.work_dir, records)
    print_restraint_references(args.work_dir, records)

    states = ["stage\tenvironment\twindow\tlambda\tseed\tdirectory"]
    state_index = 0
    for stage, environment, schedule in stages:
        for window_index, lambda_value in enumerate(schedule):
            state_index += 1
            # Only heating starts new velocities; later stages restart with ig=-1.
            heating_seed = -1 if seed_base is None else seed_base + state_index
            states.append(
                write_window(
                    args.work_dir,
                    args.input_dir,
                    stage,
                    environment,
                    schedule,
                    window_index,
                    lambda_value,
                    heating_seed,
                    records,
                    ligand_mask,
                    common_replacements,
                    mbar_interval,
                    softcore,
                    charge_masks,
                )
            )
    (args.work_dir / "states.tsv").write_text("\n".join(states) + "\n", encoding="utf-8")
    (args.work_dir / "standard_state.tsv").write_text(
        f"temperature_K\tstandard_state_concentration_M\n{positive_float(run, 'temperature'):.6f}\t{standard_state:.6f}\n",
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
