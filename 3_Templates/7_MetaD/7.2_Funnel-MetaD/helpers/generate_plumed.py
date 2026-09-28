#!/usr/bin/env python3
"""Generate PLUMED 2.10 input for Funnel-MetaD production segments."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from config_utils import (  # noqa: E402
    load_config,
    positive_float,
    positive_int,
    section,
    string_value,
)




def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render one PLUMED input with explicit bias-state filenames."
    )
    parser.add_argument("config", type=Path, help="Template TOML configuration")
    parser.add_argument("output", type=Path, help="PLUMED input to create")
    parser.add_argument(
        "--funnel-context",
        type=Path,
        required=True,
        help="Generated funnel atom and axis context",
    )
    parser.add_argument(
        "--file-prefix",
        default="",
        help="Prefix for bias state and COLVAR paths (default: none)",
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







def state_path(args: argparse.Namespace, name: str) -> str:
    if args.parse_only:
        return f"plumed.parse.{name}"
    return f"{args.file_prefix}{name}"





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
        text = render_funnel(args, config)
    except (TypeError, ValueError) as error:
        raise SystemExit(f"Config error: {error}") from None
    restart = "RESTART\n\n" if args.restart and not args.parse_only else ""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(restart + text, encoding="utf-8")


if __name__ == "__main__":
    main()
