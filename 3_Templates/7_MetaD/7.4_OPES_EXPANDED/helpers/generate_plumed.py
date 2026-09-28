#!/usr/bin/env python3
"""Generate PLUMED 2.10 input for OPES_EXPANDED production segments."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from config_utils import (  # noqa: E402
    load_config,
    positive_float,
    positive_int,
    section,
)




def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render one PLUMED input with explicit bias-state filenames."
    )
    parser.add_argument("config", type=Path, help="Template TOML configuration")
    parser.add_argument("output", type=Path, help="PLUMED input to create")
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



def main() -> None:
    args = parse_arguments()
    try:
        config = load_config(args.config)
        text = render_opes_expanded(args, config)
    except (TypeError, ValueError) as error:
        raise SystemExit(f"Config error: {error}") from None
    restart = "RESTART\n\n" if args.restart and not args.parse_only else ""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(restart + text, encoding="utf-8")


if __name__ == "__main__":
    main()
