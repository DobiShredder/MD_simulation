#!/usr/bin/env python3
"""Publish a complete analysis directory and verify its recorded output hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import uuid
from contextlib import contextmanager



def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record_generation(directory: Path) -> None:
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != ".generation.json":
            files[str(path.relative_to(directory))] = file_digest(path)
    if not files:
        raise ValueError(f"No analysis outputs were created: {directory}")
    marker = directory / ".generation.json"
    inputs = json.loads(marker.read_text(encoding="utf-8"))["inputs"] if marker.exists() else list(files)
    record = {"generation": uuid.uuid4().hex, "files": files, "inputs": inputs}
    (directory / ".generation.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )


def verify_generation(directory: Path) -> str:
    pending = directory.with_name(f".{directory.name}.pending")
    if pending.exists():
        raise ValueError(f"Analysis publication is incomplete: {pending}")
    marker = directory / ".generation.json"
    try:
        marker_text = marker.read_text(encoding="utf-8")
        record = json.loads(marker_text)
        generation = record["generation"]
        files = record["files"]
        if not isinstance(generation, str) or not generation:
            raise ValueError("invalid generation identifier")
        if not isinstance(files, dict) or not files:
            raise ValueError("missing output hashes")
        actual = {
            str(path.relative_to(directory))
            for path in directory.rglob("*")
            if path.is_file() and path.name != ".generation.json"
        }
        if set(files) != actual:
            raise ValueError("output set differs from the completed generation")
        for name, expected in files.items():
            if file_digest(directory / name) != expected:
                raise ValueError(f"output hash differs: {directory / name}")
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Incomplete or mixed analysis generation: {marker}; "
            f"run ./run.sh again. {error}"
        ) from error
    if pending.exists() or marker.read_text(encoding="utf-8") != marker_text:
        raise ValueError(f"Analysis generation changed while reading: {directory}")
    return generation


@contextmanager
def result_generation(output_dir: Path):
    pending = output_dir.with_name(f".{output_dir.name}.pending")
    if pending.exists():
        raise ValueError(f"Analysis publication is incomplete; inspect {pending}")
    if output_dir.is_symlink():
        raise ValueError(f"Analysis output must be a directory, not a symlink: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.generation-", dir=output_dir.parent))
    stage = temporary / "new"
    previous = temporary / "previous"
    stage.mkdir()
    owns_pending = False
    retain_backup = False
    try:
        yield stage
        record_generation(stage)
        verify_generation(stage)
        with pending.open("x", encoding="utf-8") as handle:
            owns_pending = True
            handle.write(f"Previous results: {previous}\nNew results: {stage}\n")
        if output_dir.exists():
            output_dir.rename(previous)
        stage.rename(output_dir)
        pending.unlink()
        owns_pending = False
    except BaseException:
        if owns_pending:
            try:
                if not stage.exists() and output_dir.exists():
                    output_dir.rename(stage)
                if previous.exists():
                    previous.rename(output_dir)
                pending.unlink()
            except OSError:
                retain_backup = True
                print(f"Error: publication rollback failed; preserve and inspect {temporary} and {pending}", file=sys.stderr)
        raise
    finally:
        if not retain_backup:
            shutil.rmtree(temporary)


def copy_analysis_inputs(output_dir: Path, stage: Path) -> None:
    generation = verify_generation(output_dir)
    record = json.loads((output_dir / ".generation.json").read_text(encoding="utf-8"))
    for name in record["inputs"]:
        if name not in record["files"]:
            raise ValueError(f"Unrecorded analysis input: {output_dir / name}")
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output_dir / name, target)
    if verify_generation(output_dir) != generation:
        raise ValueError(f"Analysis inputs changed while copying: {output_dir}")
    record_generation(stage)
    verify_generation(stage)


@contextmanager
def input_generation(output_dir: Path):
    with result_generation(output_dir) as stage:
        copy_analysis_inputs(output_dir, stage)
        yield stage


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish validated analysis outputs; called by run.sh.")
    parser.add_argument("stage", type=Path, help="Fresh output directory created by run.sh")
    parser.add_argument("output", type=Path, help="Completed analysis output directory")
    args = parser.parse_args()
    try:
        with result_generation(args.output) as stage:
            stage.rmdir()
            args.stage.rename(stage)
    except (OSError, KeyError, ValueError) as error:
        raise SystemExit(f"Analysis publication failed: {args.output}; {error}") from error


if __name__ == "__main__":
    main()
