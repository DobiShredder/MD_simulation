#!/usr/bin/env python3
"""RBFE environment/window directory와 AMBER input을 생성합니다."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


LAMBDAS = [index / 10 for index in range(11)]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", type=Path)
    parser.add_argument("input_dir", type=Path)
    return parser.parse_args()


def render(template: Path, output: Path, replacements: dict[str, str]) -> None:
    text = template.read_text(encoding="utf-8")
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    if "@" in text:
        raise SystemExit(f"치환되지 않은 marker가 있습니다: {output}")
    output.write_text(text, encoding="utf-8")


def relative_link(target: Path, link: Path) -> None:
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(os.path.relpath(target, link.parent))


def main() -> None:
    args = parse_arguments()
    state_rows = ["environment\twindow\tlambda\tseed\tdirectory"]
    state_index = 0

    for environment in ("complex", "solvent"):
        topology = args.work_dir / "build" / f"{environment}.parm7"
        restart = args.work_dir / "build" / f"{environment}.rst7"
        for window_index, lambda_value in enumerate(LAMBDAS):
            state_index += 1
            window = f"{window_index:03d}"
            directory = args.work_dir / environment / window
            directory.mkdir(parents=True, exist_ok=True)

            relative_link(topology, directory / "system.parm7")
            relative_link(restart, directory / "system.rst7")
            replacements = {
                "@LAMBDA@": f"{lambda_value:.1f}",
                "@RANDOM_SEED@": str(51000 + state_index),
            }
            render(args.input_dir / "heat.in.template", directory / "heat.in", replacements)
            render(
                args.input_dir / "equilibrate.in.template",
                directory / "equilibrate.in",
                replacements,
            )
            render(
                args.input_dir / "production.in.template",
                directory / "production.in",
                replacements,
            )
            render(
                args.input_dir / "minimize.in.template",
                directory / "minimize.in",
                replacements,
            )
            state_rows.append(
                f"{environment}\t{window}\t{lambda_value:.1f}\t"
                f"{51000 + state_index}\t{directory}"
            )

    (args.work_dir / "states.tsv").write_text("\n".join(state_rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
