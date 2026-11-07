#!/usr/bin/env python3
"""Check that the WE basis state starts outside every target bin.

WESTPA uses the bin that contains each work/tstate.file value as a target
(recycling) bin. configure_we.py writes that file from weighted_ensemble.target_state.
Bins are [b0, b1), ..., [b_last, inf) from bin_boundaries.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_utils import load_config  # noqa: E402


def read_target_values(target_file: Path) -> list[float]:
    values: list[float] = []
    for line_number, raw in enumerate(target_file.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 2:
            raise ValueError(f"{target_file}:{line_number}: expected LABEL VALUE")
        try:
            value = float(fields[1])
        except ValueError:
            raise ValueError(f"{target_file}:{line_number}: target value is not numeric") from None
        if not math.isfinite(value):
            raise ValueError(f"{target_file}:{line_number}: target value is not finite")
        values.append(value)
    if not values:
        raise ValueError(f"No target state was found: {target_file}")
    return values


def bin_index(boundaries: list[float], value: float, name: str) -> int:
    """Return the RectilinearBinMapper bin index; the last bin extends to inf."""
    if value < boundaries[0]:
        raise ValueError(f"{name} {value:g} is below the first bin boundary {boundaries[0]:g}")
    index = 0
    for position, lower in enumerate(boundaries):
        if value >= lower:
            index = position
    return index


def bin_label(boundaries: list[float], index: int) -> str:
    upper = boundaries[index + 1] if index + 1 < len(boundaries) else math.inf
    return f"[{boundaries[index]:g}, {upper:g})"


def check_target_bins(boundaries: list[float], target_values: list[float]) -> set[int]:
    targets = {bin_index(boundaries, value, "target state value") for value in target_values}
    if len(targets) == len(boundaries):
        raise ValueError("every bin is a target bin; at least one bin must remain outside the target")
    return targets


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("work_dir", type=Path, help="WE work directory written by build.sh")
    return parser.parse_args()


def main() -> None:
    args = arguments()
    config_file = args.work_dir / "resolved_config.toml"
    target_file = args.work_dir / "tstate.file"
    basis_file = args.work_dir / "basis_pcoord.txt"
    try:
        boundaries = [float(value) for value in load_config(config_file)["weighted_ensemble"]["bin_boundaries"]]
        targets = check_target_bins(boundaries, read_target_values(target_file))
        basis_value = float(basis_file.read_text(encoding="utf-8").split()[0])
        if not math.isfinite(basis_value):
            raise ValueError(f"basis progress coordinate is not finite: {basis_value}")
        basis_bin = bin_index(boundaries, basis_value, "basis progress coordinate")
    except (OSError, KeyError, IndexError, ValueError) as error:
        raise SystemExit(f"Error: WE basis/target state check failed: {error}. "
                         f"Inputs: {config_file}, {target_file}, {basis_file}") from None

    target_text = ", ".join(bin_label(boundaries, index) for index in sorted(targets))
    print(f"Basis progress coordinate: {basis_value:g} A in bin {bin_label(boundaries, basis_bin)}; "
          f"target bin(s): {target_text}")
    if basis_bin in targets:
        raise SystemExit(
            f"Error: the basis progress coordinate {basis_value:g} A lies in a target bin "
            f"{bin_label(boundaries, basis_bin)}, so WESTPA would recycle the walkers at once. "
            f"Change weighted_ensemble.bin_boundaries or weighted_ensemble.target_state and build in a new WORK_DIR."
        )


if __name__ == "__main__":
    main()
