"""Publish complete source assets while preserving unrelated files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys


def publish(stage, destination, dependencies=None):
    markers = [destination / ".download.pending"]
    if dependencies is not None:
        markers.append(dependencies.parent / f".{dependencies.name}.download.pending")
    for marker in markers:
        if marker.exists() or marker.is_symlink():
            raise RuntimeError(f"Download publication is incomplete; inspect {marker}")
    files = sorted(path for path in stage.iterdir() if path.name != ".dependencies")
    if not files or any(not path.is_file() or path.is_symlink() or path.stat().st_size == 0 for path in files):
        raise ValueError(f"Download staging contains missing, empty or invalid assets: {stage}")
    manifest = stage / "SHA256SUMS"
    expected = {}
    for line in manifest.read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.lstrip(" *")
        if name in expected or Path(name).name != name:
            raise ValueError(f"Invalid checksum filename: {name}")
        expected[name] = digest
    if set(expected) != {path.name for path in files if path != manifest}:
        raise ValueError(f"Checksum asset list does not match staging: {manifest}")
    for name, digest in expected.items():
        if hashlib.sha256((stage / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Checksum mismatch before publication: {stage / name}")
    publications = [(source, destination / source.name) for source in files]
    for source, target in publications:
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError(f"Download destination is not a regular file: {target}")
    if dependencies is not None:
        staged_dependencies = stage / ".dependencies"
        if not staged_dependencies.is_dir():
            raise ValueError(f"Parser staging directory is missing: {staged_dependencies}")
        for source in sorted(staged_dependencies.iterdir()):
            target = dependencies / source.name
            if source.is_symlink() or target.is_symlink():
                raise ValueError(f"Parser asset is not a regular file or directory: {source}")
            publications.append((source, target))
        dependencies.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    backup = stage / ".previous"
    failed = stage / ".unpublished"
    backup.mkdir()
    failed.mkdir()
    previous = [target.exists() for source, target in publications]
    attempted = []
    created_markers = []
    old_handlers = {}

    def interrupted(signum, frame):
        raise InterruptedError(f"Download publication interrupted by signal {signum}")

    for signum in (signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, interrupted)
    try:
        for marker in markers:
            with marker.open("x") as handle:
                created_markers.append(marker)
                json.dump({"stage": str(stage), "targets": [str(p) for _, p in publications], "previous": previous}, handle)
                handle.write("\n")
        for index, (source, target) in enumerate(publications):
            attempted.append(index)
            if previous[index]:
                os.replace(target, backup / str(index))
            os.replace(source, target)
        for marker in created_markers:
            marker.unlink()
    except BaseException:
        for signum in old_handlers:
            signal.signal(signum, signal.SIG_IGN)
        for index in reversed(attempted):
            target = publications[index][1]
            original = backup / str(index)
            if original.exists():
                if target.exists():
                    os.replace(target, failed / str(index))
                os.replace(original, target)
            elif not previous[index] and target.exists():
                os.replace(target, failed / str(index))
        for marker in created_markers:
            marker.unlink(missing_ok=True)
        raise
    finally:
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--dependencies", type=Path, help="REST3 parser asset destination")
    args = parser.parse_args()
    try:
        publish(args.stage, args.destination, args.dependencies)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Error: download publication: {error}; staging: {args.stage}; destination: {args.destination}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
