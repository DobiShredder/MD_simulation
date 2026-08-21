#!/usr/bin/env python3
"""Apply config values to generated engine inputs without changing run commands."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from config_utils import (
    choice_value,
    disulfide_pairs,
    disulfide_tleap_lines,
    load_config,
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


def apply_amber_input(
    path: Path,
    runtime: dict[str, object],
    pressure: float,
    pressure_coupling: str,
    cation: str,
    anion: str,
    generated_minimization_max: int,
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
            "heating_initial_temperature_kelvin": runtime[
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
    pressure = float(run.get("pressure_bar", 1.0))
    pressure_coupling = str(run.get("pressure_coupling", "isotropic")).lower()
    validate_divalent_neutralization(work_dir, salt)

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
            apply_gromacs_input(path, runtime)
        elif path.name.endswith((".in", ".in.template")):
            apply_amber_input(
                path,
                runtime,
                pressure,
                pressure_coupling,
                str(salt["cation"]),
                str(salt["anion"]),
                generated_minimization_max,
            )
    synchronize_resolved_config(config, work_dir, runtime)


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
