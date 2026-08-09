#!/usr/bin/env python3
"""cpptraj trajectory 길이와 sampling 설정으로 source-frame map을 만든다."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpptraj", default="cpptraj")
    return parser.parse_args()


def read_metadata(output_dir: Path) -> dict[str, str]:
    rows = (output_dir / "run_metadata.tsv").read_text(encoding="utf-8").splitlines()
    return dict(line.split("\t", maxsplit=1) for line in rows[1:] if line)


def read_trajectories(output_dir: Path) -> list[Path]:
    rows = (output_dir / "trajectories.tsv").read_text(encoding="utf-8").splitlines()
    return [Path(line.split("\t", maxsplit=1)[1]) for line in rows[1:] if line]


def count_frames(cpptraj: str, topology: Path, trajectory: Path) -> int:
    command = [cpptraj, "-p", str(topology), "-y", str(trajectory), "-tl"]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    text = result.stdout + "\n" + result.stderr
    patterns = (
        r"Frames:\s*([0-9]+)",
        r"with\s+([0-9]+)\s+frames",
        r"([0-9]+)\s+frames\.",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    raise ValueError(f"trajectory frame 수를 읽지 못했습니다: {trajectory}")


def selected_frames(total: int, start: int, stop_value: str, stride: int) -> range:
    stop = total if stop_value == "last" else min(int(stop_value), total)
    if start > stop:
        raise ValueError(f"선택된 frame이 없습니다: start={start}, stop={stop}")
    return range(start, stop + 1, stride)


def main() -> int:
    args = parse_arguments()
    metadata = read_metadata(args.output)
    topology = Path(metadata["topology"])
    start = int(metadata["start_frame"])
    stop = metadata["stop_frame"]
    stride = int(metadata["stride"])

    rows = ["output_frame\tsource_index\tsource_file\tsource_frame"]
    output_frame = 1
    for source_index, trajectory in enumerate(read_trajectories(args.output), start=1):
        total = count_frames(args.cpptraj, topology, trajectory)
        for source_frame in selected_frames(total, start, stop, stride):
            rows.append(
                f"{output_frame}\t{source_index}\t{trajectory}\t{source_frame}"
            )
            output_frame += 1

    (args.output / "frame_map.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
