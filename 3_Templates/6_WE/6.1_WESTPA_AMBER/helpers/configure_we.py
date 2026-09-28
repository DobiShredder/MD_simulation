#!/usr/bin/env python3
"""Validate WE settings and generate WESTPA/AMBER runtime files."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, ".")
from apply_config import apply_config  # noqa: E402
from config_utils import load_config, positive_float, positive_int, section, string_value  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate WESTPA block configs and AMBER segment input.")
    parser.add_argument("config", type=Path, help="Template TOML configuration")
    parser.add_argument("output", type=Path, help="Generated WESTPA work directory")
    return parser.parse_args()


def float_list(values: dict[str, object], key: str) -> list[float]:
    raw = values.get(key)
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError(f"{key} must contain at least two numeric boundaries")
    result: list[float] = []
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{key} must contain only numbers")
        result.append(float(item))
    if result != sorted(set(result)):
        raise ValueError(f"{key} must be unique and increasing")
    return result


def render_west_config(boundaries: list[float], walkers: int, iterations: int) -> str:
    boundary_text = ", ".join(f"{value:g}" for value in boundaries) + ", 'inf'"
    return f"""---
west:
  system:
    driver: westpa.core.systems.WESTSystem
    system_options:
      pcoord_ndim: 1
      pcoord_len: 2
      pcoord_dtype: !!python/name:numpy.float32
      bins:
        type: RectilinearBinMapper
        boundaries:
          - [{boundary_text}]
      bin_target_counts: {walkers}
  propagation:
    max_total_iterations: {iterations}
    propagator: executable
    gen_istates: false
  data:
    west_data_file: $WORK_DIR/west.h5
    datasets:
      - name: pcoord
        scaleoffset: 4
    data_refs:
      segment: $WORK_DIR/traj_segs/{{segment.n_iter:06d}}/{{segment.seg_id:06d}}
      basis_state: $WORK_DIR/bstates/{{basis_state.auxref}}
      initial_state: $WORK_DIR/istates/{{initial_state.iter_created}}/{{initial_state.state_id}}
  executable:
    environ: {{}}
    propagator:
      executable: $WEST_SIM_ROOT/westpa_scripts/runseg.sh
      stdout: $WORK_DIR/seg_logs/{{segment.n_iter:06d}}-{{segment.seg_id:06d}}.log
      stderr: stdout
    get_pcoord:
      executable: $WEST_SIM_ROOT/westpa_scripts/get_pcoord.sh
      stdout: $WORK_DIR/get_pcoord.log
      stderr: stdout
"""


def amber_input(title: str, values: list[str]) -> str:
    body = "\n".join(f"  {value}," for value in values)
    return f"{title}\n&cntrl\n{body}\n/\n"


def main() -> None:
    args = arguments()
    detected_salt_pairs: int | None = None
    generated_manifest = args.output / "resolved_config.toml"
    if generated_manifest.is_file():
        generated = load_config(generated_manifest)
        salt_value = generated.get("build", {}).get("salt_pairs")
        if isinstance(salt_value, int) and salt_value >= 0:
            detected_salt_pairs = salt_value
    try:
        config = load_config(args.config)
        run = section(config, "run")
        we = section(config, "weighted_ensemble")
        if string_value(we, "mode") != "steady_state":
            raise ValueError("mode currently supports only steady_state")
        mask = string_value(we, "progress_coordinate_mask")
        basis = Path(string_value(we, "basis_state_file"))
        target = Path(string_value(we, "target_state_file"))
        if not basis.is_file() or not target.is_file():
            raise ValueError("basis_state_file and target_state_file must exist")
        tau_steps = positive_int(we, "tau_steps")
        total_iterations = positive_int(we, "total_iterations")
        blocks = positive_int(we, "run_blocks")
        per_block = positive_int(we, "iterations_per_block")
        if blocks * per_block != total_iterations:
            raise ValueError("run_blocks * iterations_per_block must equal total_iterations")
        walkers = positive_int(we, "walkers_per_bin")
        initial = positive_int(we, "initial_walkers")
        boundaries = float_list(we, "bin_boundaries")
        timestep_ps = positive_float(run, "timestep") / 1000.0
        temperature = positive_float(run, "temperature")
        pressure = positive_float(run, "pressure")
    except ValueError as error:
        raise SystemExit(f"Config error: {error}") from None

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "configs").mkdir(exist_ok=True)
    (args.output / "inputs").mkdir(exist_ok=True)
    (args.output / "bstates").mkdir(exist_ok=True)
    shutil.copy2(basis, args.output / "bstates/bstates.txt")
    shutil.copy2(target, args.output / "tstate.file")
    (args.output / "progress_coordinate.mask").write_text(mask + "\n", encoding="utf-8")
    (args.output / "initial_walkers.txt").write_text(f"{initial}\n", encoding="ascii")
    shutil.copy2(args.config, args.output / "source_config.toml")

    for block in range(1, blocks + 1):
        limit = block * per_block
        path = args.output / "configs" / f"west.{block:03d}.cfg"
        path.write_text(render_west_config(boundaries, walkers, limit), encoding="utf-8")

    segment = amber_input(
        "One weighted-ensemble segment",
        [
            "imin=0", "irest=1", "ntx=5", "ntxo=2", "ig=WEST_SEED",
            f"nstlim={tau_steps}", f"dt={timestep_ps:.6f}",
            f"temp0={temperature:.3f}", "ntt=3", "gamma_ln=1.0",
            "ntb=2", "ntp=1", "barostat=2", f"pres0={pressure:.3f}",
            "taup=2.0", "ntc=2", "ntf=2", "cut=10.0", "ntr=0",
            f"ntpr={tau_steps}", "ntwx=0", f"ntwr={tau_steps}",
        ],
    )
    (args.output / "inputs/segment.in.template").write_text(segment, encoding="utf-8")
    resolved = args.config.read_text(encoding="utf-8").rstrip()
    resolved += "\n\n[resolved]\n"
    if detected_salt_pairs is not None:
        resolved += f"salt_pairs = {detected_salt_pairs}\n"
    resolved += f"tau_ps = {tau_steps * timestep_ps:.6f}\n"
    resolved += f"generated_block_configs = {blocks}\n"
    (args.output / "resolved_config.toml").write_text(resolved, encoding="utf-8")
    apply_config(args.config, args.output)
    print(
        f"WESTPA configuration: {blocks} blocks, {total_iterations} iterations, "
        f"tau={tau_steps * timestep_ps:.3f} ps"
    )


if __name__ == "__main__":
    main()
