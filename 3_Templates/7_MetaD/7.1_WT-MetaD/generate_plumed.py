#!/usr/bin/env python3
"""Generate PLUMED 2.10 input for WT-MetaD production segments."""

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
        "--cv-file",
        type=Path,
        required=True,
        help="PLUMED collective-variable definitions",
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





def main() -> None:
    args = parse_arguments()
    try:
        config = load_config(args.config)
        text = render_wt(args, config)
    except (TypeError, ValueError) as error:
        raise SystemExit(f"Config error: {error}") from None
    restart = "RESTART\n\n" if args.restart and not args.parse_only else ""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(restart + text, encoding="utf-8")


if __name__ == "__main__":
    main()
