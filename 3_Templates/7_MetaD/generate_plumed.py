#!/usr/bin/env python3
"""Generate PLUMED 2.10 input for MetaD and OPES production segments."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, "../../common")
from config_utils import (  # noqa: E402
    load_config,
    positive_float,
    positive_int,
    section,
    string_value,
)


METHODS = ("wt-metad", "funnel-metad", "opes-metad", "opes-expanded")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render one PLUMED input with explicit bias-state filenames."
    )
    parser.add_argument("method", choices=METHODS, help="MetaD or OPES method")
    parser.add_argument("config", type=Path, help="Template TOML configuration")
    parser.add_argument("output", type=Path, help="PLUMED input to create")
    parser.add_argument(
        "--cv-file",
        type=Path,
        help="PLUMED collective-variable definitions for WT-MetaD or OPES_METAD",
    )
    parser.add_argument(
        "--funnel-context",
        type=Path,
        help="Generated funnel atom and axis context for Funnel-MetaD",
    )
    parser.add_argument(
        "--file-prefix",
        default="",
        help="Prefix for HILLS, state, and COLVAR paths (default: none)",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Read and append the bias state from a previous segment",
    )
    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="Use disposable output names for a PLUMED parse-only check",
    )
    return parser.parse_args()


def numeric_list(
    values: dict[str, object], key: str, expected: int | None = None
) -> list[float]:
    raw = values.get(key)
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{key} must be a non-empty numeric list")
    result: list[float] = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must contain only numbers")
        result.append(float(value))
    if expected is not None and len(result) != expected:
        raise ValueError(f"{key} must contain {expected} values")
    return result


def string_list(values: dict[str, object], key: str) -> list[str]:
    raw = values.get(key)
    if not isinstance(raw, list) or not raw or not all(isinstance(v, str) and v for v in raw):
        raise ValueError(f"{key} must be a non-empty string list")
    return list(raw)


def integer_list(values: dict[str, object], key: str, expected: int) -> list[int]:
    raw = values.get(key)
    if (
        not isinstance(raw, list)
        or len(raw) != expected
        or not all(isinstance(value, int) and not isinstance(value, bool) for value in raw)
    ):
        raise ValueError(f"{key} must contain {expected} integers")
    return list(raw)


def comma(values: list[float | int | str]) -> str:
    return ",".join(f"{value:g}" if isinstance(value, float) else str(value) for value in values)


def read_cv(path: Path | None) -> str:
    if path is None or not path.is_file():
        raise ValueError("--cv-file is required and must exist")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("collective-variable definition file is empty")
    return text


def state_path(args: argparse.Namespace, name: str) -> str:
    if args.parse_only:
        return f"plumed.parse.{name}"
    return f"{args.file_prefix}{name}"


def render_wt(args: argparse.Namespace, config: dict[str, object]) -> str:
    run = section(config, "run")
    cv = section(config, "collective_variable")
    metad = section(config, "metadynamics")
    arguments = string_list(cv, "arguments")
    sigma = numeric_list(metad, "sigma", len(arguments))
    grid_min = numeric_list(metad, "grid_min", len(arguments))
    grid_max = numeric_list(metad, "grid_max", len(arguments))
    grid_bins = integer_list(metad, "grid_bins", len(arguments))
    if any(value <= 0 for value in sigma) or any(value <= 0 for value in grid_bins):
        raise ValueError("sigma and grid_bins must be positive")
    if any(lower >= upper for lower, upper in zip(grid_min, grid_max)):
        raise ValueError("each grid_min value must be smaller than grid_max")
    if positive_float(metad, "bias_factor") <= 1.0:
        raise ValueError("bias_factor must be greater than one")
    return f"""{read_cv(args.cv_file)}

metad: METAD ...
  ARG={comma(arguments)}
  SIGMA={comma(sigma)}
  HEIGHT={positive_float(metad, 'height'):g}
  PACE={positive_int(metad, 'pace_steps')}
  BIASFACTOR={positive_float(metad, 'bias_factor'):g}
  TEMP={positive_float(run, 'temperature'):g}
  FILE={state_path(args, 'HILLS')}
  GRID_MIN={comma(grid_min)}
  GRID_MAX={comma(grid_max)}
  GRID_BIN={comma(grid_bins)}
  CALC_RCT
...

PRINT ARG={comma(arguments)},metad.bias,metad.rbias STRIDE={positive_int(run, 'trajectory_interval_steps')} FILE={state_path(args, 'COLVAR')}
"""


def render_opes_metad(args: argparse.Namespace, config: dict[str, object]) -> str:
    run = section(config, "run")
    cv = section(config, "collective_variable")
    opes = section(config, "opes")
    arguments = string_list(cv, "arguments")
    sigma = numeric_list(opes, "sigma", len(arguments))
    if any(value <= 0.0 for value in sigma):
        raise ValueError("sigma values must be positive")
    pace = positive_int(opes, "pace_steps")
    state_stride = positive_int(opes, "state_write_interval_steps")
    if state_stride % pace != 0:
        raise ValueError("state_write_interval_steps must be divisible by pace_steps")
    state_read = ""
    if args.restart and not args.parse_only:
        state_read = f"  STATE_RFILE={state_path(args, 'opes.state')}\n"
    return f"""{read_cv(args.cv_file)}

opes: OPES_METAD ...
  ARG={comma(arguments)}
  TEMP={positive_float(run, 'temperature'):g}
  PACE={pace}
  BARRIER={positive_float(opes, 'barrier'):g}
  SIGMA={comma(sigma)}
  FILE={state_path(args, 'KERNELS')}
{state_read}  STATE_WFILE={state_path(args, 'opes.state')}
  STATE_WSTRIDE={state_stride}
...

