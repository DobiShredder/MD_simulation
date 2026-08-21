#!/usr/bin/env python3
"""Small TOML helpers shared by the simulation templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        raise SystemExit(
            "Python 3.11 or newer is required, or install the Python 3.10 "
            "fallback with: python3 -m pip install tomli"
        ) from None


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Config file not found: {path}")
    try:
        with path.open("rb") as handle:
            config = tomllib.load(handle)
            build = config.get("build")
            if isinstance(build, dict) and "salt_concentration" in build:
                concentration = build["salt_concentration"]
                if (
                    isinstance(concentration, bool)
                    or not isinstance(concentration, (int, float))
                    or concentration < 0
                ):
                    raise ValueError("salt_concentration must be zero or greater")
                # Compatibility alias for existing generators. Public config uses mM.
                build["salt_concentration_molar"] = float(concentration) / 1000.0
            if isinstance(build, dict) and build.get("salt_type") in SALT_TYPES:
                cation, anion, _, _ = SALT_TYPES[str(build["salt_type"])]
                for section_value in config.values():
                    if not isinstance(section_value, dict):
                        continue
                    for key, value in section_value.items():
                        if key.endswith("_mask") and isinstance(value, str):
                            value = value.replace("Na+,Cl-", f"{cation},{anion}")
                            value = value.replace("K+,Cl-", f"{cation},{anion}")
                            section_value[key] = value
            run = config.get("run")
            if isinstance(run, dict) and "equilibration_ensemble" in run:
                # Compatibility alias while existing generators are converted to
                # stage-specific ensemble fields.
                run["ensemble"] = run["equilibration_ensemble"]
            return config
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"Invalid TOML in {path}: {error}") from error


def section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"Missing config section: [{name}]")
    return value


def string_value(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def positive_float(values: dict[str, Any], key: str) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{key} must be greater than zero")
    return float(value)


def positive_int(values: dict[str, Any], key: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def nonnegative_float(values: dict[str, Any], key: str) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{key} must be zero or greater")
    return float(value)


def nonnegative_int(values: dict[str, Any], key: str) -> int:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be zero or a positive integer")
    return value


def boolean_value(values: dict[str, Any], key: str) -> bool:
    value = values.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be true or false")
    return value


def choice_value(values: dict[str, Any], key: str, choices: set[str]) -> str:
    value = string_value(values, key)
    normalized = value.upper()
    allowed = {choice.upper(): choice for choice in choices}
    if normalized not in allowed:
        options = ", ".join(sorted(choices))
        raise ValueError(f"{key} must be one of: {options}")
    return allowed[normalized]


SALT_TYPES = {
    "NaCl": ("Na+", "Cl-", 1, 1),
    "KCl": ("K+", "Cl-", 1, 1),
    "MgCl2": ("MG", "Cl-", 1, 2),
    "CaCl2": ("CA", "Cl-", 1, 2),
}


def salt_settings(values: dict[str, Any]) -> dict[str, object]:
    salt_type = choice_value(values, "salt_type", set(SALT_TYPES))
    cation, anion, cation_count, anion_count = SALT_TYPES[salt_type]
    return {
        "salt_type": salt_type,
        "salt_concentration": nonnegative_float(values, "salt_concentration"),
        "cation": cation,
        "anion": anion,
        "cation_count": cation_count,
        "anion_count": anion_count,
        "cation_charge": 2 if salt_type in {"MgCl2", "CaCl2"} else 1,
    }


def salt_tleap_lines(
    settings: dict[str, object], formula_units: int
) -> list[str]:
    if formula_units < 0:
        raise ValueError("salt formula-unit count must be zero or greater")
    cation = settings["cation"]
    anion = settings["anion"]
    cation_count = formula_units * int(settings["cation_count"])
    anion_count = formula_units * int(settings["anion_count"])
    return [
        f"addionsrand system {cation} 0",
        f"addionsrand system {anion} 0",
        f"addionsrand system {cation} {cation_count}",
        f"addionsrand system {anion} {anion_count}",
    ]


def disulfide_pairs(values: dict[str, Any]) -> list[tuple[str, str]]:
    raw = values.get("disulfide_bonds")
    if not isinstance(raw, list):
        raise ValueError("disulfide_bonds must be an array")
    pairs: list[tuple[str, str]] = []
    for index, pair in enumerate(raw, 1):
        if (
            not isinstance(pair, (list, tuple))
            or len(pair) != 2
            or not all(isinstance(item, str) and item.strip() for item in pair)
        ):
            raise ValueError(
                f"disulfide_bonds entry {index} must contain two chain:residue strings"
            )
        pairs.append((pair[0].strip(), pair[1].strip()))
    return pairs


def disulfide_tleap_lines(
    values: dict[str, Any], pdb_path: Path, unit: str = "system"
) -> list[str]:
    pairs = disulfide_pairs(values)
    if not pairs:
        return []
    if not pdb_path.is_file():
        raise ValueError(f"PDB file for disulfide mapping not found: {pdb_path}")

    residues: list[tuple[str, str, str, set[str]]] = []
    current_key: tuple[str, str, str] | None = None
    for line in pdb_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(("ATOM  ", "HETATM")):
            continue
        chain = line[21:22].strip() or "_"
        residue_number = line[22:26].strip()
        insertion_code = line[26:27].strip()
        key = (chain, residue_number, insertion_code)
        atom_name = line[12:16].strip()
        if key != current_key:
            residues.append((chain, residue_number, insertion_code, {atom_name}))
            current_key = key
        else:
            residues[-1][3].add(atom_name)

    lookup: dict[str, list[tuple[int, set[str]]]] = {}
    for index, (chain, number, insertion, atoms) in enumerate(residues, 1):
        reference = f"{chain}:{number}{insertion}"
        lookup.setdefault(reference, []).append((index, atoms))

    lines: list[str] = []
    used: set[int] = set()
    for left, right in pairs:
        indices: list[int] = []
        for reference in (left, right):
            matches = lookup.get(reference, [])
            if len(matches) != 1:
                raise ValueError(
                    f"disulfide residue must match one PDB residue: {reference} matched {len(matches)}"
                )
            residue_index, atoms = matches[0]
            if "SG" not in atoms:
                raise ValueError(f"disulfide residue has no SG atom: {reference}")
            indices.append(residue_index)
        if indices[0] == indices[1] or any(index in used for index in indices):
            raise ValueError(f"disulfide residue is reused: {left}, {right}")
        used.update(indices)
        lines.append(f"bond {unit}.{indices[0]}.SG {unit}.{indices[1]}.SG")
    return lines


def run_settings(values: dict[str, Any]) -> dict[str, object]:
    minimization_steps = positive_int(values, "minimization_steps")
    steepest_steps = nonnegative_int(values, "minimization_steepest_steps")
    if steepest_steps > minimization_steps:
        raise ValueError(
            "minimization_steepest_steps cannot exceed minimization_steps"
        )
    initial_temperature = nonnegative_float(
        values, "heating_initial_temperature"
    )
    target_temperature = positive_float(values, "temperature")
    if initial_temperature > target_temperature:
        raise ValueError(
            "heating_initial_temperature cannot exceed temperature"
        )
    return {
        "minimization_steps": minimization_steps,
        "minimization_steepest_steps": steepest_steps,
        "heating_initial_temperature": initial_temperature,
        "energy_interval": positive_int(values, "energy_interval_steps"),
        "restart_interval": positive_int(values, "restart_interval_steps"),
        "equilibration_ensemble": choice_value(
            values, "equilibration_ensemble", {"NVT", "NPT"}
        ),
        "production_ensemble": choice_value(
            values, "production_ensemble", {"NVT", "NPT"}
        ),
    }


def amber_ensemble_lines(
    ensemble: str,
    pressure: float,
    *,
    pressure_coupling: str = "isotropic",
    barostat: int = 2,
) -> list[str]:
    if ensemble == "NVT":
        return ["ntb=1", "ntp=0"]
    ntp = 2 if pressure_coupling == "anisotropic" else 1
    return [
        "ntb=2",
        f"ntp={ntp}",
        f"barostat={barostat}",
        f"pres0={pressure:.3f}",
        "taup=2.0",
    ]
