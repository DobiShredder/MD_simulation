#!/usr/bin/env python3
"""Publish the FEP report and its three TSV outputs as one checked generation."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import uuid


OUTPUT_NAMES = ("mbar", "free_energy.tsv", "mbar_diagnostics.tsv", "overlap_matrix.tsv")
MARKER = ".analysis-generation.json"


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def output_hashes(work: Path) -> dict[str, str]:
    files = {}
    for name in OUTPUT_NAMES:
        path = work / name
        if name == "mbar":
            if not path.is_dir():
                raise ValueError(f"MBAR report directory was not created: {path}")
            paths = sorted(item for item in path.rglob("*") if item.is_file())
            if not paths:
                raise ValueError(f"MBAR report directory is empty: {path}")
        else:
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"FEP analysis output was not created: {path}")
            paths = [path]
        for item in paths:
            files[str(item.relative_to(work))] = file_digest(item)
    return files


def verify_analysis(work: Path) -> str:
    pending = work / ".analysis.pending"
    if pending.exists():
        raise ValueError(f"FEP analysis publication is incomplete; inspect {pending}")
    marker = work / MARKER
    try:
        marker_text = marker.read_text(encoding="utf-8")
        record = json.loads(marker_text)
        if not isinstance(record["generation"], str) or not record["generation"]:
            raise ValueError("invalid generation identifier")
        if record["files"] != output_hashes(work):
            raise ValueError("report and TSV hashes do not match the completed generation")
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Incomplete or mixed FEP analysis generation: {marker}; {error}") from error
    if pending.exists() or marker.read_text(encoding="utf-8") != marker_text:
        raise ValueError(f"FEP analysis generation changed while reading: {work}")
    return record["generation"]


def relocate_report_paths(stage: Path, work: Path) -> None:
    # FE-ToolKit records the extraction directory in XML/Python/HTML reports.
    # Keep those references usable after moving the validated report to work/mbar.
    replacements = ((str(stage.absolute()), str(work.absolute())), (str(stage), str(work)))
    for path in (stage / "mbar").rglob("*"):
        if path.is_file() and path.suffix in (".xml", ".py", ".html"):
            text = path.read_text(encoding="utf-8")
            for old, new in replacements:
                text = text.replace(old, new)
            path.write_text(text, encoding="utf-8")


@contextmanager
def analysis_generation(work: Path):
    pending = work / ".analysis.pending"
    if pending.exists():
        raise ValueError(f"FEP analysis publication is incomplete; inspect {pending}")
    for name in (*OUTPUT_NAMES, MARKER):
        if (work / name).is_symlink():
            raise ValueError(f"FEP analysis output must not be a symlink: {work / name}")
    temporary = Path(tempfile.mkdtemp(prefix=".analysis.generation-", dir=work))
    stage = temporary / "new"
    previous = temporary / "previous"
    stage.mkdir()
    previous.mkdir()
    owns_pending = False
    retain_backup = False
    try:
        yield stage
        relocate_report_paths(stage, work)
        record = {"generation": uuid.uuid4().hex, "files": output_hashes(stage)}
        (stage / MARKER).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        names = (*OUTPUT_NAMES, MARKER)
        with pending.open("x", encoding="utf-8") as handle:
            owns_pending = True
            handle.write(f"Previous results: {previous}\nNew results: {stage}\n")
        for name in names:
            if (work / name).exists():
                (work / name).rename(previous / name)
        for name in names:
            (stage / name).rename(work / name)
        if output_hashes(work) != record["files"]:
            raise ValueError(f"Published FEP output hashes differ: {work}")
        pending.unlink()
        owns_pending = False
    except BaseException:
        if owns_pending:
            try:
                for name in names:
                    if not (stage / name).exists() and (work / name).exists():
                        (work / name).rename(stage / name)
                for name in names:
                    if (previous / name).exists():
                        (previous / name).rename(work / name)
                pending.unlink()
            except OSError:
                retain_backup = True
                print(f"Error: FEP publication rollback failed; preserve and inspect {temporary} and {pending}", file=sys.stderr)
        for log in stage.rglob("*.log"):
            print(f"Failed analysis log: {log}", file=sys.stderr)
            print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]), file=sys.stderr)
        raise
    finally:
        if not retain_backup:
            shutil.rmtree(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the completed FEP report/TSV generation.")
    parser.add_argument("work", type=Path, help="Simulation work directory containing FEP analysis outputs")
    args = parser.parse_args()
    try:
        verify_analysis(args.work)
    except (OSError, ValueError) as error:
        raise SystemExit(f"FEP analysis verification failed: {error}") from error
    print(f"Completed FEP analysis generation: {args.work}")


if __name__ == "__main__":
    main()