PRINT ARG={comma(arguments)},opes.bias,opes.rct,opes.neff,opes.nker STRIDE={positive_int(run, 'trajectory_interval_steps')} FILE={state_path(args, 'COLVAR')}
"""


def render_opes_expanded(args: argparse.Namespace, config: dict[str, object]) -> str:
    run = section(config, "run")
    opes = section(config, "opes_expanded")
    base_temperature = positive_float(run, "temperature")
    minimum = positive_float(opes, "minimum_temperature")
    maximum = positive_float(opes, "maximum_temperature")
    if not minimum <= base_temperature <= maximum or minimum >= maximum:
        raise ValueError("temperature range must contain the simulation temperature")
    pace = positive_int(opes, "pace_steps")
    state_stride = positive_int(opes, "state_write_interval_steps")
    if state_stride % pace != 0:
        raise ValueError("state_write_interval_steps must be divisible by pace_steps")
    state_read = ""
    if args.restart and not args.parse_only:
        state_read = f"  STATE_RFILE={state_path(args, 'opes.state')}\n"
    return f"""ene: ENERGY

ecv: ECV_MULTITHERMAL ...
  ARG=ene
  TEMP={base_temperature:g}
  TEMP_MIN={minimum:g}
  TEMP_MAX={maximum:g}
...

opes: OPES_EXPANDED ...
  ARG=ecv.ene
  PACE={pace}
  FILE={state_path(args, 'DELTAFS')}
{state_read}  STATE_WFILE={state_path(args, 'opes.state')}
  STATE_WSTRIDE={state_stride}
...

PRINT ARG=ene,ecv.ene,opes.bias STRIDE={positive_int(run, 'trajectory_interval_steps')} FILE={state_path(args, 'COLVAR')}
"""


def render_funnel(args: argparse.Namespace, config: dict[str, object]) -> str:
    if args.funnel_context is None or not args.funnel_context.is_file():
        raise ValueError("--funnel-context is required and must exist")
    context = load_config(args.funnel_context)
    groups = section(context, "groups")
    geometry = section(context, "geometry")
    run = section(config, "run")
    funnel = section(config, "funnel")
    metad = section(config, "metadynamics")
    zcc = positive_float(funnel, "zcc")
    minimum = float(funnel.get("minimum_projection"))
    maximum = positive_float(funnel, "maximum_projection")
    lower = float(funnel.get("lower_wall"))
    upper = positive_float(funnel, "upper_wall")
    if not minimum < lower < zcc < upper < maximum:
        raise ValueError("funnel projection limits must satisfy min < lower < zcc < upper < max")
    alpha = positive_float(funnel, "alpha")
    if alpha >= math.pi / 2.0:
        raise ValueError("alpha must be smaller than pi/2")
    if positive_float(metad, "bias_factor") <= 1.0:
        raise ValueError("bias_factor must be greater than one")
    reference_file = "funnel-reference.pdb"
    if not args.parse_only:
        reference_file = f"{args.file_prefix}{reference_file}"
    return f"""WHOLEMOLECULES ENTITY0={string_value(groups, 'protein_atoms')} ENTITY1={string_value(groups, 'ligand_atoms')}

ligand: COM ATOMS={string_value(groups, 'ligand_heavy_atoms')}

fps: FUNNEL_PS ...
  LIGAND=ligand
  REFERENCE={reference_file}
  ANCHOR={positive_int(geometry, 'anchor_atom')}
  POINTS={string_value(geometry, 'points_nm')}
...

funnel: FUNNEL ...
  ARG=fps.lp,fps.ld
  ZCC={zcc:g}
  ALPHA={alpha:g}
  RCYL={positive_float(funnel, 'cylinder_radius'):g}
  MINS={minimum:g}
  MAXS={maximum:g}
  KAPPA={positive_float(funnel, 'wall_force'):g}
  NBINS={positive_int(funnel, 'radial_grid_bins')}
  NBINZ={positive_int(funnel, 'axial_grid_bins')}
  FILE={state_path(args, 'FUNNEL_GRID')}
...

lower: LOWER_WALLS ARG=fps.lp AT={lower:g} KAPPA={positive_float(funnel, 'wall_force'):g} EXP=2
upper: UPPER_WALLS ARG=fps.lp AT={upper:g} KAPPA={positive_float(funnel, 'wall_force'):g} EXP=2

metad: METAD ...
  ARG=fps.lp
  SIGMA={positive_float(metad, 'sigma'):g}
  HEIGHT={positive_float(metad, 'height'):g}
  PACE={positive_int(metad, 'pace_steps')}
  BIASFACTOR={positive_float(metad, 'bias_factor'):g}
  TEMP={positive_float(run, 'temperature'):g}
  FILE={state_path(args, 'HILLS')}
  GRID_MIN={minimum:g}
  GRID_MAX={maximum:g}
  GRID_BIN={positive_int(metad, 'grid_bins')}
  CALC_RCT
...

PRINT ARG=fps.lp,fps.ld,funnel.bias,lower.bias,upper.bias,metad.bias,metad.rbias STRIDE={positive_int(run, 'trajectory_interval_steps')} FILE={state_path(args, 'COLVAR')}
"""


def main() -> None:
    args = parse_arguments()
    try:
        config = load_config(args.config)
        renderers = {
            "wt-metad": render_wt,
            "funnel-metad": render_funnel,
            "opes-metad": render_opes_metad,
            "opes-expanded": render_opes_expanded,
        }
        text = renderers[args.method](args, config)
    except (TypeError, ValueError) as error:
        raise SystemExit(f"Config error: {error}") from None
    restart = "RESTART\n\n" if args.restart and not args.parse_only else ""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(restart + text, encoding="utf-8")


if __name__ == "__main__":
    main()
