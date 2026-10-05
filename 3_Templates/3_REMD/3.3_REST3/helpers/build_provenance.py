#!/usr/bin/env python3
"""Write compact provenance for a completed REST build."""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def version_line(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        return f"unavailable: {error}"
    text = completed.stdout or completed.stderr
    return next((line.strip() for line in text.splitlines() if line.strip()), "unknown")


def charge_summary(logs: list[Path]) -> tuple[int, float | None]:
    warning_count = 0
    total_charge = None
    pattern = re.compile(r"System has non-zero total charge:\s*([-+0-9.eE]+)")
    for path in logs:
        if not path.is_file():
            raise SystemExit(f"Charge provenance log is missing: {path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        warning_count += len(re.findall(r"^WARNING \d+ \[", text, flags=re.MULTILINE))
        matches = pattern.findall(text)
        if matches:
            total_charge = float(matches[-1])
            if not math.isfinite(total_charge):
                raise SystemExit(f"Charge provenance is nonfinite: {path}")
    return warning_count, total_charge


def energy_status(path: Path | None) -> tuple[str, float]:
    if path is None or not path.is_file():
        return "not_run", 0.0
    rows = [
        line.split("\t")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("variant\t")
    ]
    if not rows:
        return "missing", 0.0
    status = rows[-1][-1]
    tolerance = float(rows[-1][-2])
    return status, tolerance


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path, help="Output TOML path")
    parser.add_argument("--method", required=True, help="REST method name")
    parser.add_argument("--gromacs", required=True, help="GROMACS executable")
    parser.add_argument("--plumed", required=True, help="PLUMED executable")
    parser.add_argument("--python", required=True, help="Python executable with ParmEd")
    parser.add_argument("--resolved-config", required=True, type=Path, help="Resolved config")
    parser.add_argument("--base-topology", required=True, type=Path, help="Canonical topology")
    parser.add_argument("--states", required=True, type=Path, help="Replica state table")
    parser.add_argument("--energy-table", type=Path, help="Energy identity TSV")
    parser.add_argument("--warning-log", action="append", default=[], type=Path, help="grompp log")
    parser.add_argument("--topology", action="append", default=[], type=Path, help="Final topology")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    required = [args.resolved_config, args.base_topology, args.states, *args.topology]
    missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise SystemExit(f"Required final build output is missing or empty: {', '.join(missing)}")

    warning_count, total_charge = charge_summary(args.warning_log)
    check_status, tolerance = energy_status(args.energy_table)
    if args.energy_table is not None and check_status != "pass":
        raise SystemExit(f"Energy identity check did not pass: {check_status}")

    lines = [
        'status = "passed"',
        f"method = {toml_string(args.method)}",
        f"generated_at_utc = {toml_string(datetime.now(timezone.utc).isoformat())}",
        "",
        "[versions]",
        f"gromacs = {toml_string(version_line([args.gromacs, '--version']))}",
        f"plumed = {toml_string(version_line([args.plumed, 'info', '--version']))}",
        f"parmed = {toml_string(version_line([args.python, '-c', 'import parmed; print(parmed.__version__)']))}",
        "",
        "[hashes]",
        f"resolved_config_sha256 = {toml_string(sha256(args.resolved_config))}",
        f"base_topology_sha256 = {toml_string(sha256(args.base_topology))}",
        f"state_table_sha256 = {toml_string(sha256(args.states))}",
        "",
        "[validation]",
        f"charge_warning_count = {warning_count}",
        f"total_charge_known = {str(total_charge is not None).lower()}",
        *([f"total_charge_e = {total_charge:.12g}"] if total_charge is not None else []),
        f"charge_warning_accepted = {str(warning_count > 0 and total_charge is not None and abs(total_charge) <= 0.01).lower()}",
        f"energy_check_status = {toml_string(check_status)}",
        f"energy_tolerance_kJ_mol = {tolerance:.12g}",
        "",
    ]
    for topology in args.topology:
        lines.extend(
            [
                "[[topologies]]",
                f"path = {toml_string(str(topology))}",
                f"size_bytes = {topology.stat().st_size}",
                f"sha256 = {toml_string(sha256(topology))}",
                "",
            ]
        )
    args.output.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
