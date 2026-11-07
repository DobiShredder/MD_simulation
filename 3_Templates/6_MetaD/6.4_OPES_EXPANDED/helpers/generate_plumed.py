#!/usr/bin/env python3
"""Generate PLUMED 2.10 input for OPES_EXPANDED production segments."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from config_utils import (  # noqa: E402
    apply_plumed_options,
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
    parser.add_argument(
        "--stage",
        default="PLUMED input generation",
        help="Workflow stage named in configuration errors",
    )
    return parser.parse_args()







def number(value: float) -> str:
    """Write a PLUMED number without losing precision (6-digit :g is too coarse)."""
    text = f"{value:g}"
    if float(text) != value:
        text = repr(float(value))
    return text


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
    # The next segment reads opes.state, so the last write must be the segment end.
    production_steps = positive_int(run, "production_steps")
    segments = positive_int(run, "production_segments")
    if production_steps % segments != 0:
        raise ValueError("production_steps must be divisible by production_segments")
    segment_steps = production_steps // segments
    if segment_steps % state_stride != 0:
        raise ValueError(
            f"production steps per segment ({segment_steps}) must be divisible by "
            f"state_write_interval_steps ({state_stride}) so that opes.state is "
            "written at the end of each segment"
        )
    state_read = ""
    if args.restart and not args.parse_only:
        state_read = f"  STATE_RFILE={state_path(args, 'opes.state')}\n"

    # Optional grid controls. When a key is absent the keyword is omitted and
    # PLUMED chooses the value (automatic TEMP_STEPS, OBSERVATION_STEPS=100).
    temperature_steps = ""
    if "temperature_steps" in opes:
        count = positive_int(opes, "temperature_steps")
        if count < 2:
            raise ValueError("temperature_steps must be at least 2 (TEMP_MIN and TEMP_MAX)")
        temperature_steps = f"  TEMP_STEPS={count}\n"
    observation_steps = ""
    if "observation_steps" in opes:
        count = positive_int(opes, "observation_steps")
        # OBSERVATION_STEPS counts PACE strides. opes.state is not written until
        # this unbiased observation ends, so it must end inside the first segment.
        if count * pace >= segment_steps:
            raise ValueError(
                f"observation_steps * pace_steps ({count * pace}) must be smaller than "
                f"the production steps per segment ({segment_steps})"
            )
        observation_steps = f"  OBSERVATION_STEPS={count}\n"
    return f"""ene: ENERGY

ecv: ECV_MULTITHERMAL ...
  ARG=ene
  TEMP={number(base_temperature)}
  TEMP_MIN={number(minimum)}
  TEMP_MAX={number(maximum)}
{temperature_steps}...

opes: OPES_EXPANDED ...
  ARG=ecv.ene
  PACE={pace}
{observation_steps}  FILE={state_path(args, 'DELTAFS')}
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
        # [plumed] passthrough: extra bias keywords and extra actions.
        text = apply_plumed_options(config, text, "opes")
    except (TypeError, ValueError) as error:
        raise SystemExit(f"Config error in {args.stage} ({args.config}): {error}") from None
    restart = "RESTART\n\n" if args.restart and not args.parse_only else ""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(restart + text, encoding="utf-8")


if __name__ == "__main__":
    main()
