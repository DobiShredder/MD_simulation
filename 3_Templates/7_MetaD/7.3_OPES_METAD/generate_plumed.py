#!/usr/bin/env python3
"""Generate PLUMED 2.10 input for OPES_METAD production segments."""

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




def main() -> None:
    args = parse_arguments()
    try:
        config = load_config(args.config)
        text = render_opes_metad(args, config)
    except (TypeError, ValueError) as error:
        raise SystemExit(f"Config error: {error}") from None
    restart = "RESTART\n\n" if args.restart and not args.parse_only else ""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(restart + text, encoding="utf-8")


if __name__ == "__main__":
    main()
