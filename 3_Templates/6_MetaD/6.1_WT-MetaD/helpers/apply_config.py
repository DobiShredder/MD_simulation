#!/usr/bin/env python3
"""Apply config values to generated engine inputs without changing run commands."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from config_utils import (
    finite_float,
    choice_value,
    disulfide_pairs,
    disulfide_tleap_lines,
    load_config,
    plumed_options,
    run_settings,
    salt_settings,
    salt_tleap_lines,
    section,
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace generated engine-input values with config.toml settings."
    )
    parser.add_argument("config", type=Path, help="Template TOML configuration")
    parser.add_argument("work_dir", type=Path, help="Generated work directory")
    return parser.parse_args()


def replace_assignment(text: str, key: str, value: object) -> str:
    pattern = re.compile(rf"(?i)\b{re.escape(key)}\s*=\s*[^,\n/]+")
    return pattern.sub(f"{key}={value}", text)


def remove_assignment(text: str, key: str) -> str:
    pattern = re.compile(
        rf"(?im)^[ \t]*{re.escape(key)}\s*=\s*[^,\n/]+,?[ \t]*\n?"
    )
    text = pattern.sub("", text)
    inline = re.compile(rf"(?i)\b{re.escape(key)}\s*=\s*[^,\n/]+,?[ \t]*")
    return inline.sub("", text)


def add_cntrl_assignments(text: str, assignments: list[str]) -> str:
    marker = re.search(r"(?m)^/\s*$", text)
    if marker is None:
        return text
    indentation = "  "
    addition = "".join(f"{indentation}{assignment},\n" for assignment in assignments)
    return text[: marker.start()] + addition + text[marker.start() :]


def apply_amber_ensemble(
    text: str,
    ensemble: str,
    pressure: float,
    pressure_coupling: str,
) -> str:
    ntp = 2 if pressure_coupling == "anisotropic" else 1
    if ensemble == "NVT":
        text = replace_assignment(text, "ntb", 1)
        if re.search(r"(?i)\bntp\s*=", text):
            text = replace_assignment(text, "ntp", 0)
        else:
            text = add_cntrl_assignments(text, ["ntp=0"])
        for key in ("barostat", "pres0", "taup"):
            text = remove_assignment(text, key)
        return text

    text = replace_assignment(text, "ntb", 2)
    assignments: list[str] = []
    for key, value in (
        ("ntp", ntp),
        ("barostat", 2),
        ("pres0", f"{pressure:.3f}"),
        ("taup", "2.0"),
    ):
        if re.search(rf"(?i)\b{key}\s*=", text):
            text = replace_assignment(text, key, value)
        else:
            assignments.append(f"{key}={value}")
    return add_cntrl_assignments(text, assignments)


def stage_for_path(path: Path) -> str:
    name = path.name.lower()
    if "min" in name:
        return "minimization"
    if "heat" in name:
        return "heating"
    if "equil" in name:
        return "equilibration"
    if any(word in name for word in ("production", "gamd_prepare", "segment")):
        return "production"
    return "other"


# Engine passthrough: [amber.<stage>.<namelist>] and [gromacs.<stage>] tables
# write any engine keyword into the generated inputs. "all" applies to every
# stage and "md" to heating, equilibration and production (MD-only keywords
# such as gamma_ln break minimization); later tables win: all < md < stage.
# Keywords that the template derives
# from its own config keys or method logic are refused so restarts, windows
# and replicas stay consistent; the message names the config key to use.
MD_STAGES = ("heating", "equilibration", "production")
RUN_STAGES = ("minimization", *MD_STAGES)
PASSTHROUGH_STAGES = ("all", "md", *RUN_STAGES)

AMBER_MANAGED = {
    "imin": "the stage type (fixed by the template workflow)",
    "irest": "the stage restart chain (fixed by the template workflow)",
    "ntx": "the stage restart chain (fixed by the template workflow)",
    "ntmin": "the minimization method (fixed by the template workflow)",
    "nstlim": "[run] *_steps",
    "dt": "[run] timestep",
    "maxcyc": "[run] minimization_steps",
    "ncyc": "[run] minimization_steepest_steps",
    "ntpr": "[run] energy_interval_steps",
    "ntwr": "[run] restart_interval_steps",
    "ntwx": "[run] trajectory_interval_steps",
    "tempi": "[run] heating_initial_temperature",
    "temp0": "[run] temperature",
    "pres0": "[run] pressure",
    "ntb": "[run] equilibration_ensemble / production_ensemble",
    "ntp": "[run] *_ensemble and pressure_coupling",
    "ig": "[run] random_seed",
    "ntc": "[run] constraint_mode",
    "ntf": "[run] constraint_mode",
    "nmropt": "the template restraints (DISANG)",
    "ntr": "the template positional restraints",
    "restraintmask": "the template positional restraints",
    "restraint_wt": "the template positional restraints",
    "numexchg": "the replica-exchange settings",
    "gremd_acyc": "the replica-exchange settings",
    "plumed": "the PLUMED coupling ([plumed] tables)",
    "plumedfile": "the PLUMED coupling ([plumed] tables)",
    "icfe": "[alchemical]",
    "ifsc": "[alchemical]",
    "aces26": "[alchemical]",
    "timask1": "[alchemical] or [gamd] masks",
    "timask2": "[alchemical] masks",
    "scmask1": "[alchemical] masks",
    "scmask2": "[alchemical] masks",
    "crgmask": "[alchemical] masks",
    "clambda": "[alchemical] lambda windows",
    "ifmbar": "[alchemical] lambda windows",
    "mbar_states": "[alchemical] lambda windows",
    "mbar_lambda": "[alchemical] lambda windows",
    "bar_intervall": "[run] mbar_interval_steps",
    "scalpha": "[alchemical] scalpha",
    "scbeta": "[alchemical] scbeta",
    "gti_add_sc": "[alchemical]",
    "gti_ele_sc": "[alchemical] gti_ele_sc",
    "gti_vdw_sc": "[alchemical] gti_vdw_sc",
    "gti_lam_sch": "[alchemical] gti_lam_sch",
    "igamd": "[gamd]",
    "ie": "[gamd]",
    "irest_gamd": "[gamd]",
    "ntcmd": "[gamd] conventional_*_steps",
    "nteb": "[gamd] boost_*_steps",
    "ntcmdprep": "[gamd] conventional_preparation_steps",
    "ntebprep": "[gamd] boost_preparation_steps",
    "ntave": "[gamd] averaging_interval_steps",
    "sigma0p": "[gamd] sigma0P",
    "sigma0d": "[gamd] sigma0D",
    "sigma0b": "[gamd] sigma0B",
    "bgpro2atm": "[gamd] masks",
    "edpro2atm": "[gamd] masks",
    "ied": "[gamd]",
    "iep": "[gamd]",
}
# Sequential or per-window namelists written by the template.
AMBER_MANAGED_NAMELISTS = {"wt": "the template restraint schedule", "rst": "the DISANG restraint file"}

GROMACS_MANAGED = {
    "integrator": "the stage type (fixed by the template workflow)",
    "nsteps": "[run] *_steps",
    "dt": "[run] timestep",
    "tinit": "the segment restart chain (fixed by the template workflow)",
    "init-step": "the segment restart chain (fixed by the template workflow)",
    "continuation": "the segment restart chain (fixed by the template workflow)",
    "gen-vel": "the segment restart chain (fixed by the template workflow)",
    "gen-temp": "[run] temperature",
    "gen-seed": "[replica_exchange] random_seed",
    "ld-seed": "[replica_exchange] random_seed",
    "ref-t": "[run] temperature",
    "pcoupl": "[run] *_ensemble",
    "ref-p": "[run] pressure",
    "nstenergy": "[run] energy_interval_steps",
    "nstlog": "[run] energy_interval_steps",
    "nstxout-compressed": "[run] trajectory_interval_steps",
    "constraints": "[run] constraint_mode",
}

IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
MDP_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def check_passthrough_engines(config: dict[str, object]) -> None:
    """Refuse tables for an engine this template does not run (they would be ignored)."""
    run = config.get("run", {})
    gromacs_template = isinstance(run, dict) and "production_engine" in run  # REST2/REST3
    if "gromacs" in config and not gromacs_template:
        raise ValueError("[gromacs] tables apply only to the GROMACS REST templates; use [amber]")
    if "amber" in config and gromacs_template:
        raise ValueError("REST runs every stage with GROMACS; use [gromacs] instead of [amber]")
    plumed_bias = ("metadynamics", "opes", "opes_expanded", "ratchet_md")
    if "plumed" in config and not any(name in config for name in plumed_bias):
        raise ValueError("[plumed] applies only to templates with a PLUMED bias (MetaD/OPES, US ratchet MD)")


def passthrough_stage(path: Path) -> str | None:
    """Stage of a generated input for passthrough; None leaves the file unchanged."""
    stage = stage_for_path(path)
    if stage == "other" and path.name.startswith(("ratchet.", "continue.")):
        # US ratchet MD and window continuation segments are production MD.
        return "production"
    # Other files (for example the REST scale-one energy_check.mdp) keep the
    # template settings so their checks stay meaningful.
    return None if stage == "other" else stage


def table_order(stage: str) -> tuple[str, ...]:
    return ("all", "md", stage) if stage in MD_STAGES else ("all", stage)


def passthrough_tables(config: dict[str, object], engine: str) -> dict[str, dict]:
    tables = config.get(engine, {})
    if not isinstance(tables, dict):
        raise ValueError(f"[{engine}] must contain stage tables")
    for stage, value in tables.items():
        if stage not in PASSTHROUGH_STAGES:
            raise ValueError(
                f"[{engine}.{stage}]: unknown stage; use one of {', '.join(PASSTHROUGH_STAGES)}"
            )
        if not isinstance(value, dict):
            raise ValueError(f"[{engine}.{stage}] must be a table")
    return tables


def amber_value(location: str, value: object) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{location}: AMBER flags are integers; write 0 or 1")
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if "'" in value:
            raise ValueError(f"{location}: string values must not contain single quotes")
        return f"'{value}'"
    if isinstance(value, list) and value and all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
    ):
        return ",".join(str(item) for item in value)
    raise ValueError(f"{location}: use a number, a string or a list of numbers")


def amber_assignments(config: dict[str, object], stage: str) -> dict[str, dict[str, str]]:
    """Merge [amber.all|md|<stage>.*] into {namelist: {key: value}}."""
    tables = passthrough_tables(config, "amber")
    run = config.get("run", {})
    # Templates that expose these as config keys manage them; others allow overrides.
    managed = dict(AMBER_MANAGED)
    for keyword, run_key in (("cut", "cutoff"), ("fswitch", "lj_force_switch")):
        if isinstance(run, dict) and run_key in run:
            managed[keyword] = f"[run] {run_key}"
    merged: dict[str, dict[str, str]] = {}
    for table_stage in table_order(stage):
        for namelist, values in tables.get(table_stage, {}).items():
            location = f"[amber.{table_stage}.{namelist}]"
            if not isinstance(values, dict):
                raise ValueError(f"{location} must be a table of keywords")
            if not IDENTIFIER.match(namelist):
                raise ValueError(f"{location}: invalid namelist name")
            if namelist.lower() in AMBER_MANAGED_NAMELISTS:
                raise ValueError(
                    f"{location}: &{namelist} is written by {AMBER_MANAGED_NAMELISTS[namelist.lower()]}"
                )
            for key, value in values.items():
                if not IDENTIFIER.match(key):
                    raise ValueError(f"{location}: invalid keyword {key!r}")
                if key.lower() in managed:
                    raise ValueError(
                        f"{location} {key}: set by the template; use {managed[key.lower()]}"
                    )
                merged.setdefault(namelist.lower(), {})[key] = amber_value(f"{location} {key}", value)
    return merged


def namelist_span(text: str, namelist: str) -> tuple[int, int] | None:
    """Return (body start, terminator start) of the first &namelist block."""
    header = re.search(rf"(?im)^[ \t]*&{re.escape(namelist)}\b", text)
    if header is None:
        return None
    terminator = re.compile(r"(?im)^[ \t]*/[ \t]*$|&end\b|/[ \t]*$").search(text, header.end())
    if terminator is None:
        raise ValueError(f"&{namelist} has no terminator")
    return header.end(), terminator.start()


def set_namelist_values(text: str, namelist: str, values: dict[str, str]) -> str:
    span = namelist_span(text, namelist)
    if span is None:
        cntrl = namelist_span(text, "cntrl")
        if cntrl is None:
            return text
        # A new namelist goes right after &cntrl, before any &wt/DISANG lines.
        line_end = text.find("\n", cntrl[1])
        insert_at = len(text) if line_end < 0 else line_end + 1
        text = text[:insert_at] + f"&{namelist}\n/\n" + text[insert_at:]
        span = namelist_span(text, namelist)
    start, end = span
    body = text[start:end]
    additions = []
    for key, value in values.items():
        pattern = re.compile(
            rf"(?i)(?<![A-Za-z0-9_]){re.escape(key)}\s*=\s*('[^']*'|\"[^\"]*\"|[^,\n/]+)"
        )
        if pattern.search(body):
            body = pattern.sub(lambda _match: f"{key}={value}", body, count=1)
        else:
            additions.append(f"  {key}={value},\n")
    if additions:
        body = body.rstrip(" \t")
        if body.strip() and not body.rstrip().endswith(","):
            body = body.rstrip() + ","
        if not body.endswith("\n"):
            body += "\n"
        body += "".join(additions)
    return text[:start] + body + text[end:]


def apply_amber_passthrough(text: str, assignments: dict[str, dict[str, str]]) -> str:
    for namelist, values in assignments.items():
        text = set_namelist_values(text, namelist, values)
    return text


def mdp_key(key: str) -> str:
    return key.lower().replace("_", "-")


def gromacs_value(location: str, value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float, str)):
        return str(value)
    if isinstance(value, list) and value and all(
        isinstance(item, (int, float, str)) and not isinstance(item, bool) for item in value
    ):
        return " ".join(str(item) for item in value)
    raise ValueError(f"{location}: use a number, a string, a boolean or a list")


def gromacs_assignments(config: dict[str, object], stage: str) -> dict[str, str]:
    tables = passthrough_tables(config, "gromacs")
    merged: dict[str, str] = {}
    for table_stage in table_order(stage):
        location = f"[gromacs.{table_stage}]"
        for key, value in tables.get(table_stage, {}).items():
            if not MDP_KEY.match(key):
                raise ValueError(f"{location}: invalid mdp option {key!r}")
            if mdp_key(key) in GROMACS_MANAGED:
                raise ValueError(
                    f"{location} {key}: set by the template; use {GROMACS_MANAGED[mdp_key(key)]}"
                )
            merged[key] = gromacs_value(f"{location} {key}", value)
    return merged


def apply_gromacs_passthrough(text: str, assignments: dict[str, str]) -> str:
    for key, value in assignments.items():
        pattern = re.compile(r"(?m)^[ \t]*([A-Za-z][A-Za-z0-9_-]*)[ \t]*=.*$")
        replaced = False

        def replace(match: re.Match[str]) -> str:
            nonlocal replaced
            if mdp_key(match.group(1)) != mdp_key(key):
                return match.group(0)
            replaced = True
            return f"{match.group(1)} = {value}"

        text = pattern.sub(replace, text)
        if not replaced:
            text = text.rstrip("\n") + f"\n{key} = {value}\n"
    return text


def apply_amber_input(
    path: Path,
    runtime: dict[str, object],
    pressure: float,
    pressure_coupling: str,
    cation: str,
    anion: str,
    generated_minimization_max: int,
    config: dict[str, object] | None = None,
) -> None:
    text = path.read_text(encoding="utf-8")
    original = text
    stage = stage_for_path(path)
    if stage == "minimization":
        match = re.search(r"(?i)\bmaxcyc\s*=\s*([0-9]+)", text)
        generated_steps = int(match.group(1)) if match else generated_minimization_max
        scale = generated_steps / generated_minimization_max
        minimization_steps = max(1, round(int(runtime["minimization_steps"]) * scale))
        steepest_steps = round(
            int(runtime["minimization_steepest_steps"]) * scale
        )
        text = replace_assignment(text, "maxcyc", minimization_steps)
        if re.search(r"(?i)\bncyc\s*=", text):
            text = replace_assignment(text, "ncyc", steepest_steps)
    if stage == "heating":
        initial = f"{float(runtime['heating_initial_temperature']):.3f}"
        text = replace_assignment(text, "tempi", initial)
        text = replace_assignment(text, "value1", initial)
    if stage != "minimization":
        text = replace_assignment(text, "ntpr", runtime["energy_interval"])
        text = replace_assignment(text, "ntwr", runtime["restart_interval"])
    if stage == "equilibration":
        text = apply_amber_ensemble(
            text,
            str(runtime["equilibration_ensemble"]),
            pressure,
            pressure_coupling,
        )
    elif stage == "production":
        text = apply_amber_ensemble(
            text,
            str(runtime["production_ensemble"]),
            pressure,
            pressure_coupling,
        )
    text = text.replace("Na+,Cl-", f"{cation},{anion}")
    text = text.replace("K+,Cl-", f"{cation},{anion}")
    passthrough = passthrough_stage(path)
    if config is not None and passthrough is not None:
        text = apply_amber_passthrough(text, amber_assignments(config, passthrough))
    if text != original:
        path.write_text(text, encoding="utf-8")


def mdp_assignment(text: str, key: str, value: object) -> str:
    pattern = re.compile(rf"(?im)^({re.escape(key)}\s*=\s*).*$")
    if pattern.search(text):
        return pattern.sub(rf"\g<1>{value}", text)
    return text + f"{key} = {value}\n"


def apply_gromacs_input(
    path: Path,
    runtime: dict[str, object],
    config: dict[str, object] | None = None,
) -> None:
    text = path.read_text(encoding="utf-8")
    original = text
    stage = stage_for_path(path)
    if stage == "minimization":
        text = mdp_assignment(text, "nsteps", runtime["minimization_steps"])
    text = mdp_assignment(text, "nstenergy", runtime["energy_interval"])
    text = mdp_assignment(text, "nstlog", runtime["energy_interval"])
    if stage in {"equilibration", "production"}:
        ensemble = str(
            runtime[
                "equilibration_ensemble"
                if stage == "equilibration"
                else "production_ensemble"
            ]
        )
        text = mdp_assignment(text, "pcoupl", "no" if ensemble == "NVT" else "C-rescale")
    passthrough = passthrough_stage(path)
    if config is not None and passthrough is not None:
        text = apply_gromacs_passthrough(text, gromacs_assignments(config, passthrough))
    if text != original:
        path.write_text(text, encoding="utf-8")


def find_structure(work_dir: Path, tleap_path: Path) -> Path | None:
    candidates = [
        work_dir / "input.pdb",
        work_dir / "build/input.pdb",
        tleap_path.parent.parent / "input.pdb",
        work_dir / "system-coordinates.pdb",
    ]
    return next((path for path in candidates if path.is_file()), None)


def existing_formula_units(lines: list[str]) -> int:
    counts: list[int] = []
    for line in lines:
        if not line.lstrip().lower().startswith("addionsrand "):
            continue
        counts.extend(int(value) for value in re.findall(r"(?<![A-Za-z+])([1-9][0-9]*)\b", line))
    return min(counts) if counts else 0


def validate_divalent_neutralization(
    work_dir: Path,
    salt: dict[str, object],
) -> None:
    if int(salt["cation_charge"]) == 1:
        return
    log_paths = list(work_dir.rglob("*solvate.log"))
    final_log = work_dir / "leap.log"
    if final_log.is_file():
        log_paths.append(final_log)
    for log_path in log_paths:
        matches = re.findall(
            r"Total unperturbed charge:\s*([-+0-9.eE]+)",
            log_path.read_text(encoding="utf-8", errors="replace"),
        )
        if not matches:
            continue
        charge = float(matches[-1])
        rounded_charge = round(charge)
        if abs(charge - rounded_charge) > 1.0e-4:
            raise ValueError(
                f"non-integer pre-ion charge in {log_path}: {charge:.6f}"
            )
        if rounded_charge < 0 and abs(rounded_charge) % int(salt["cation_charge"]):
            raise ValueError(
                f"{salt['salt_type']} cannot exactly neutralize charge {rounded_charge} "
                f"with {salt['cation']}; choose a monovalent salt"
            )


def apply_tleap_input(
    path: Path,
    work_dir: Path,
    build: dict[str, object],
    salt: dict[str, object],
) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    formula_units = existing_formula_units(lines)
    box_shape = choice_value(build, "box_shape", {"rectangular", "octahedral"})
    has_solvation_command = any(
        line.lstrip().startswith(("solvatebox ", "solvateoct ")) for line in lines
    )
    if box_shape == "octahedral" and not has_solvation_command:
        raise ValueError("box_shape=octahedral is not supported by this template")
    if box_shape == "octahedral":
        lines = [
            re.sub(r"^(\s*)solvatebox\b", r"\1solvateoct", line)
            for line in lines
        ]
    else:
        lines = [
            re.sub(r"^(\s*)solvateoct\b", r"\1solvatebox", line)
            for line in lines
        ]

    has_ions = any(line.lstrip().lower().startswith("addionsrand ") for line in lines)
    lines = [
        line
        for line in lines
        if not line.lstrip().lower().startswith("addionsrand ")
        and not line.lstrip().startswith("bond system.")
        and line.strip() != "charge system"
    ]
    if not has_ions and ".solvate." in path.name:
        insertion = next(
            (
                index
                for index, line in enumerate(lines)
                if line.lstrip().startswith("savepdb system")
            ),
            len(lines),
        )
        lines[insertion:insertion] = ["charge system"]

    structure = find_structure(work_dir, path)
    bonds: list[str] = []
    if disulfide_pairs(build) and ".solvent." not in path.name:
        if structure is None:
            raise ValueError(f"PDB file for disulfide mapping not found below {work_dir}")
        bonds = disulfide_tleap_lines(build, structure)
    if bonds:
        insertion = next(
            (index for index, line in enumerate(lines) if line.lstrip().startswith(("check system", "solvate"))),
            len(lines),
        )
        lines[insertion:insertion] = bonds

    if has_ions:
        solvation_indices = [
            index
            for index, line in enumerate(lines)
            if line.lstrip().startswith(("solvatebox ", "solvateoct "))
        ]
        if solvation_indices:
            insertion = solvation_indices[-1] + 1
        else:
            insertion = next(
                (
                    index
                    for index, line in enumerate(lines)
                    if line.lstrip().startswith(("check system", "saveamberparm"))
                ),
                len(lines),
            )
        lines[insertion:insertion] = [
            "charge system",
            *salt_tleap_lines(salt, formula_units),
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def toml_value(value: object) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return json.dumps(value)
    return str(value)


def synchronize_resolved_section(
    text: str,
    section_name: str,
    assignments: dict[str, object],
    legacy_keys: tuple[str, ...] = (),
) -> str:
    header = re.search(rf"(?m)^\[{re.escape(section_name)}\]\s*$", text)
    if header is None:
        return text
    next_header = re.search(r"(?m)^\[", text[header.end() :])
    end = len(text) if next_header is None else header.end() + next_header.start()
    section_text = text[header.end() : end]
    for key in legacy_keys:
        section_text = re.sub(
            rf"(?m)^{re.escape(key)}\s*=.*\n?", "", section_text
        )
    for key, value in assignments.items():
        line = f"{key} = {toml_value(value)}"
        pattern = re.compile(rf"(?m)^{re.escape(key)}\s*=.*$")
        if pattern.search(section_text):
            section_text = pattern.sub(line, section_text)
        else:
            section_text = section_text.rstrip() + f"\n{line}\n\n"
    return text[: header.end()] + section_text + text[end:]


def synchronize_resolved_config(
    config: dict[str, object],
    work_dir: Path,
    runtime: dict[str, object],
) -> None:
    path = work_dir / "resolved_config.toml"
    if not path.is_file():
        return
    build = section(config, "build")
    text = path.read_text(encoding="utf-8")
    text = synchronize_resolved_section(
        text,
        "build",
        {
            "box_shape": build["box_shape"],
            "disulfide_bonds": build["disulfide_bonds"],
            "salt_type": build["salt_type"],
            "salt_concentration": build["salt_concentration"],
        },
        ("salt_concentration_molar",),
    )
    text = synchronize_resolved_section(
        text,
        "run",
        {
            "minimization_steps": runtime["minimization_steps"],
            "minimization_steepest_steps": runtime[
                "minimization_steepest_steps"
            ],
            "heating_initial_temperature": runtime[
                "heating_initial_temperature"
            ],
            "energy_interval_steps": runtime["energy_interval"],
            "restart_interval_steps": runtime["restart_interval"],
            "equilibration_ensemble": runtime["equilibration_ensemble"],
            "production_ensemble": runtime["production_ensemble"],
        },
        ("ensemble",),
    )
    path.write_text(text, encoding="utf-8")


def _apply_config(config_path: Path, work_dir: Path) -> None:
    config = load_config(config_path)
    build = section(config, "build")
    run = section(config, "run")
    runtime = run_settings(run)
    salt = salt_settings(build)
    box_shape = choice_value(build, "box_shape", {"rectangular", "octahedral"})
    if "funnel" in config and box_shape != "rectangular":
        raise ValueError("Funnel-MetaD requires box_shape=rectangular")
    if "membrane" in config and box_shape != "rectangular":
        raise ValueError("membrane-protein templates require box_shape=rectangular")
    pressure = finite_float(run, "pressure", default=1.0)
    pressure_coupling = "isotropic"
    if "pressure_coupling" in run:
        pressure_coupling = choice_value(
            run, "pressure_coupling", {"isotropic", "anisotropic"}
        )
    # Templates constrain bonds to hydrogen (SHAKE) but do not repartition
    # hydrogen masses, so AMBER dt above 2 fs is not supported here.
    timestep_fs = finite_float(run, "timestep", default=2.0)
    if timestep_fs > 2.0:
        raise ValueError(
            f"timestep must be 2.0 fs or less without hydrogen mass repartitioning: {timestep_fs:g}"
        )
    validate_divalent_neutralization(work_dir, salt)
    # Check passthrough tables up front so a typo fails even when no file uses it.
    check_passthrough_engines(config)
    for stage in RUN_STAGES:
        amber_assignments(config, stage)
        gromacs_assignments(config, stage)
    plumed_options(config)

    generated_minimization_steps: list[int] = []
    for path in work_dir.rglob("*"):
        if not path.is_file() or not path.name.endswith((".in", ".in.template")):
            continue
        if stage_for_path(path) != "minimization":
            continue
        match = re.search(
            r"(?i)\bmaxcyc\s*=\s*([0-9]+)",
            path.read_text(encoding="utf-8"),
        )
        if match:
            generated_minimization_steps.append(int(match.group(1)))
    generated_minimization_max = max(generated_minimization_steps, default=1)

    for path in work_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name.startswith("tleap") and path.suffix == ".in":
            apply_tleap_input(path, work_dir, build, salt)
        elif path.suffix == ".mdp":
            apply_gromacs_input(path, runtime, config)
        elif path.name.endswith((".in", ".in.template")):
            apply_amber_input(
                path,
                runtime,
                pressure,
                pressure_coupling,
                str(salt["cation"]),
                str(salt["anion"]),
                generated_minimization_max,
                config,
            )
    synchronize_resolved_config(config, work_dir, runtime)


def apply_engine_passthrough(config_path: Path, directory: Path) -> None:
    """Apply only the [amber]/[gromacs] passthrough tables to inputs in directory.

    For generators that write stage inputs outside the build-time apply_config
    pass (for example the US seed and window inputs).
    """
    try:
        config = load_config(config_path)
        for path in sorted(directory.rglob("*")):
            is_mdp = path.suffix == ".mdp"
            is_amber = path.name.endswith((".in", ".in.template")) and not path.name.startswith("tleap")
            if not path.is_file() or not (is_mdp or is_amber):
                continue
            stage = passthrough_stage(path)
            if stage is None:
                continue
            text = path.read_text(encoding="utf-8")
            if is_mdp:
                updated = apply_gromacs_passthrough(text, gromacs_assignments(config, stage))
            else:
                updated = apply_amber_passthrough(text, amber_assignments(config, stage))
            if updated != text:
                path.write_text(updated, encoding="utf-8")
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None


def apply_config(config_path: Path, work_dir: Path) -> None:
    try:
        _apply_config(config_path, work_dir)
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None


def main() -> None:
    args = arguments()
    apply_config(args.config, args.work_dir)


if __name__ == "__main__":
    main()
