#!/usr/bin/env python3
"""고정 temperature/κ table에 맞춰 ssREST3 topology를 생성합니다."""

from __future__ import annotations

import argparse
import csv
import importlib
import importlib.util
import os
import shutil
from pathlib import Path
from types import ModuleType


def load_parser_module() -> ModuleType:
    candidates = (
        "repex_topology_parser",
        "src.repex_topology_parser",
    )

    for name in candidates:
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            continue

    source_value = os.environ.get("REPEX_TOPOLOGY_PARSER_SOURCE", "")
    if source_value:
        source = Path(source_value).expanduser().resolve()
        if source.is_dir():
            source = source / "src" / "repex_topology_parser.py"

        if not source.is_file():
            raise SystemExit(
                "REPEX_TOPOLOGY_PARSER_SOURCE에서 parser를 찾지 못했습니다: "
                f"{source}"
            )

        spec = importlib.util.spec_from_file_location(
            "repex_topology_parser_external", source
        )
        if spec is None or spec.loader is None:
            raise SystemExit(f"parser module을 불러올 수 없습니다: {source}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    raise SystemExit(
        "repex-topology-parser 0.2.2 module을 찾지 못했습니다. "
        "README의 source-package 안내와 REPEX_TOPOLOGY_PARSER_SOURCE를 확인하세요."
    )


def generated_hot_topology(
    output_dir: Path, lambda_pp: float, kappa: float
) -> Path:
    expected_suffix = f"-{lambda_pp:.3f}-{kappa:.3f}.top"
    candidates = [
        path
        for path in output_dir.rglob("*.top")
        if path.name.endswith(expected_suffix)
    ]

    if len(candidates) != 1:
        raise SystemExit(
            "target λ/κ topology를 하나로 식별하지 못했습니다: "
            f"suffix={expected_suffix}, found={len(candidates)}"
        )

    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("processed_topology", type=Path)
    parser.add_argument("states", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()

    module = load_parser_module()
    args.output_directory.mkdir(parents=True, exist_ok=True)

    with args.states.open(encoding="utf-8", newline="") as handle:
        states = list(csv.DictReader(handle, delimiter="\t"))

    if len(states) != 8:
        raise SystemExit(f"REST3 state는 8개여야 합니다: {len(states)}")

    base_target = args.output_directory / "000" / "topol.top"
    base_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.processed_topology, base_target)

    for state in states[1:]:
        replica = state["replica"]
        temperature = float(state["effective_temperature_K"])
        lambda_pp = float(state["lambda_pp"])
        kappa = float(state["kappa"])
        temporary = args.output_directory / f".rest3_{replica}"
        temporary.mkdir(parents=True, exist_ok=True)

        converter = module.topo2rest(str(args.processed_topology))

        molecules = getattr(converter, "molecules", {})
        protein_name = str(molecules.get(0, "")).lower()
        if "protein" not in protein_name:
            raise SystemExit(
                "hot molecule index 0이 protein이 아닙니다: "
                f"{molecules.get(0, '<unknown>')}"
            )

        converter.run(
            method="ssrest3",
            hot_molecules=[0],
            nreps=2,
            temps=[300.0, temperature],
            kappa_low_temp=300.0,
            kappa_max=kappa,
            kappa_atom_names=["OW"],
            outfile=f"rest3_{replica}",
            filepath=f"{temporary}/",
            verbose=False,
        )

        source = generated_hot_topology(temporary, lambda_pp, kappa)
        target = args.output_directory / replica / "topol.top"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        shutil.rmtree(temporary)

    print(f"REST3 topology 8개를 생성했습니다: {args.output_directory}")


if __name__ == "__main__":
    main()
